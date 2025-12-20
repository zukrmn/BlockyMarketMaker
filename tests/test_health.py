"""
Unit tests for the health endpoint.
Tests HealthServer functionality without requiring a running bot.
"""
import asyncio
import unittest
from unittest.mock import MagicMock, patch, PropertyMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestHealthServerUnit(unittest.TestCase):
    """Unit tests for HealthServer without HTTP calls."""
    
    def test_health_server_initialization(self):
        """Test HealthServer can be initialized with a mock bot."""
        from health import HealthServer
        
        mock_bot = MagicMock()
        mock_bot.markets = ["diam_iron", "gold_iron"]
        
        server = HealthServer(mock_bot, port=8080)
        
        self.assertEqual(server.port, 8080)
        self.assertEqual(server.bot, mock_bot)
        
        print("✓ HealthServer initializes correctly")
    
    def test_health_server_custom_port(self):
        """Test HealthServer accepts custom port."""
        from health import HealthServer
        
        mock_bot = MagicMock()
        server = HealthServer(mock_bot, port=9000)
        
        self.assertEqual(server.port, 9000)
        
        print("✓ Custom port configuration works")


class TestHealthServerAsync(unittest.IsolatedAsyncioTestCase):
    """Async tests for HealthServer."""
    
    async def test_health_handler_returns_correct_structure(self):
        """Test that health handler returns expected JSON structure."""
        from health import HealthServer, AIOHTTP_AVAILABLE
        
        if not AIOHTTP_AVAILABLE:
            self.skipTest("aiohttp not installed")
        
        # Create mock bot with all required attributes
        mock_bot = MagicMock()
        mock_bot.markets = ["diam_iron", "gold_iron", "coal_iron"]
        mock_bot.client.circuit_breaker.state = "CLOSED"
        mock_bot.client.circuit_breaker.get_stats.return_value = {
            "failures": 0,
            "total_blocked": 0
        }
        mock_bot.client.rate_limiter.get_stats.return_value = {
            "total_requests": 100,
            "total_waits": 2
        }
        mock_bot.ws.running = True
        mock_bot.price_model.is_healthy.return_value = True
        mock_bot.metrics.get_realized_pnl.return_value = 12.3456
        mock_bot.metrics.orders_placed = 50
        mock_bot.metrics.orders_cancelled = 5
        mock_bot.metrics.trades = [1, 2, 3]  # 3 trades
        
        server = HealthServer(mock_bot, port=8080)
        
        # Create mock request
        mock_request = MagicMock()
        
        # Call handler
        response = await server.health_handler(mock_request)
        
        # Check response
        self.assertEqual(response.status, 200)
        
        # Parse JSON body
        import json
        body = json.loads(response.body)
        
        self.assertEqual(body["status"], "healthy")
        self.assertEqual(body["markets_count"], 3)
        self.assertEqual(body["circuit_breaker"], "CLOSED")
        self.assertTrue(body["websocket_connected"])
        self.assertTrue(body["metrics_healthy"])
        self.assertEqual(body["realized_pnl"], 12.3456)
        self.assertEqual(body["orders_placed"], 50)
        self.assertEqual(body["total_trades"], 3)
        
        print("✓ Health handler returns correct structure")
    
    async def test_health_handler_degraded_state(self):
        """Test that health handler returns 503 when circuit breaker is open."""
        from health import HealthServer, AIOHTTP_AVAILABLE
        
        if not AIOHTTP_AVAILABLE:
            self.skipTest("aiohttp not installed")
        
        mock_bot = MagicMock()
        mock_bot.markets = ["diam_iron"]
        mock_bot.client.circuit_breaker.state = "OPEN"  # Degraded!
        mock_bot.client.circuit_breaker.get_stats.return_value = {"failures": 5, "total_blocked": 10}
        mock_bot.client.rate_limiter.get_stats.return_value = {"total_requests": 0, "total_waits": 0}
        mock_bot.ws.running = False
        mock_bot.price_model.is_healthy.return_value = True
        mock_bot.metrics.get_realized_pnl.return_value = 0
        mock_bot.metrics.orders_placed = 0
        mock_bot.metrics.orders_cancelled = 0
        mock_bot.metrics.trades = []
        
        server = HealthServer(mock_bot, port=8080)
        mock_request = MagicMock()
        
        response = await server.health_handler(mock_request)
        
        # Should return 503 Service Unavailable
        self.assertEqual(response.status, 503)
        
        import json
        body = json.loads(response.body)
        self.assertEqual(body["status"], "degraded")
        
        print("✓ Health handler returns degraded state correctly")


class TestHealthConfig(unittest.TestCase):
    """Tests for health configuration."""
    
    def test_health_config_defaults(self):
        """Test that HealthConfig has correct defaults."""
        from config import HealthConfig
        
        config = HealthConfig()
        
        self.assertTrue(config.enabled)
        self.assertEqual(config.port, 8080)
        
        print("✓ HealthConfig has correct defaults")
    
    def test_config_includes_health(self):
        """Test that main Config includes health section."""
        from config import Config
        
        config = Config()
        
        self.assertTrue(hasattr(config, 'health'))
        self.assertTrue(config.health.enabled)
        
        print("✓ Config includes health section")


if __name__ == "__main__":
    print("=" * 60)
    print("Running Health Endpoint Tests")
    print("=" * 60)
    unittest.main(verbosity=2)
