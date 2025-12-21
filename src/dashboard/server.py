"""
ACMaker Dashboard - Trading Dashboard Server
Modular server implementation with template rendering
"""
import logging
import os
import time
import json
import random
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from aiohttp import web
import aiohttp_jinja2
import jinja2

if TYPE_CHECKING:
    from main import MarketMaker

logger = logging.getLogger(__name__)

# Get paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
IMG_DIR = os.path.join(os.path.dirname(BASE_DIR), 'img')


class TradingDashboard:
    """Full-featured trading dashboard with charts and real-time data."""
    
    STRATEGY_COLORS = {
        "scarcity": "#ff00ff",
        "ticker": "#00aaff", 
        "vwap": "#00ff00",
        "composite": "#ffaa00",
    }
    
    def __init__(self, bot: Optional['MarketMaker'] = None, port: int = 8081):
        self.bot = bot
        self.port = port
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.selected_market = "diam_iron"
    
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
    
    def _generate_candles(self, market: str, count: int = 50) -> List[dict]:
        """Generate mock candle data for demo."""
        base_prices = {
            "diam_iron": 50, "gold_iron": 5, "coal_iron": 0.5, 
            "lapi_iron": 2, "ston_iron": 0.1
        }
        base = base_prices.get(market, 10)
        now = int(time.time())
        candles = []
        price = base
        
        for i in range(count):
            t = now - (count - i) * 3600
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
            change = data.get("change", 1.5)
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
    
    def _render_strategy_cards(self, market_data: dict) -> str:
        """Render strategy cards HTML."""
        strategies = ["scarcity", "ticker", "vwap", "composite"]
        active = market_data.get("strategy", "composite")
        mid = market_data.get("mid_price", 10)
        html = ""
        
        price_mults = {"scarcity": 1.15, "ticker": 1.0, "vwap": 0.98, "composite": 1.02}
        confidences = {"scarcity": 85, "ticker": 92, "vwap": 78, "composite": 88}
        
        for s in strategies:
            is_active = "active" if s == active else ""
            price = mid * price_mults[s]
            conf = confidences[s]
            html += f'''
            <div class="strategy-card {is_active}">
                <div class="strategy-name">{s}</div>
                <div class="strategy-price">{price:.4f}</div>
                <div class="strategy-confidence">Confiança: {conf}%</div>
            </div>'''
        
        return html
    
    def _render_orderbook(self, mid: float) -> str:
        """Render order book HTML."""
        asks = [mid * (1 + i * 0.005) for i in range(5, 0, -1)]
        bids = [mid * (1 - i * 0.005) for i in range(1, 6)]
        html = ""
        
        for a in asks:
            html += f'<div class="ob-row ask"><span>{a:.4f}</span><span>{int(50 + a * 2)}</span></div>'
        
        spread_pct = (asks[-1] - bids[0]) / mid * 100
        html += f'<div class="ob-row spread">Spread: {spread_pct:.2f}%</div>'
        
        for b in bids:
            html += f'<div class="ob-row bid"><span>{b:.4f}</span><span>{int(50 + b * 2)}</span></div>'
        
        return html
    
    def _render_trade_log(self) -> str:
        """Render trade log HTML."""
        trades = [
            ("10:15:32", "BUY", 49.50, 10),
            ("10:14:28", "SELL", 50.20, 10),
            ("10:12:45", "BUY", 49.80, 10),
            ("10:10:12", "SELL", 50.10, 10),
            ("10:08:33", "BUY", 49.60, 10),
        ]
        html = ""
        for t in trades:
            side_class = "trade-buy" if t[1] == "BUY" else "trade-sell"
            html += f'''<div class="trade-row">
                <span>{t[0]}</span>
                <span class="{side_class}">{t[1]}</span>
                <span>{t[2]:.2f}</span>
                <span>{t[3]}</span>
            </div>'''
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
        candles = self._generate_candles(market)
        
        strategy_lines = [
            {"name": "Scarcity", "price": mid * 1.15, "color": self.STRATEGY_COLORS["scarcity"]},
            {"name": "VWAP", "price": mid * 0.98, "color": self.STRATEGY_COLORS["vwap"]},
            {"name": "Ticker", "price": mid, "color": self.STRATEGY_COLORS["ticker"]},
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
            "strategy_cards": self._render_strategy_cards(market_data),
            "orderbook": self._render_orderbook(mid),
            "candle_data": json.dumps(candles),
            "strategy_lines": json.dumps(strategy_lines),
            "bid_price": round(mid * (1 - spread / 2), 4),
            "ask_price": round(mid * (1 + spread / 2), 4),
            "buy_order": f"{mid * (1 - spread / 2):.2f} x 10",
            "sell_order": f"{mid * (1 + spread / 2):.2f} x 10",
            "spread": f"{spread * 100:.2f}%",
            "position": "0",
            "trade_log": self._render_trade_log(),
            "timestamp": time.strftime("%H:%M:%S"),
        }
    
    async def _api_stats(self, request: web.Request) -> web.Response:
        """API endpoint for stats."""
        return web.json_response(self._get_stats())
    
    async def _api_candles(self, request: web.Request) -> web.Response:
        """API endpoint for candle data."""
        market = request.match_info.get('market', 'diam_iron')
        return web.json_response(self._generate_candles(market))


# Backward compatibility aliases
DashboardServer = TradingDashboard
AdvancedDashboard = TradingDashboard
