"""
Prometheus metrics endpoint for the Market Maker bot.
Exposes trading metrics in Prometheus format at /metrics.
"""
import logging
from typing import TYPE_CHECKING, Optional
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from aiohttp import web

if TYPE_CHECKING:
    from main import MarketMaker

logger = logging.getLogger(__name__)

# Define Prometheus metrics
# Counters - monotonically increasing values
ORDERS_PLACED = Counter(
    'blocky_mm_orders_placed_total',
    'Total number of orders placed',
    ['market', 'side']
)

ORDERS_CANCELLED = Counter(
    'blocky_mm_orders_cancelled_total', 
    'Total number of orders cancelled',
    ['market']
)

TRADES_EXECUTED = Counter(
    'blocky_mm_trades_executed_total',
    'Total number of trades executed',
    ['market', 'side']
)

API_REQUESTS = Counter(
    'blocky_mm_api_requests_total',
    'Total API requests made',
    ['endpoint', 'status']
)

# Gauges - current values that can go up and down
PNL_REALIZED = Gauge(
    'blocky_mm_pnl_realized',
    'Realized profit/loss in Iron'
)

PNL_UNREALIZED = Gauge(
    'blocky_mm_pnl_unrealized',
    'Unrealized profit/loss in Iron'
)

INVENTORY = Gauge(
    'blocky_mm_inventory',
    'Current inventory per asset',
    ['asset']
)

SPREAD = Gauge(
    'blocky_mm_spread_current',
    'Current spread percentage',
    ['market', 'side']
)

CIRCUIT_BREAKER_STATE = Gauge(
    'blocky_mm_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=half-open, 2=open)'
)

WEBSOCKET_CONNECTED = Gauge(
    'blocky_mm_websocket_connected',
    'WebSocket connection status (1=connected, 0=disconnected)'
)

MARKETS_ACTIVE = Gauge(
    'blocky_mm_markets_active',
    'Number of actively traded markets'
)

# Histograms - distribution of values
ORDER_LATENCY = Histogram(
    'blocky_mm_order_latency_seconds',
    'Order execution latency',
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)


class PrometheusMetrics:
    """Prometheus metrics collector and endpoint handler."""
    
    def __init__(self, bot: Optional['MarketMaker'] = None, port: int = 9090):
        """
        Initialize Prometheus metrics.
        
        Args:
            bot: MarketMaker instance for collecting live metrics
            port: Port to serve /metrics endpoint
        """
        self.bot = bot
        self.port = port
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
    
    async def start(self) -> None:
        """Start the Prometheus metrics HTTP server."""
        self.app = web.Application()
        self.app.router.add_get('/metrics', self._metrics_handler)
        
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await site.start()
        
        logger.info(f"📊 Prometheus metrics available at http://0.0.0.0:{self.port}/metrics")
    
    async def stop(self) -> None:
        """Stop the Prometheus metrics server."""
        if self.runner:
            await self.runner.cleanup()
    
    async def _metrics_handler(self, request: web.Request) -> web.Response:
        """Handle /metrics endpoint request."""
        # Update gauges from bot state before generating output
        self._update_gauges()
        
        return web.Response(
            body=generate_latest(),
            content_type=CONTENT_TYPE_LATEST
        )
    
    def _update_gauges(self) -> None:
        """Update gauge metrics from bot state."""
        if not self.bot:
            return
        
        try:
            # P&L metrics
            if hasattr(self.bot, 'metrics'):
                metrics = self.bot.metrics
                PNL_REALIZED.set(metrics.realized_pnl)
                PNL_UNREALIZED.set(metrics.get_unrealized_pnl())
            
            # Market count
            if hasattr(self.bot, 'markets'):
                MARKETS_ACTIVE.set(len(self.bot.markets))
            
            # Inventory
            if hasattr(self.bot, 'wallets'):
                for asset, balance in self.bot.wallets.items():
                    INVENTORY.labels(asset=asset).set(balance)
            
            # WebSocket state
            if hasattr(self.bot, 'ws') and self.bot.ws:
                connected = 1 if self.bot.ws.connected else 0
                WEBSOCKET_CONNECTED.set(connected)
            
            # Circuit breaker state
            if hasattr(self.bot, 'client') and hasattr(self.bot.client, 'circuit_breaker'):
                state = self.bot.client.circuit_breaker.state.value
                CIRCUIT_BREAKER_STATE.set(state)
                
        except Exception as e:
            logger.debug(f"Error updating Prometheus gauges: {e}")


# Convenience functions to record metrics from anywhere
def record_order_placed(market: str, side: str) -> None:
    """Record an order placement."""
    ORDERS_PLACED.labels(market=market, side=side).inc()


def record_order_cancelled(market: str) -> None:
    """Record an order cancellation."""
    ORDERS_CANCELLED.labels(market=market).inc()


def record_trade(market: str, side: str) -> None:
    """Record a trade execution."""
    TRADES_EXECUTED.labels(market=market, side=side).inc()


def record_spread(market: str, buy_spread: float, sell_spread: float) -> None:
    """Record current spreads."""
    SPREAD.labels(market=market, side='buy').set(buy_spread)
    SPREAD.labels(market=market, side='sell').set(sell_spread)


def record_api_request(endpoint: str, status: str) -> None:
    """Record an API request."""
    API_REQUESTS.labels(endpoint=endpoint, status=status).inc()
