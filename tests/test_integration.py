"""
Integration tests for the Market Maker bot.
Tests real component interactions without live API calls.
"""
import asyncio
import unittest
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfigIntegration(unittest.TestCase):
    """Tests configuration loading and integration."""
    
    def test_config_loads_from_yaml(self):
        """Verify config loads values from config.yaml."""
        from config import load_config, Config
        
        config = load_config()
        
        # Should return Config object
        self.assertIsInstance(config, Config)
        
        # Should have default/YAML values
        self.assertIsNotNone(config.trading.spread)
        self.assertIsNotNone(config.trading.target_value)
        self.assertIsNotNone(config.api.endpoint)
        
        print("✓ Config loads from YAML successfully")
    
    def test_config_env_override(self):
        """Verify environment variables override YAML values."""
        from config import load_config
        
        # Set test env var
        os.environ["BLOCKY_API_ENDPOINT"] = "https://test.example.com/api"
        
        config = load_config()
        
        self.assertEqual(config.api.endpoint, "https://test.example.com/api")
        
        # Cleanup
        del os.environ["BLOCKY_API_ENDPOINT"]
        print("✓ Environment variables override YAML")


class TestPriceModelIntegration(unittest.TestCase):
    """Tests price model calculations."""
    
    def test_market_mapping_completeness(self):
        """Verify all expected markets have mappings."""
        from price_model import PriceModel
        
        expected_markets = [
            "diam_iron", "gold_iron", "coal_iron", "ston_iron",
            "pump_iron", "eggs_iron"  # Recently added
        ]
        
        for market in expected_markets:
            self.assertIn(market, PriceModel.MARKET_MAPPING,
                         f"Missing mapping for {market}")
        
        print(f"✓ All {len(expected_markets)} expected markets have mappings")
    
    def test_price_calculation_with_mock_client(self):
        """Test fair price calculation logic."""
        from price_model import PriceModel
        
        # Mock client
        mock_client = MagicMock()
        mock_client.BASE_URL = "https://mock.api"
        mock_client.get_supply_metrics.return_value = [
            {"264": 1000, "56": 500, "57": 200}  # Diamond items
        ]
        
        model = PriceModel(mock_client)
        
        price = model.calculate_fair_price("diam_iron")
        
        self.assertGreater(price, 0, "Price should be positive")
        print(f"✓ Diamond fair price calculated: {price:.2f} Iron")
    
    def test_health_check_method(self):
        """Verify is_healthy() method works."""
        from price_model import PriceModel
        
        mock_client = MagicMock()
        mock_client.BASE_URL = "https://mock.api"
        mock_client.get_supply_metrics.return_value = [{"264": 100}]
        
        model = PriceModel(mock_client)
        
        # Initially should be healthy (no failures)
        self.assertTrue(model.is_healthy())
        
        print("✓ Health check method works")


class TestMetricsIntegration(unittest.TestCase):
    """Tests metrics tracking and persistence."""
    
    def test_metrics_save_and_load(self):
        """Verify metrics can be saved and loaded."""
        import tempfile
        import os
        from metrics import MetricsTracker
        
        # Create temp file for test
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Create tracker with temp path
            tracker = MetricsTracker(persistence_path=temp_path)
            
            # Record some activity
            tracker.record_order_placed()
            tracker.record_order_placed()
            tracker.record_order_cancelled()
            
            # Save
            tracker.save()
            
            # Create new tracker that should load
            tracker2 = MetricsTracker(persistence_path=temp_path)
            
            self.assertEqual(tracker2.orders_placed, 2)
            self.assertEqual(tracker2.orders_cancelled, 1)
            
            print("✓ Metrics persistence works")
            
        finally:
            os.unlink(temp_path)


class TestBotIntegration(unittest.IsolatedAsyncioTestCase):
    """Async tests for bot integration."""
    
    async def test_bot_initialization(self):
        """Test bot initializes correctly with mocked dependencies."""
        from bot import MarketMaker
        
        mock_client = MagicMock()
        mock_client.get_markets.return_value = {
            "success": True,
            "markets": [{"market": "diam_iron"}, {"market": "gold_iron"}]
        }
        mock_client.get_wallets.return_value = {
            "success": True,
            "wallets": [{"currency": "iron", "balance": "1000"}]
        }
        mock_client.get_orders.return_value = {"success": True, "orders": []}
        mock_client.BASE_URL = "https://mock.api"
        
        with patch('bot.Blocky', return_value=mock_client), \
             patch('bot.PriceModel') as MockPM, \
             patch('bot.BlockyWebSocket') as MockWS:
            
            MockPM.return_value.calculate_fair_price.return_value = 50.0
            MockPM.return_value.get_circulating_supply.return_value = {}
            MockWS.return_value.connect = AsyncMock()
            MockWS.return_value.subscribe_transactions = AsyncMock()
            MockWS.return_value.subscribe_orderbook = AsyncMock()
            
            bot = MarketMaker("test_key", "https://mock.api")
            
            self.assertEqual(len(bot.markets), 2)
            self.assertIn("diam_iron", bot.markets)
            
            print("✓ Bot initializes correctly")


if __name__ == '__main__':
    print("=" * 60)
    print("Running Market Maker Integration Tests")
    print("=" * 60)
    unittest.main(verbosity=2)
