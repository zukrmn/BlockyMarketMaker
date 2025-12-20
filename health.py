"""
Lightweight HTTP health endpoint for the Market Maker bot.
Provides /health endpoint for monitoring and alerting systems.
"""
import asyncio
import logging
from typing import TYPE_CHECKING

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    web = None

if TYPE_CHECKING:
    from bot import MarketMaker

logger = logging.getLogger(__name__)


class HealthServer:
    """
    Simple HTTP server exposing health status.
    
    Endpoints:
        GET /health - Returns JSON with bot status
    """
    
    def __init__(self, bot: "MarketMaker", port: int = 8080):
        """
        Initialize HealthServer.
        
        Args:
            bot: MarketMaker instance to monitor.
            port: Port to listen on (default: 8080).
        """
        self.bot = bot
        self.port = port
        self._runner = None
        
    async def health_handler(self, request):
        """Returns bot health status as JSON."""
        try:
            status = {
                "status": "healthy",
                "markets_count": len(self.bot.markets),
                "markets": self.bot.markets,
                "circuit_breaker": self.bot.client.circuit_breaker.state,
                "websocket_connected": self.bot.ws.running if self.bot.ws else False,
                "metrics_healthy": self.bot.price_model.is_healthy(),
                "realized_pnl": round(self.bot.metrics.get_realized_pnl(), 4),
                "orders_placed": self.bot.metrics.orders_placed,
                "orders_cancelled": self.bot.metrics.orders_cancelled,
                "total_trades": len(self.bot.metrics.trades),
            }
            
            # Add rate limiter stats
            if hasattr(self.bot.client, 'rate_limiter'):
                rl_stats = self.bot.client.rate_limiter.get_stats()
                status["rate_limiter"] = {
                    "total_requests": rl_stats.get("total_requests", 0),
                    "total_waits": rl_stats.get("total_waits", 0),
                }
            
            # Add circuit breaker details
            if hasattr(self.bot.client, 'circuit_breaker'):
                cb_stats = self.bot.client.circuit_breaker.get_stats()
                status["circuit_breaker_details"] = {
                    "failures": cb_stats.get("failures", 0),
                    "total_blocked": cb_stats.get("total_blocked", 0),
                }
            
            # Determine overall health
            is_healthy = (
                status["circuit_breaker"] != "OPEN" and
                status["metrics_healthy"]
            )
            
            http_status = 200 if is_healthy else 503
            status["status"] = "healthy" if is_healthy else "degraded"
            
            return web.json_response(status, status=http_status)
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=500
            )
    
    async def start(self):
        """Start the health server."""
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not installed. Health endpoint disabled. Install with: pip install aiohttp")
            return False
            
        try:
            app = web.Application()
            app.router.add_get('/health', self.health_handler)
            app.router.add_get('/', self.health_handler)  # Root also returns health
            
            self._runner = web.AppRunner(app)
            await self._runner.setup()
            
            site = web.TCPSite(self._runner, '0.0.0.0', self.port)
            await site.start()
            
            logger.info(f"🏥 Health endpoint running on http://0.0.0.0:{self.port}/health")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start health server: {e}")
            return False
    
    async def stop(self):
        """Stop the health server."""
        if self._runner:
            await self._runner.cleanup()
            logger.info("Health server stopped.")
