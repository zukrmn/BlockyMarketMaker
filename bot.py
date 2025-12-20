import asyncio
import os
import time
import logging
from typing import List, Dict
from dotenv import load_dotenv
from blocky import Blocky, BlockyWebSocket, CircuitBreakerOpen
from price_model import PriceModel
from spread_calculator import SpreadCalculator, SpreadConfig
from metrics import MetricsTracker
from alerts import AlertManager, AlertLevel
from config import get_config
from health import HealthServer

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

# Setup handler with colored output
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter(
    fmt='%(asctime)s │ %(levelname)s │ %(message)s',
    datefmt='%H:%M:%S'
))
logging.basicConfig(level=logging.INFO, handlers=[handler])
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
    def __init__(self, api_key: str, endpoint: str):
        self.client = Blocky(api_key=api_key, endpoint=endpoint)
        self.endpoint = endpoint
        self.price_model = PriceModel(
            self.client, 
            base_prices=config.price_model.base_prices
        )
        self.markets = self._fetch_markets()
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
        
        if spread_config.enabled:
            logger.info("📊 Dynamic spread calculation enabled")

    async def _on_event_update(self, data: dict):
        """Callback for real-time events (Trade or Orderbook)."""
        try:
            # Data: {'channel': 'market:transactions', ...} OR {'channel': 'market:orderbook', ...}
            channel = data.get("channel", "")
            if ":" in channel:
                market = channel.split(":")[0]
                # Log only on transaction to reduce noise, or debug for orderbook
                if "transactions" in channel:
                     logger.info(f"WS Event: Trade on {market}")
                
                # Fetch supplies cache (safe to use stale for 60s)
                # We do NOT await get_circulating_supply here if it does network call, 
                # but it uses cache logic. 
                supplies = await self._run_sync(self.price_model.get_circulating_supply)
                
                # Fetch Open Orders JUST for this market
                my_orders = []
                try:
                    # Optimized fetch for single market
                    response = await self._run_sync(
                        self.client.get_orders, 
                        statuses=["open"], 
                        markets=[market]  # Filter by market
                    )
                    if response.get("success"):
                         my_orders = response.get("orders", [])
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

    async def _run_sync(self, func, *args, **kwargs):
        """Runs a synchronous function in a thread pool."""
        loop = asyncio.get_running_loop()
        from functools import partial
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    def _fetch_markets(self) -> List[str]:
        """Fetches available markets from the API and applies config filters."""
        logger.info("Fetching available markets...")
        try:
            # this is called in __init__, so it can stay sync blocking or we need to move it to a factory/run method
            # For now it's in init, so keep sync.
            response = self.client.get_markets()
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

    async def _update_wallets(self):
        """Fetches and updates wallet balances with 100ms throttling."""
        now = time.time()
        if now - self.last_wallet_update < 0.1:  # 100ms throttle (was 1s)
            return
            
        try:
            response = await self._run_sync(self.client.get_wallets)
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
        """Fetches all open orders and maps them by market."""
        open_orders = {}
        cursor = None
        has_more = True
        
        try:
            while has_more:
                response = await self._run_sync(
                    self.client.get_orders, 
                    statuses=["open"], 
                    limit=50, # Fix: Max limit is 50
                    cursor=cursor
                )
                
                if response.get("success"):
                    orders = response.get("orders", [])
                    if not orders:
                        break
                        
                    for order in orders:
                        m = order["market"]
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

    async def _poll_recent_trades(self):
        """Polls recent trades from API and records them in metrics for P&L tracking."""
        try:
            # Fetch recent trades (limit 50, newest first)
            response = await self._run_sync(
                self.client.get_trades,
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


    async def _process_market(self, market: str, supplies: dict, ticker: dict = None, open_orders: List[dict] = None, capital_tracker: dict = None):
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
                mid_price = await self._run_sync(self.price_model.calculate_fair_price, market)
                
                
                # Fallback to ticker
                if mid_price <= 0 and ticker:
                     mid_price = float(ticker.get("close", 0) or ticker.get("last", 0) or 0)
                elif mid_price <= 0:
                     t = await self._run_sync(self.client.get_ticker, market)
                     mid_price = float(t.get("close", 0))
    
                if mid_price == 0:
                    return
    
                # Calculate Dynamic Spread
                base, quote = market.split('_')  # e.g. ston, iron
                base_inventory = self.wallets.get(base.lower(), 0)
                
                # Get asymmetric spreads based on volatility + inventory
                buy_spread, sell_spread = self.spread_calculator.get_dynamic_spread(
                    market, 
                    inventory=base_inventory,
                    ticker=ticker
                )
                
                # Calculate prices using dynamic spreads
                buy_price = round(mid_price * (1 - buy_spread / 2), 2)
                sell_price = round(mid_price * (1 + sell_spread / 2), 2)
                
                # Log dynamic spread for first few markets (debug)
                logger.debug(f"{market}: Dynamic spread buy={buy_spread:.2%} sell={sell_spread:.2%}")

                # COMPETITIVE STRATEGY (Pennying)
                # Beat best bid/ask by 0.01 if it leaves us with > 1% profit margin from Mid Price
                # Safe Limits:
                MAX_BUY = mid_price * 0.99  # Ensure 1% margin from mid
                MIN_SELL = mid_price * 1.01 # Ensure 1% margin from mid
                
                # Identify OUR current top orders to prevent self-pennying
                my_best_bid = 0.0
                my_best_ask = 0.0

                if open_orders:
                    for o in open_orders:
                        p = float(o.get("price", 0))
                        if o["side"] == "buy":
                            if p > my_best_bid: my_best_bid = p
                        elif o["side"] == "sell":
                            if my_best_ask == 0 or p < my_best_ask: my_best_ask = p

                if ticker:
                    best_bid = float(ticker.get("bid", 0) or 0)
                    best_ask = float(ticker.get("ask", 0) or 0)
                    
                    # Pennying Buy
                    # Only penny if the competitor is NOT us.
                    # If best_bid is approximately equal to our bid, assume it's us (or matched). 
                    is_our_bid = abs(best_bid - my_best_bid) < 0.001

                    if best_bid > buy_price and best_bid < MAX_BUY:
                        if not is_our_bid:
                            # Competitor: Beat them
                            buy_price = best_bid + 0.01
                        else:
                            # Us: Maintain position (Snap target to current best to avoid cancel)
                            buy_price = best_bid
                    
                    # Pennying Sell
                    is_our_ask = abs(best_ask - my_best_ask) < 0.001 and my_best_ask > 0
                    
                    if best_ask > 0 and (best_ask < sell_price or sell_price == 0) and best_ask > MIN_SELL:
                        if not is_our_ask:
                            sell_price = best_ask - 0.01
                        else:
                            sell_price = best_ask

                # Enforce minimum spread
                if buy_price >= sell_price:
                     # Logic: Try to widen by lowering Buy first.
                     buy_price -= MIN_SPREAD_TICKS
                     
                     # If we are effectively equal/inverted still (e.g. they were 0.01, 0.01 -> buy 0.00, sell 0.01. diff 0.01. OK)
                     # If they were 0.00, 0.00 -> buy -0.01.
                     if buy_price < 0:
                         buy_price = 0.00
                     
                     # Recalculate spread
                     current_spread = sell_price - buy_price
                     if current_spread < MIN_SPREAD_TICKS:
                         # Must raise sell
                         sell_price += (MIN_SPREAD_TICKS - current_spread)
                     
                     # Final sanity check: round to 2 decimals to avoid float artifacts
                     buy_price = round(buy_price, 2)
                     sell_price = round(sell_price, 2)
    
                # 2. Check Inventory (base, quote already extracted above)
                
                # Account for Locked Funds in Open Orders
                # If we have an open order, the funds are removed from "Available Balance".
                # To decide if we SHOULD have an order, we need Total Equity (Available + Locked).
                open_orders = open_orders or []
                locked_base = 0.0
                locked_quote = 0.0
                
                for o in open_orders:
                    try:
                        q = float(o.get("quantity", 0))
                        p = float(o.get("price", 0))
                        if o["side"] == "sell":
                            locked_base += q
                        elif o["side"] == "buy":
                            locked_quote += (q * p)
                    except:
                        pass

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
                
                # Atomic Iron allocation: read + decision + write under same lock
                if should_buy and quote == "iron" and capital_tracker is not None:
                    async with self.capital_lock:
                        # Re-check balance under lock (another coroutine may have consumed it)
                        current_balance = capital_tracker.get(quote.lower(), 0) + locked_quote
                        cost = buy_price * required_qty
                        if current_balance >= cost:
                            # Decrement the tracker (not including locked_quote in decrement)
                            capital_tracker[quote.lower()] = max(0, capital_tracker.get(quote.lower(), 0) - cost)
                        else:
                            should_buy = False
                            logger.debug(f"{market}: Iron allocation race detected, skipping buy.")
                
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
    
                # 3. SMART ORDER MAINTENANCE (Diffing)
                open_orders = open_orders or []
                
                # Helper to check if we resemble an order
                def is_match(order, target_price, target_qty, side):
                    if order["side"] != side: return False
                    o_price = float(order["price"])
                    o_qty = float(order["quantity"])
                    # Tolerance: Price exact (0.001), Qty strict (0.01)
                    return abs(o_price - target_price) < 0.001 and abs(o_qty - target_qty) < 0.01
    
                orders_to_cancel = []
                buy_active = False
                sell_active = False
                
                for o in open_orders:
                    # ID Key Helper
                    oid = o.get("id") or o.get("order_id")
                    
                    if not oid:
                        logger.warning(f"{market}: Order missing ID: {o}")
                        continue
    
                    if o["side"] == "buy":
                        if should_buy and is_match(o, buy_price, required_qty, "buy"):
                            buy_active = True 
                        else:
                            orders_to_cancel.append(oid)
                    elif o["side"] == "sell":
                        if should_sell and is_match(o, sell_price, sell_qty, "sell"):
                            sell_active = True
                        else:
                            orders_to_cancel.append(oid)
    
                # Execute Changes (Cancel Stale)
                for oid in orders_to_cancel:
                    if config.trading.dry_run:
                        logger.info(f"🧪 [DRY-RUN] {market}: Would cancel order {oid}")
                        self.metrics.record_order_cancelled()
                    else:
                        logger.info(f"{market}: Cancelling order {oid} (Diff Mismatch).")
                        try:
                            await self._run_sync(self.client.cancel_order, order_id=oid)
                            self.metrics.record_order_cancelled()
                        except Exception as e:
                            # 1102 or 'Not Open' means it's already done.
                            if "1102" in str(e) or "Not Open" in str(e):
                                logger.debug(f"{market}: Order {oid} already closed (benign race).")
                            else:
                                logger.error(f"{market}: Failed to cancel {oid}: {e}")
    
                # Execute Changes (Create New)
                if should_buy and not buy_active and buy_price > 0:
                    if config.trading.dry_run:
                        logger.info(f"🧪 [DRY-RUN] {market}: Would place Buy {buy_price:.2f} x {required_qty}")
                        self.metrics.record_order_placed()
                        self.metrics.record_spread(market, buy_price, sell_price)
                    else:
                        try:
                            await self._run_sync(
                                self.client.create_order,
                                market=market, side="buy", type_="limit", 
                                price=f"{buy_price:.2f}", quantity=f"{required_qty:.2f}"
                            )
                            logger.info(f"{market}: Placed Buy {buy_price:.2f} x {required_qty}")
                            self.metrics.record_order_placed()
                            self.metrics.record_spread(market, buy_price, sell_price)
                        except Exception as e:
                            if "3003" in str(e) or "Funds error" in str(e):
                                logger.warning(f"{market}: Buy failed - Insufficient funds.")
                            else:
                                logger.error(f"{market}: Buy failed: {e}")
                
                if should_sell and not sell_active and sell_price > 0:
                    if config.trading.dry_run:
                        logger.info(f"🧪 [DRY-RUN] {market}: Would place Sell {sell_price:.2f} x {sell_qty}")
                        self.metrics.record_order_placed()
                    else:
                        try:
                            await self._run_sync(
                                self.client.create_order,
                                market=market, side="sell", type_="limit", 
                                price=f"{sell_price:.2f}", quantity=f"{sell_qty:.2f}"
                            )
                            logger.info(f"{market}: Placed Sell {sell_price:.2f} x {sell_qty}")
                            self.metrics.record_order_placed()
                        except Exception as e:
                            if "3003" in str(e) or "Funds error" in str(e):
                                logger.warning(f"{market}: Sell failed - Insufficient inventory/funds.")
                            else:
                                logger.error(f"{market}: Sell failed: {e}")
    
            except Exception as e:
                # Catch strict errors in earlier logic (calc price, wallet check)
                logger.error(f"Error preparing {market}: {e}")

    async def place_orders_parallel(self):
        try:
            # Update wallets once
            await self._update_wallets()
            
            # Initialize local capital tracker for this batch
            tracker = self.wallets.copy()
            
            # Pre-heat metrics cache sequentially
            supplies = {}
            try:
                supplies = await self._run_sync(self.price_model.get_circulating_supply)
            except Exception as e:
                logger.error(f"Failed to fetch supplies: {e}")
                supplies = {} # Safer fallback

            # Fetch current market state (Tickers)
            ticker_map = {}
            try:
                response = await self._run_sync(self.client.get_markets, get_tickers=True)
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

    async def run(self):
        """Main execution loop."""
        
        # 1. Robust Startup: Retry until API is available
        while True:
            logger.info("Initializing... (Checking API availability)")
            
            # Retry fetching markets
            self.markets = self._fetch_markets()
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
                    logger.info("Cleaning up existing orders...")
                    await self._run_sync(self.client.cancel_orders) 
                
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
                await self._run_sync(self.client.cancel_orders)
                logger.info("All orders cancelled successfully.")
            except Exception as e:
                logger.error(f"Error cancelling orders on exit: {e}")

async def main():
    bot = MarketMaker(API_KEY, API_ENDPOINT)
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
