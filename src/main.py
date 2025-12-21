import asyncio
import os
import time
import logging
from typing import List, Dict, Optional, Any, Callable, Tuple
from dotenv import load_dotenv

# Internal imports (relative within src package)
from blocky import BlockyWebSocket, CircuitBreakerOpen
from blocky.async_client import AsyncBlocky
from price_model import PriceModel
from spread_calculator import SpreadCalculator, SpreadConfig
from metrics import MetricsTracker
from alerts import AlertManager, AlertLevel
from config import get_config
from health import HealthServer
from trading_helpers import (
    calculate_quotes,
    apply_pennying,
    calculate_locked_funds,
    calculate_order_quantities,
    calculate_order_quantities,
    diff_orders
)
from data_recorder import DataRecorder


# Load environment variables from .env file
load_dotenv(override=True)

# Configure structured logging
class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels."""
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname:8s}{self.RESET}"
        return super().format(record)

# Setup console handler with colored output
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter(
    fmt='%(asctime)s │ %(levelname)s │ %(message)s',
    datefmt='%H:%M:%S'
))

# Setup file handler for persistent logging
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'bot.log')

file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
file_handler.setFormatter(logging.Formatter(
    fmt='%(asctime)s │ %(levelname)-8s │ %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))

logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])
logger = logging.getLogger(__name__)

# Configuration - Load from config.yaml with env var overrides
config = get_config()
API_KEY = config.api.api_key
if not API_KEY:
    raise RuntimeError("BLOCKY_API_KEY environment variable is not set. Please set it before running the bot.")
API_ENDPOINT = config.api.endpoint
TARGET_VALUE = config.trading.target_value
MAX_QUANTITY = config.trading.max_quantity
REFRESH_INTERVAL = config.trading.refresh_interval
MIN_SPREAD_TICKS = config.trading.min_spread_ticks
FALLBACK_SPREAD = config.trading.spread  # Used when dynamic spread is disabled

class MarketMaker:
    """Automated market maker bot for Blocky exchange."""
    
    def __init__(self, api_key: str, endpoint: str) -> None:
        self.client = AsyncBlocky(api_key=api_key, endpoint=endpoint)
        self.endpoint = endpoint
        self.price_model = PriceModel(
            self.client, 
            base_prices=config.price_model.base_prices
        )
        # self.markets resolved in run() now since it needs async call
        self.markets = []
        self.wallets = {}
        self.last_wallet_update = 0
        self.available_capital = {}
        # Concurrency Control
        self.market_locks = {m: asyncio.Lock() for m in self.markets}
        self.capital_lock = asyncio.Lock()  # Lock for thread-safe Iron allocation
        
        # Determine WS Endpoint from HTTP Endpoint
        ws_endpoint = endpoint.replace("https://", "wss://").replace("http://", "ws://") + "/ws/"
        self.ws = BlockyWebSocket(endpoint=ws_endpoint)
        self.event_queue = asyncio.Queue()
        
        # Performance Metrics
        self.metrics = MetricsTracker()
        
        # Alert System
        self.alerts = AlertManager(
            webhook_url=os.environ.get("ALERT_WEBHOOK_URL"),
            webhook_type=os.environ.get("ALERT_WEBHOOK_TYPE", "discord"),
            min_level=AlertLevel.WARNING
        )
        
        # Trade tracking for metrics
        self.last_trade_cursor = None  # Track last processed trade ID
        
        # Dynamic Spread Calculator
        spread_config = SpreadConfig(
            enabled=config.dynamic_spread.enabled,
            base_spread=config.dynamic_spread.base_spread,
            volatility_multiplier=config.dynamic_spread.volatility_multiplier,
            inventory_impact=config.dynamic_spread.inventory_impact,
            min_spread=config.dynamic_spread.min_spread,
            max_spread=config.dynamic_spread.max_spread,
            volatility_window=config.dynamic_spread.volatility_window
        )
        self.spread_calculator = SpreadCalculator(self.client, spread_config)
        self.recorder = DataRecorder() # Initialize Recorder
        
        if spread_config.enabled:
            logger.info("📊 Dynamic spread calculation enabled")

    async def _on_event_update(self, data: Dict[str, Any]) -> None:
        """Callback for real-time events (Trade or Orderbook)."""
        try:
            # Data: {'channel': 'market:transactions', ...} OR {'channel': 'market:orderbook', ...}
            channel = data.get("channel", "")
            if ":" in channel:
                market = channel.split(":")[0]
                # Log only on transaction to reduce noise, or debug for orderbook
                if "transactions" in channel:
                     logger.info(f"WS Event: Trade on {market}")
                     # Parse trade data from payload
                     payload = data.get("payload", {})
                     # Payload usually mimics the trade object: {price, quantity, side}
                     # We need to verify the exact structure in logs if this fails, but standard is root or nested.
                     # Assuming standard Blocky WS format based on other integrations.
                     price = float(payload.get("price", 0))
                     quantity = float(payload.get("quantity", 0) or payload.get("amount", 0))
                     side = payload.get("side", "buy")
                     
                     if price > 0:
                        self.metrics.record_public_trade(market, price, side, quantity)
                        # Log trade using recorder
                        await self.recorder.log_trade(market, payload)
                
                # Fetch supplies cache (safe to use stale for 60s)
                # We do NOT await get_circulating_supply here if it does network call, 
                # but it uses cache logic. 
                # Fetch supplies cache (safe to use stale for 60s)
                # We do NOT await get_circulating_supply here if it does network call, 
                # but it uses cache logic. 
                supplies = await self.price_model.get_circulating_supply()
                
                # Fetch Open Orders for this market
                # Note: Blocky API ignores filter params, so we filter client-side
                my_orders = []
                try:
                    response = await self.client.get_orders( 
                        statuses=["open"], 
                        markets=[market]
                    )
                    if response.get("success"):
                        # Client-side filtering: API ignores status and market filters
                        for order in response.get("orders", []):
                            order_market = order.get("market", "")
                            order_status = order.get("status", "").lower()
                            if order_market == market and order_status in ["open", "pending", "new"]:
                                my_orders.append(order)
                except Exception as e:
                    logger.error(f"{market}: Failed to fetch open orders in WS handler: {e}")
                    return # Skip processing if we can't see our orders (safety)

                # Fetch Ticker (or use data if possible, but safer to fetch fresh ticker from API to be sure)
                # Relying on _process_market to fetch ticker if None passed?
                # _process_market fetches individual ticker if None passed.
                # To be faster, we could parse the orderbook update? 
                # Orderbook update might be partial. Safer to fetch snapshot or ticker.
                # Let's pass None and let _process_market fetch ticker.
                
                await self._process_market(market, supplies, ticker=None, open_orders=my_orders)
                
        except Exception as e:
            logger.error(f"WS Handler Error: {e}")


    async def _fetch_markets(self) -> List[str]:
        """Fetches available markets from the API and applies config filters."""
        logger.info("Fetching available markets...")
        try:
            response = await self.client.get_markets()
            if response.get("success"):
                all_markets = [m["market"] for m in response.get("markets", [])]
                
                # Apply whitelist (if specified)
                if config.trading.enabled_markets:
                    filtered = [m for m in all_markets if m in config.trading.enabled_markets]
                    logger.info(f"Whitelist active: {len(filtered)}/{len(all_markets)} markets enabled")
                else:
                    filtered = all_markets
                
                # Apply blacklist (always)
                if config.trading.disabled_markets:
                    before_count = len(filtered)
                    filtered = [m for m in filtered if m not in config.trading.disabled_markets]
                    disabled_count = before_count - len(filtered)
                    if disabled_count > 0:
                        logger.info(f"Blacklist active: {disabled_count} markets disabled")
                
                logger.info(f"Found {len(filtered)} markets: {filtered}")
                return filtered
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
        return []

    async def _update_wallets(self) -> None:
        """Fetches and updates wallet balances with 100ms throttling."""
        now = time.time()
        if now - self.last_wallet_update < 0.1:  # 100ms throttle (was 1s)
            return
            
        try:
            response = await self.client.get_wallets()
            if response.get("success"):
                new_wallets = {}
                # Handle varying API response keys
                wallets_data = response.get("wallets", [])
                for w in wallets_data:
                     # Key can be 'currency' or 'instrument'
                     currency = w.get("currency") or w.get("instrument")
                     balance = w.get("balance")
                     
                     if currency and balance is not None:
                        new_wallets[currency.lower()] = float(balance)
                
                self.wallets = new_wallets
                self.last_wallet_update = now
            else:
                logger.debug(f"Failed to update wallets: {response}")
        except Exception as e:
            logger.error(f"Error fetching wallets: {e}")

    async def _fetch_open_orders(self) -> Dict[str, List[dict]]:
        """Fetches all open orders and maps them by market.
        
        Note: The Blocky API ignores filter parameters (status, market), so we
        must filter client-side.
        """
        open_orders = {}
        cursor = None
        has_more = True
        
        try:
            while has_more:
                response = await self.client.get_orders( 
                    statuses=["open"], 
                    limit=50,
                    cursor=cursor
                )
                
                if response.get("success"):
                    orders = response.get("orders", [])
                    if not orders:
                        break
                        
                    for order in orders:
                        # Client-side filtering: API ignores status filter
                        status = order.get("status", "").lower()
                        if status not in ["open", "pending", "new"]:
                            continue

                        m = order.get("market")
                        if not m:
                            continue
                            
                        if m not in open_orders:
                            open_orders[m] = []
                        open_orders[m].append(order)
                    
                    # Pagination Logic
                    # Check for explicit cursor in response
                    next_cursor = response.get("next_cursor") or response.get("cursor")
                    
                    if next_cursor:
                        cursor = next_cursor
                    elif len(orders) >= 50:
                         # Fallback: if no explicit cursor but full page, 
                         # maybe last order ID is the cursor?
                         last_order = orders[-1]
                         cursor = last_order.get("id") or last_order.get("order_id")
                         
                         if not cursor:
                             # Should not happen in valid API, but safe break
                             has_more = False
                    else:
                        has_more = False
                        
                    if len(orders) < 50:
                        has_more = False
                else:
                    logger.error(f"Failed to fetch open orders: {response}")
                    has_more = False
                    
        except Exception as e:
            logger.error(f"Error fetching open orders: {e}")
            
        return open_orders

    async def _poll_recent_trades(self) -> None:
        """Polls recent trades from API and records them in metrics for P&L tracking."""
        try:
            # Fetch recent trades (limit 50, newest first)
            response = await self.client.get_trades(
                limit=50,
                sort_order="desc"
            )
            
            if not response.get("success"):
                logger.debug(f"Failed to fetch trades: {response}")
                return
            
            trades = response.get("trades", [])
            if not trades:
                return
            
            # Process trades in reverse order (oldest first) to maintain chronological order
            new_trades = []
            for trade in reversed(trades):
                trade_id = trade.get("id") or trade.get("trade_id")
                
                # Skip if we've already processed this trade
                if self.last_trade_cursor and trade_id and trade_id <= self.last_trade_cursor:
                    continue
                
                new_trades.append(trade)
            
            # Record new trades in metrics
            for trade in new_trades:
                trade_id = trade.get("id") or trade.get("trade_id")
                market = trade.get("market", "unknown")
                side = trade.get("side", "unknown")
                price = float(trade.get("price", 0))
                quantity = float(trade.get("quantity", 0))
                
                if price > 0 and quantity > 0:
                    self.metrics.record_trade(market, side, price, quantity)
                    logger.info(f"📈 Recorded fill: {side.upper()} {quantity:.2f} {market} @ {price:.2f}")
                
                # Update cursor to latest trade
                if trade_id:
                    if not self.last_trade_cursor or trade_id > self.last_trade_cursor:
                        self.last_trade_cursor = trade_id
            
            if new_trades:
                logger.info(f"Processed {len(new_trades)} new trade(s)")
                
        except Exception as e:
            logger.error(f"Error polling trades: {e}")


    async def _process_market(
        self, 
        market: str, 
        supplies: Dict[str, int], 
        ticker: Optional[Dict[str, Any]] = None, 
        open_orders: Optional[List[Dict[str, Any]]] = None, 
        capital_tracker: Optional[Dict[str, float]] = None
    ) -> None:
        """Processes a single market: Calculates price, checks balance, updates orders."""
        lock = self.market_locks.get(market)
        if not lock: return
        
        # Debounce/Throttle: If locked, skip this update (we only care about latest state)
        if lock.locked():
             return

        async with lock:
            try:
                # 0. Ensure Wallets are Fresh (Throttled 1s)
                # Essential to prevent Stale Wallet + Open Order = Double Count
                await self._update_wallets()

                # 1. Calculate Fair Price
                mid_price = await self.price_model.calculate_fair_price(market)
                
                # Fallback to ticker
                if mid_price <= 0 and ticker:
                     mid_price = float(ticker.get("close", 0) or ticker.get("last", 0) or 0)
                elif mid_price <= 0:
                     t = await self.client.get_ticker(market)
                     mid_price = float(t.get("close", 0))
    
                if mid_price == 0:
                    return

                # Update metrics with current price so sidebar/dashboard has data even without trades
                change = float(ticker.get("change", 0)) if ticker else 0.0
                self.metrics.update_market_price(market, mid_price, change_24h=change)

                # CALCULATE VISUAL STRATEGY PRICES FOR DASHBOARD
                # This doesn't affect trading, just shows what other strategies would do
                strat_prices = {}
                active_strat = config.strategy.type
                
                # We need to simulate price calc for other strategies
                # Scarcity (default logic approx)
                inventory = self.wallets.get(market.split('_')[0], 0)
                scarcity_mult = 1.0 + (0.01 if inventory < 10 else -0.01) # Dummy logic for viz if not creating full objects
                strat_prices['scarcity'] = {'price': mid_price * scarcity_mult, 'confidence': 80}
                
                # VWAP (Approx)
                vwap_price = mid_price * 0.99 # Mock logic for what VWAP usually is relative to mid
                strat_prices['vwap'] = {'price': vwap_price, 'confidence': 60}
                
                # Ticker
                ticker_price = float(ticker.get("last", mid_price)) if ticker else mid_price
                strat_prices['ticker'] = {'price': ticker_price, 'confidence': 100}
                
                # Composite (The actual Fair Price calculated)
                strat_prices['composite'] = {'price': mid_price, 'confidence': 90}

                # Mark active
                if active_strat in strat_prices:
                    strat_prices[active_strat]['active'] = True
                
                self.metrics.update_strategy_prices(market, strat_prices)


                # Calculate Dynamic Spread
                base, quote = market.split('_')  # e.g. ston, iron
                base_inventory = self.wallets.get(base.lower(), 0)
                
                # Get asymmetric spreads based on volatility + inventory
                buy_spread, sell_spread = await self.spread_calculator.get_dynamic_spread(
                    market, 
                    inventory=base_inventory,
                    ticker=ticker
                )
                # Calculate prices using dynamic spreads (using helper function)
                buy_price, sell_price = calculate_quotes(mid_price, buy_spread, sell_spread)
                
                # Log dynamic spread for first few markets (debug)
                logger.debug(f"{market}: Dynamic spread buy={buy_spread:.2%} sell={sell_spread:.2%}")

                # Apply pennying strategy using helper function
                buy_price, sell_price = apply_pennying(
                    buy_price, sell_price, mid_price, ticker, open_orders, MIN_SPREAD_TICKS
                )
                # 2. Check Inventory (base, quote already extracted above)
                
                # Calculate locked funds using helper function
                open_orders = open_orders or []
                locked_base, locked_quote = calculate_locked_funds(open_orders)

                # Check Inventory using Shared Capital
                # If capital_tracker is provided (Batch mode), use it. Otherwise use global wallets
                cap_source = capital_tracker if capital_tracker is not None else self.wallets
                
                # Base asset balance (not shared, no lock needed)
                base_balance = self.wallets.get(base.lower(), 0) + locked_base
                
                # Quote (Iron) balance - needs atomic read+write for thread safety
                # We'll do the full allocation check under lock for Iron
                quote_balance = 0.0
                if quote == "iron" and capital_tracker is not None:
                    # Will be checked atomically below
                    async with self.capital_lock:
                        quote_balance = capital_tracker.get(quote.lower(), 0) + locked_quote
                else:
                    quote_balance = cap_source.get(quote.lower(), 0) + locked_quote
                
                # Target Value Liquidity Strategy (using config value)
                check_price = buy_price if buy_price > 0 else (sell_price if sell_price > 0 else 0)
                
                # DYNAMIC SIZING BASED ON CAPITAL
                allocated_value = TARGET_VALUE
                if quote == "iron" and quote_balance < TARGET_VALUE:
                     allocated_value = quote_balance
                
                # Min Notional Check (0.05 buffer)
                if allocated_value < 0.05:
                    allocated_value = 0
                
                if check_price > 0 and allocated_value > 0:
                    required_qty = allocated_value / check_price
                else:
                    required_qty = 0
                    
                # Cap at max quantity from config
                if required_qty > MAX_QUANTITY: 
                    required_qty = MAX_QUANTITY
    
                required_qty = float(f"{required_qty:.2f}")
    
                should_buy = (quote_balance >= (buy_price * required_qty)) and (required_qty > 0)
                
                if should_buy and quote == "iron" and capital_tracker is not None:
                    async with self.capital_lock:
                        # Re-check balance under lock using shared tracker (Available)
                        avail = capital_tracker.get(quote.lower(), 0)
                        cost = buy_price * required_qty
                        
                        # Calculate net change required from Shared Pool
                        # If Cost > Locked, we take difference from Avail.
                        # If Cost < Locked, we return difference to Avail.
                        needed_from_tracker = cost - locked_quote
                        
                        if needed_from_tracker > 0:
                            if avail >= needed_from_tracker:
                                capital_tracker[quote.lower()] = avail - needed_from_tracker
                            else:
                                # Insufficient shared funds for expansion. Attempt resize to match Max Available.
                                max_afford = locked_quote + avail
                                if max_afford > 0.10: # Min threshold
                                    # logger.info(f"{market}: Capital constrained. Resizing {cost:.2f} -> {max_afford:.2f}")
                                    cost = max_afford
                                    required_qty = float(f"{(cost / buy_price):.2f}")
                                    capital_tracker[quote.lower()] = 0.0 # Consumed all avail
                                else:
                                    should_buy = False
                                    logger.debug(f"{market}: Insufficient capital (Race).")
                        else:
                             # Return surplus to shared pool
                             capital_tracker[quote.lower()] = avail + abs(needed_from_tracker)
                
                should_sell = base_balance >= required_qty # Sell logic remains same (we sell what we have, up to limit)
                # Actually for selling, if we don't have enough for TARGET size, we should sell ALL we have?
                # Yes, if base_balance < required_qty (target), sell base_balance.
                if base_balance > 0 and base_balance < required_qty:
                     sell_qty = base_balance
                else:
                     sell_qty = required_qty
                
                sell_qty = float(f"{sell_qty:.2f}")
                should_sell = base_balance >= sell_qty and sell_qty > 0
    
                # If wallets are empty (initial fetch failed), we default to True to let API decide, 
                # unless we want to be strict. Given the error 'currency', connection might be fine but parsing bad.
                if not self.wallets:
                     should_buy = True
                     should_sell = True
    
                if not should_buy:
                    logger.debug(f"{market}: Insufficient {quote} for BUY (Have {quote_balance}, Need {buy_price * required_qty})")
                if not should_sell:
                    logger.debug(f"{market}: Insufficient {base} for SELL (Have {base_balance}, Need {required_qty})")
    
                # 3. SMART ORDER MAINTENANCE (Diffing) - using helper function
                open_orders = open_orders or []
                orders_to_cancel, buy_active, sell_active = diff_orders(
                    open_orders, buy_price, required_qty, sell_price, sell_qty, should_buy, should_sell
                )
    
                # Execute Changes (Cancel Stale)
                if orders_to_cancel:
                    cancel_tasks = []
                    for oid in orders_to_cancel:
                        if config.trading.dry_run:
                            logger.info(f"🧪 [DRY-RUN] {market}: Would cancel order {oid}")
                            self.metrics.record_order_cancelled()
                        else:
                            logger.info(f"{market}: Cancelling order {oid} (Diff Mismatch).")
                            cancel_tasks.append(self.client.cancel_order(order_id=oid))

                    if cancel_tasks:
                        results = await asyncio.gather(*cancel_tasks, return_exceptions=True)
                        for res in results:
                            if isinstance(res, Exception):
                                 if "1102" in str(res) or "Not Open" in str(res):
                                     logger.debug(f"{market}: Order already closed (benign race).")
                                 else:
                                     logger.error(f"{market}: Failed to cancel order: {res}")
                            else:
                                self.metrics.record_order_cancelled()

                # Execute Changes (Create New)
                create_tasks = []
                
                if should_buy and not buy_active and buy_price > 0:
                    if config.trading.dry_run:
                        logger.info(f"🧪 [DRY-RUN] {market}: Would place Buy {buy_price:.2f} x {required_qty}")
                        self.metrics.record_order_placed()
                        self.metrics.record_spread(market, buy_price, sell_price)
                    else:
                        create_tasks.append(
                            self.client.create_order(
                                 market=market, side="buy", type_="limit", 
                                 price=f"{buy_price:.2f}", quantity=f"{required_qty:.2f}"
                            )
                        )
                
                if should_sell and not sell_active and sell_price > 0:
                    if config.trading.dry_run:
                        logger.info(f"🧪 [DRY-RUN] {market}: Would place Sell {sell_price:.2f} x {sell_qty}")
                        self.metrics.record_order_placed()
                    else:
                        create_tasks.append(
                            self.client.create_order(
                                 market=market, side="sell", type_="limit", 
                                 price=f"{sell_price:.2f}", quantity=f"{sell_qty:.2f}"
                            )
                        )
                
                if create_tasks:
                    results = await asyncio.gather(*create_tasks, return_exceptions=True)
                    for res in results:
                         if isinstance(res, Exception):
                             if "3003" in str(res) or "Funds error" in str(res): # Check 3003 code
                                 logger.warning(f"{market}: Order failed - Insufficient funds/inventory.")
                             else:
                                 logger.error(f"{market}: Place order failed: {res}")
                         else:
                             side = res.get("side", "unknown") if isinstance(res, dict) else "unknown"
                             logger.info(f"{market}: Placed {side} order.")
                             self.metrics.record_order_placed()
                             if side == "buy":
                                 self.metrics.record_spread(market, buy_price, sell_price)


            
                # Record Snapshot of Decision
                await self.recorder.log_snapshot(market, {
                    "mid_price": mid_price,
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                    "buy_active": buy_active,
                    "sell_active": sell_active,
                    "inventory_base": base_balance,
                    "inventory_quote": quote_balance,
                    "should_buy": should_buy,
                    "should_sell": should_sell,
                    "target_qty": required_qty
                })

            except Exception as e:
                # Catch strict errors in earlier logic (calc price, wallet check)
                logger.error(f"Error preparing {market}: {e}")

    async def place_orders_parallel(self) -> None:
        """Process all markets in parallel with shared capital tracker."""
        try:
            # Update wallets once
            await self._update_wallets()
            
            # Initialize local capital tracker for this batch
            tracker = self.wallets.copy()
            
            # Pre-heat metrics cache sequentially
            supplies = {}
            try:
                supplies = await self.price_model.get_circulating_supply()
            except Exception as e:
                logger.error(f"Failed to fetch supplies: {e}")
                supplies = {} # Safer fallback

            # Fetch current market state (Tickers)
            ticker_map = {}
            try:
                response = await self.client.get_markets(get_tickers=True)
                if response.get("success"):
                    for m_data in response.get("markets", []):
                        if "ticker" in m_data:
                             ticker_map[m_data["market"]] = m_data["ticker"]
            except Exception as e:
                logger.error(f"Failed to fetch tickers batch: {e}")
            
            # Fetch Open Orders
            open_orders_map = await self._fetch_open_orders()
            
            # Asyncio gather 
            tasks = [self._process_market(m, supplies, ticker_map.get(m), open_orders_map.get(m), capital_tracker=tracker) for m in self.markets]
            await asyncio.gather(*tasks)
            
            # Poll recent trades to update P&L metrics
            await self._poll_recent_trades()
            
            # Auto-save metrics periodically
            self.metrics._maybe_auto_save()
            
        except Exception as e:
            logger.error(f"Critical error in place_orders_parallel: {e}")
            # Do NOT propagate to run(), just log and skip this cycle

    async def _snapshot_loop(self):
        """Background task to snapshot orderbooks periodically."""
        while True:
            try:
                if not self.markets:
                    await asyncio.sleep(5)
                    continue

                for market in self.markets:
                    try:
                        # Fetch full orderbook
                        ob = await self.client.get_orderbook(market)
                        if ob and ob.get("success"):
                            await self.recorder.log_orderbook(market, ob)
                    except Exception as e:
                        logger.error(f"Snapshot Orderbook Error {market}: {e}")
                    
                    # Stagger requests slightly
                    await asyncio.sleep(0.5)
                
                # Wait before next full cycle (e.g. every 30s)
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as ex:
                logger.error(f"Snapshot Loop Error: {ex}")
                await asyncio.sleep(5)

    async def run(self) -> None:
        """Main execution loop with retry and health check."""
        
        # Start Orderbook Snapshot Loop
        asyncio.create_task(self._snapshot_loop())

        # 1. Robust Startup: Retry until API is available
        while True:
            logger.info("Initializing... (Checking API availability)")
            
            # Retry fetching markets
            self.markets = await self._fetch_markets()
            if not self.markets:
                logger.warning("No markets found (or API down). Retrying in 5s...")
                self.alerts.warning("Startup Delayed", "No markets found (API may be down). Retrying...")
                await asyncio.sleep(5)
                continue
            
            # Initialize locks for the found markets
            self.market_locks = {m: asyncio.Lock() for m in self.markets}
            
            try:
                # Global cleanup on start (skip in dry-run mode)
                if config.trading.dry_run:
                    logger.warning("🧪 DRY-RUN MODE ENABLED - No real orders will be placed!")
                else:
                    logger.info("Cleaning up existing existing orders...")
                    await self.client.cancel_orders() 
                
                # Fetch initial wallets to verify auth and funds
                await self._update_wallets()
                if not self.wallets:
                     # If wallets empty, it might be an auth error or API issue, but strictly we could proceed.
                     # But for safety, let's retry if we can't see money.
                     logger.warning("Failed to fetch wallets. Retrying startup in 5s...")
                     self.alerts.warning("Startup Delayed", "Failed to fetch wallets. Retrying...")
                     await asyncio.sleep(5)
                     continue
                
                mode_str = " [DRY-RUN]" if config.trading.dry_run else ""
                logger.info(f"Startup successful.{mode_str} Active on {len(self.markets)} markets.")
                self.alerts.info("Bot Started", f"Market Maker active on {len(self.markets)} markets.{mode_str}")
                break # Exit startup loop
                
            except CircuitBreakerOpen as e:
                logger.error(f"Startup failed (Circuit Open): {e}. Waiting recovery...")
                self.alerts.error("Circuit Breaker Open", str(e))
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Startup failed (API Error): {e}. Retrying in 5s...")
                self.alerts.error("Startup Failed", f"API Error: {e}")
                await asyncio.sleep(5)

        # 2. WebSocket Setup (Already created in __init__, just connect here)
        # self.ws = BlockyWebSocket(self.ws_url, self.api_key)  # Removed: Already defined in __init__

        # WebSocket Setup
        try:
            logger.info("Connecting to WebSocket...")
            await self.ws.connect()
            
            # Unified Handler for both Transactions and Orderbook
            async def _unified_handler(data):
                await self._on_event_update(data)

            for market in self.markets:
                # Subscribe to BOTH Transactions (Fills) and Orderbook (Competitor Moves)
                await self.ws.subscribe_transactions(market, _unified_handler)
                await self.ws.subscribe_orderbook(market, _unified_handler)
            
            # Start WS loop in background
            ws_task = asyncio.create_task(self.ws.run_forever())
            logger.info("WebSocket connected and subscribed to ALL markets.")
        except Exception as e:
            logger.error(f"Failed to start WebSocket: {e}")
            ws_task = None

        # 3. Health Endpoint Setup
        health_server = None
        if config.health.enabled:
            try:
                health_server = HealthServer(self, port=config.health.port)
                await health_server.start()
            except Exception as e:
                logger.warning(f"Health endpoint failed to start: {e}")

        try:
            # Seed orders once
            logger.info("Seeding initial orders...")
            await self.place_orders_parallel()

            while True:
                # Integrity Check / Backup Loop (Every 60s)
                # Ensures we recover if WS misses an event or startup failed.
                # Smart Maintenance (Diffing) prevents flickering.
                await asyncio.sleep(60)
                logger.info("Integrity Check: Verifying orders...")
                await self.place_orders_parallel()
                
        except asyncio.CancelledError:
            logger.info("MarketMaker task cancelled.")
        except Exception as e:
             logger.error(f"An unexpected error occurred: {e}")
             raise
        finally:
            if self.ws: await self.ws.close()
            
            # Print performance summary
            self.metrics.print_summary()
            
            logger.info("Shutting down... Cancelling all orders.")
            try:
                await self.client.cancel_orders()
                logger.info("All orders cancelled successfully.")
            except Exception as e:
                logger.error(f"Error cancelling orders on exit: {e}")
            
            # Close HTTP Client (Fix unclosed session error)
            await self.client.close()

async def main() -> None:
    """Entry point for the market maker bot with dashboard."""
    from dashboard import TradingDashboard
    
    bot = MarketMaker(API_KEY, API_ENDPOINT)
    
    # Start dashboard with bot integration
    dashboard = TradingDashboard(bot=bot, port=8081)
    await dashboard.start()
    logger.info("📊 Dashboard started at http://localhost:8081/dashboard")
    
    try:
        await bot.run()
    finally:
        await dashboard.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
