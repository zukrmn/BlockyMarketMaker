"""
ACMaker Dashboard - Trading Dashboard Server
Modular server implementation with template rendering
"""
import logging
import os
import sys
import time
import json
import random
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from aiohttp import web, ClientSession, WSMsgType
import aiohttp_jinja2
import jinja2

if TYPE_CHECKING:
    from main import MarketMaker

from .candles import CandleCollector, get_collector

logger = logging.getLogger(__name__)

# API endpoint for OHLCV data
API_BASE_URL = "https://craft.blocky.com.br/api/v1"

# Get paths - handle PyInstaller frozen mode
def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe - use _MEIPASS for bundled files
        base = sys._MEIPASS
    else:
        # Running as script
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)

# For PyInstaller, resources are at _MEIPASS/src/dashboard/...
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.join(sys._MEIPASS, 'src', 'dashboard')
    PROJECT_ROOT = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))

TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
IMG_DIR = os.path.join(PROJECT_ROOT, 'img')


class TradingDashboard:
    """Full-featured trading dashboard with charts and real-time data."""
    
    STRATEGY_COLORS = {
        "scarcity": "#ff00ff",
        "ticker": "#00ff00",
        "vwap": "#00aaff",
        "composite": "#ffaa00",
    }
    
    def __init__(self, bot: Optional['MarketMaker'] = None, port: int = 8081):
        self.bot = bot
        self.port = port
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.selected_market = "diam_iron"
        self.candle_collector = get_collector()
        self.ws_clients: set = set()  # Connected WebSocket clients for real-time updates
    
    async def start(self) -> None:
        """Start the dashboard HTTP server."""
        self.app = web.Application()
        
        # Setup Jinja2 templates
        aiohttp_jinja2.setup(
            self.app,
            loader=jinja2.FileSystemLoader(TEMPLATES_DIR)
        )
        
        # Routes
        self.app.router.add_get('/', self._redirect)
        self.app.router.add_get('/dashboard', self._dashboard_handler)
        self.app.router.add_get('/dashboard/{market}', self._dashboard_handler)
        self.app.router.add_get('/api/stats', self._api_stats)
        self.app.router.add_get('/api/candles/{market}', self._api_candles)
        self.app.router.add_get('/api/strategy/{market}', self._api_strategy_lines)
        self.app.router.add_get('/ws', self._websocket_handler)  # WebSocket for real-time updates
        
        # Static files
        self.app.router.add_static('/static', STATIC_DIR)
        if os.path.exists(IMG_DIR):
            self.app.router.add_static('/img', IMG_DIR)
        
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"📊 Trading Dashboard at http://0.0.0.0:{self.port}/dashboard")
    
    async def stop(self) -> None:
        """Stop the dashboard server."""
        if self.runner:
            await self.runner.cleanup()
    
    async def _redirect(self, request: web.Request) -> web.Response:
        """Redirect root to dashboard."""
        raise web.HTTPFound('/dashboard')
    
    def _get_stats(self) -> dict:
        """Get current stats from bot."""
        stats = {
            "status": "RUNNING",
            "realized_pnl": 0.0,
            "total_trades": 0,
            "orders_placed": 0,
            "market_count": 0,
            "markets": {},
        }
        
        if not self.bot:
            return stats
        
        try:
            if hasattr(self.bot, 'metrics'):
                m = self.bot.metrics
                stats["realized_pnl"] = m.get_realized_pnl() if hasattr(m, 'get_realized_pnl') else 0
                stats["total_trades"] = len(m.trades) if hasattr(m, 'trades') else 0
                stats["orders_placed"] = m.orders_placed if hasattr(m, 'orders_placed') else 0
                
                if hasattr(m, 'market_stats'):
                    stats["markets"] = dict(m.market_stats)
                    stats["market_count"] = len(stats["markets"])
        except Exception as e:
            logger.debug(f"Dashboard stats error: {e}")
            stats["status"] = "ERROR"
        
        return stats
    
    async def _fetch_candles_from_api(self, market: str, timeframe: str = "4H", count: int = 100) -> List[dict]:
        """
        Fetch real candle data directly from BlockyCRAFT API.
        Makes HTTP request directly using aiohttp.
        
        API returns format with separate arrays:
        {
            "success": true,
            "timestamp": ["1701864000000000000", ...],
            "open": ["50.00000000", ...],
            "high": ["50.50000000", ...],
            "low": ["49.75000000", ...],
            "close": ["50.25000000", ...]
        }
        """
        # Map timeframe string to nanoseconds (matching BlockyCRAFT interface)
        tf_map = {
            # Minutes
            "1m": 60000000000,
            "3m": 180000000000,
            "5m": 300000000000,
            "30m": 1800000000000,
            # Hours
            "2H": 7200000000000,
            "6H": 21600000000000,
            "8H": 28800000000000,
            "12H": 43200000000000,
            # Days/Weeks/Months
            "1D": 86400000000000,
            "3D": 259200000000000,
            "1W": 604800000000000,
            "1M": 2592000000000000  # ~30 days
        }
        
        tf_ns = tf_map.get(timeframe, 3600000000000)  # Default to 1H
        market_symbol = market.replace('-', '_')
        url = f"{API_BASE_URL}/markets/{market_symbol}/ohlcv?timeframe={tf_ns}"
        
        print(f"DEBUG: Fetching candles from: {url}")
        logger.info(f"Fetching candles from: {url}")
        
        try:
            async with ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        print(f"DEBUG: Status {response.status}")
                        logger.error(f"OHLCV API Error: Status {response.status} for {url}")
                        text = await response.text()
                        logger.error(f"API Response: {text[:200]}")
                        return []
                    
                    # API returns text/plain, so we must disable content type check
                    data = await response.json(content_type=None)
                    
                    if not data:
                        print("DEBUG: Empty data")
                        logger.error("API returned empty data")
                        return []
                        
                    if not data.get("success"):
                        logger.error(f"API returned success=False: {data}")
                        return []
                        
                    # Transform from separate arrays to Lightweight Charts format
                    timestamps = data.get("timestamp", [])
                    if not timestamps:
                        logger.warning(f"No timestamps in response for {market_symbol}")
                        return []
                        
                    opens = data.get("open", [])
                    highs = data.get("high", [])
                    lows = data.get("low", [])
                    closes = data.get("close", [])
                    
                    if opens:
                        logger.info(f"Raw Opens (Last 5): {opens[-5:]}")
                    
                    candles = []
                    num_candles = len(timestamps)
                    
                    # Return ALL candles from API (no limit)
                    for i in range(num_candles):
                        candles.append({
                            "time": int(timestamps[i]) // 1000000000,  # ns to seconds
                            "open": float(opens[i]) if i < len(opens) else 0,
                            "high": float(highs[i]) if i < len(highs) else 0,
                            "low": float(lows[i]) if i < len(lows) else 0,
                            "close": float(closes[i]) if i < len(closes) else 0
                        })
                    
                    logger.info(f"Successfully fetched {len(candles)} candles for {market_symbol}")
                    if candles:
                        logger.info(f"First candle: {candles[0]}")
                        logger.info(f"Last candle: {candles[-1]}")
                    return candles
                        
        except Exception as e:
            logger.exception(f"Exception fetching candles from API: {e}")
        
        return []

    async def _fetch_orderbook(self, market: str) -> dict:
        """Fetch real orderbook from API."""
        market_symbol = market.replace('-', '_')
        url = f"{API_BASE_URL}/markets/{market_symbol}/orderbook"
        
        try:
            async with ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        # API returns text/plain, disable validation
                        data = await response.json(content_type=None)
                        if data.get("success", False):
                            return data.get("orderbook", {})
                    else:
                        logger.error(f"Error fetching orderbook: {response.status}")
        except Exception as e:
            logger.error(f"Exception fetching orderbook: {e}")
        
        return {}
    
    def _get_candles(self, market: str, timeframe: str = "4H", count: int = 50) -> List[dict]:
        """
        Get candle data for a market.
        Priority: 1) Collector, 2) Mock data
        Note: For real API data, use _fetch_candles_from_api (async)
        """
        # Try to get real data from collector first
        real_candles = self.candle_collector.get_candles(market, timeframe, count)
        if real_candles:
            return real_candles
        
        # Fallback to mock data for demo
        return self._generate_mock_candles(market, timeframe, count)
    
    def _generate_mock_candles(self, market: str, timeframe: str = "4H", count: int = 50) -> List[dict]:
        """Generate mock candle data for demo."""
        base_prices = {
            "diam_iron": 50, "gold_iron": 5, "coal_iron": 0.5, 
            "lapi_iron": 2, "ston_iron": 0.1
        }
        intervals = {
            "1m": 60, "5m": 300, "15m": 900, "1H": 3600,
            "4H": 14400, "1D": 86400, "1W": 604800
        }
        interval = intervals.get(timeframe, 14400)
        base = base_prices.get(market, 10)
        now = int(time.time())
        candles = []
        price = base
        
        for i in range(count):
            t = now - (count - i) * interval
            change = random.uniform(-0.03, 0.03)
            o = price
            c = price * (1 + change)
            h = max(o, c) * (1 + random.uniform(0, 0.02))
            l = min(o, c) * (1 - random.uniform(0, 0.02))
            candles.append({
                "time": t, 
                "open": round(o, 4), 
                "high": round(h, 4), 
                "low": round(l, 4), 
                "close": round(c, 4)
            })
            price = c
        
        return candles
    
    def _render_market_list(self, markets: dict, selected: str) -> str:
        """Render market list HTML."""
        html = ""
        for market, data in markets.items():
            active = "active" if market == selected else ""
            price = data.get("mid_price", 0)
            change = data.get("change", 0.0)
            change_class = "up" if change >= 0 else "down"
            display_name = market.upper().replace('_', ' / ')
            html += f'''
            <div class="market-item {active}" data-market="{market}" onclick="location.href='/dashboard/{market}'">
                <div>
                    <div class="market-name">{display_name}</div>
                </div>
                <div style="text-align:right">
                    <div class="market-price">{price:.4f}</div>
                    <div class="market-change {change_class}">{change:+.1f}%</div>
                </div>
            </div>'''
        return html
    
    def _render_strategy_cards(self, market: str) -> str:
        """Render strategy cards HTML with real confidence and prices."""
        # Defaults
        active_strat = "composite"
        strat_data = {}
        
        # Try to get from metrics
        if self.bot and hasattr(self.bot, 'metrics'):
             stats = self.bot.metrics.market_stats[market]
             strat_data = stats.get('strategy_prices', {})
             
        # Fallback if empty (should not happen after first tick)
        if not strat_data:
             return '<div class="strategy-card" data-i18n="waiting_data">Waiting for data...</div>'

        # Sort order
        strategies = ["scarcity", "ticker", "vwap", "composite"]
        html = ""
        
        for s in strategies:
            data = strat_data.get(s, {})
            price = data.get('price', 0)
            conf = data.get('confidence', 0)
            is_active = "active" if data.get('active') else ""
            
            html += f'''
            <div class="strategy-card {is_active}" onclick="showStrategyInfo('{s}')" style="cursor: pointer;">
                <div class="strategy-name" data-i18n="{s}_title">{s.upper()}</div>
                <div class="strategy-price">{price:.4f}</div>
                <div class="strategy-confidence"><span data-i18n="confidence">Confidence</span>: {conf}%</div>
            </div>'''
        
        return html
    
    def _render_orderbook(self, ob_data: dict) -> str:
        """Render order book HTML from real API data.
        
        Blocky API Format:
        {
            "asks": {"price": ["50.70"], "quantity": ["0.10"], ...},
            "bids": {"price": ["49.20"], "quantity": ["0.10"], ...},
            "spread": "1.50",
            "spread_percentage": "3.04"
        }
        """
        html = ""
        
        asks_raw = ob_data.get('asks', {})
        bids_raw = ob_data.get('bids', {})
        
        # Parse asks - Blocky uses parallel arrays: {price: [...], quantity: [...]}
        asks = []
        if isinstance(asks_raw, dict):
            prices = asks_raw.get('price', [])
            quantities = asks_raw.get('quantity', [])
            # Zip the parallel arrays together
            for i, price in enumerate(prices):
                qty = quantities[i] if i < len(quantities) else 0
                try:
                    asks.append({'price': float(price), 'amount': float(qty)})
                except (ValueError, TypeError):
                    continue
        elif isinstance(asks_raw, list):
            # Alternative format: list of objects
            asks = [{'price': float(x.get('price', 0)), 'amount': float(x.get('amount', 0) or x.get('quantity', 0))} for x in asks_raw]
        
        # Parse bids - same parallel array format
        bids = []
        if isinstance(bids_raw, dict):
            prices = bids_raw.get('price', [])
            quantities = bids_raw.get('quantity', [])
            for i, price in enumerate(prices):
                qty = quantities[i] if i < len(quantities) else 0
                try:
                    bids.append({'price': float(price), 'amount': float(qty)})
                except (ValueError, TypeError):
                    continue
        elif isinstance(bids_raw, list):
            bids = [{'price': float(x.get('price', 0)), 'amount': float(x.get('amount', 0) or x.get('quantity', 0))} for x in bids_raw]
        
        # Sort: Asks ascending (lowest first), Bids descending (highest first)
        asks.sort(key=lambda x: x['price'])
        bids.sort(key=lambda x: x['price'], reverse=True)
        
        # Take top 5
        asks = asks[:5]
        bids = bids[:5]
        
        # Render asks (reversed so highest ask is at top, lowest near spread)
        for ask in reversed(asks):
            html += f'<div class="ob-row ask"><span>{ask["price"]:.4f}</span><span>{ask["amount"]:.2f}</span></div>'
        
        # Spread
        best_ask = asks[0]['price'] if asks else 0
        best_bid = bids[0]['price'] if bids else 0
        
        if best_ask > 0 and best_bid > 0:
            spread_pct = (best_ask - best_bid) / best_ask * 100
            html += f'<div class="ob-row spread">Spread: {spread_pct:.2f}%</div>'
        else:
            html += '<div class="ob-row spread">Spread: -</div>'
            
        for bid in bids:
            html += f'<div class="ob-row bid"><span>{bid["price"]:.4f}</span><span>{bid["amount"]:.2f}</span></div>'
        
        if not asks and not bids:
            html = '<div style="padding:10px;color:#666">No orderbook data available...</div>'
        
        return html
    
    def _render_trade_log(self, market: str) -> str:
        """Render trade log HTML from real metrics buffer."""
        html = ""
        trades = []
        
        if self.bot and hasattr(self.bot, 'metrics'):
             # deque to list
             trades = list(self.bot.metrics.market_stats[market]['recent_trades'])
        
        # Limit to 10 for display
        for t in trades[:15]:
            # t is dict: {time_str, side, price, quantity, ...}
            side_class = "trade-buy" if t['side'] == "BUY" else "trade-sell"
            html += f'''<div class="trade-row">
                <span>{t['time_str']}</span>
                <span class="{side_class}">{t['side']}</span>
                <span>{t['price']:.4f}</span>
                <span>{t['quantity']:.2f}</span>
            </div>'''
            
        if not trades:
            html = '<div style="padding:10px;color:#666" data-i18n="no_trades_yet">No trades yet...</div>'
            
        return html
    
    @aiohttp_jinja2.template('dashboard.html')
    async def _dashboard_handler(self, request: web.Request) -> dict:
        """Handle dashboard page request."""
        market = request.match_info.get('market', self.selected_market)
        stats = self._get_stats()
        markets = stats.get("markets", {})
        
        if market not in markets and markets:
            market = list(markets.keys())[0]
        
        market_data = markets.get(market, {
            "mid_price": 50, 
            "strategy": "composite", 
            "spread": 0.03
        })
        mid = market_data.get("mid_price", 50)
        spread = market_data.get("spread", 0.03)
        
        pnl = stats["realized_pnl"]
        
        # Try to get real candles from API first (5m = default timeframe)
        candles = await self._fetch_candles_from_api(market, "5m")
        
        # Try to get real orderbook
        orderbook_data = await self._fetch_orderbook(market)
        
        # Fallback to local data if API fails
        if not candles:
            candles = self._get_candles(market)
        
        # Strategy Lines for Chart (Approximate from metrics)
        metrics_stats = {}
        if self.bot and hasattr(self.bot, 'metrics'):
             metrics_stats = self.bot.metrics.market_stats[market]
        
        strat_prices = metrics_stats.get('strategy_prices', {})
        strategy_lines = []
        if strat_prices:
            for s, d in strat_prices.items():
                # Plot ALL strategies (removed filter that skipped active)
                color = self.STRATEGY_COLORS.get(s, "#ffffff")
                strategy_lines.append({"name": s.upper(), "price": d.get('price', 0), "color": color})
        else:
             # Fallback visual - All 4 strategies based on mid price
             strategy_lines = [
                {"name": "SCARCITY", "price": mid * 1.02, "color": self.STRATEGY_COLORS["scarcity"]},
                {"name": "TICKER", "price": mid, "color": self.STRATEGY_COLORS["ticker"]},
                {"name": "VWAP", "price": mid * 0.99, "color": self.STRATEGY_COLORS["vwap"]},
                {"name": "COMPOSITE", "price": mid, "color": self.STRATEGY_COLORS["composite"]},
             ]

        return {
            "status": "RUNNING",
            "pnl_class": "pos" if pnl >= 0 else "neg",
            "realized_pnl": f"{pnl:+.2f}",
            "total_trades": stats["total_trades"],
            "orders_placed": stats["orders_placed"],
            "market_count": stats["market_count"],
            "market_list": self._render_market_list(markets, market),
            "selected_market_display": market.upper().replace('_', ' / '),
            "strategy_cards": self._render_strategy_cards(market),
            "orderbook": self._render_orderbook(orderbook_data) if orderbook_data else self._render_orderbook({'asks':[], 'bids':[]}),
            "candle_data": json.dumps(candles),
            "strategy_lines": json.dumps(strategy_lines),
            "bid_price": round(mid * (1 - spread / 2), 4),
            "ask_price": round(mid * (1 + spread / 2), 4),
            "buy_order": f"{mid * (1 - spread / 2):.2f} x 10",
            "sell_order": f"{mid * (1 + spread / 2):.2f} x 10",
            "spread": f"{spread * 100:.2f}%",
            "position": "0",
            "trade_log": self._render_trade_log(market),
            "timestamp": time.strftime("%H:%M:%S"),
        }
    
    async def _api_stats(self, request: web.Request) -> web.Response:
        """API endpoint for stats."""
        return web.json_response(self._get_stats())
    
    async def _api_candles(self, request: web.Request) -> web.Response:
        """API endpoint for candle data."""
        market = request.match_info.get('market', 'diam_iron')
        timeframe = request.query.get('tf', '5m')
        
        # Get real data from API only (no mock fallback!)
        candles = await self._fetch_candles_from_api(market, timeframe)
        
        # Return empty array if no data - no mock data!
        if not candles:
            candles = []
        
        return web.json_response(candles)
    
    async def _api_strategy_lines(self, request: web.Request) -> web.Response:
        """API endpoint for strategy lines data."""
        market = request.match_info.get('market', 'diam_iron')
        
        # Get strategy data from bot metrics
        strategy_lines = []
        mid = 50.0  # Default
        
        if self.bot and hasattr(self.bot, 'metrics'):
            metrics_stats = self.bot.metrics.market_stats.get(market, {})
            mid = metrics_stats.get('mid_price', 50.0)
            strat_prices = metrics_stats.get('strategy_prices', {})
            
            if strat_prices:
                for s, d in strat_prices.items():
                    color = self.STRATEGY_COLORS.get(s, "#ffffff")
                    strategy_lines.append({
                        "name": s.upper(), 
                        "price": d.get('price', 0), 
                        "color": color
                    })
        
        # Fallback if no data
        if not strategy_lines:
            strategy_lines = [
                {"name": "SCARCITY", "price": mid * 1.02, "color": self.STRATEGY_COLORS["scarcity"]},
                {"name": "TICKER", "price": mid, "color": self.STRATEGY_COLORS["ticker"]},
                {"name": "VWAP", "price": mid * 0.99, "color": self.STRATEGY_COLORS["vwap"]},
                {"name": "COMPOSITE", "price": mid, "color": self.STRATEGY_COLORS["composite"]},
            ]
        
        return web.json_response({
            "market": market,
            "mid_price": mid,
            "strategy_lines": strategy_lines
        })
    
    # === WebSocket for Real-Time Updates ===
    
    async def _websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connections for real-time dashboard updates."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        # Add to connected clients
        self.ws_clients.add(ws)
        logger.info(f"📡 WebSocket client connected ({len(self.ws_clients)} total)")
        
        try:
            # Send initial stats on connect (JSON-safe simplified version)
            simple_stats = {
                'realized_pnl': 0.0,
                'total_trades': 0,
                'orders_placed': 0,
                'market_count': 0
            }
            if self.bot and hasattr(self.bot, 'metrics'):
                simple_stats = {
                    'realized_pnl': self.bot.metrics.get_realized_pnl(),
                    'total_trades': len(self.bot.metrics.trades),
                    'orders_placed': self.bot.metrics.orders_placed,
                    'market_count': len(self.bot.config.markets) if hasattr(self.bot, 'config') else 0
                }
            await ws.send_json({
                'type': 'stats_update',
                'data': simple_stats
            })
            
            # Keep connection open and listen for messages
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # Client can send heartbeat or request updates
                    if msg.data == 'ping':
                        await ws.send_str('pong')
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')
        finally:
            self.ws_clients.discard(ws)
            logger.info(f"📡 WebSocket client disconnected ({len(self.ws_clients)} remaining)")
        
        return ws
    
    async def broadcast_event(self, event_type: str, data: dict):
        """Broadcast an event to all connected WebSocket clients."""
        if not self.ws_clients:
            return
        
        message = json.dumps({'type': event_type, 'data': data})
        
        # Send to all connected clients
        disconnected = set()
        for ws in self.ws_clients:
            try:
                await ws.send_str(message)
            except Exception:
                disconnected.add(ws)
        
        # Clean up disconnected clients
        self.ws_clients -= disconnected


# Backward compatibility aliases
DashboardServer = TradingDashboard
AdvancedDashboard = TradingDashboard
