"""
Unit tests for the PriceModel class.
Tests fair price calculation logic and supply estimation.
"""
import unittest
import os
import sys
from unittest.mock import MagicMock, patch

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))


class TestPriceModel(unittest.TestCase):
    """Tests for PriceModel."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock client
        self.mock_client = MagicMock()
        self.mock_client.BASE_URL = "https://test.blocky.com/api/v1"
        self.mock_client.get_supply_metrics.return_value = [
            {"1": 100, "4": 50}  # Stone IDs
        ]
        
    def test_init_with_default_prices(self):
        """Test initialization with default base prices."""
        from price_model import PriceModel
        
        model = PriceModel(self.mock_client)
        
        # Should have default prices
        self.assertIn("diam_iron", model.base_prices)
        self.assertEqual(model.base_prices["diam_iron"], 50.0)
        self.assertEqual(model.base_prices["ston_iron"], 0.1)
        
    def test_init_with_custom_prices(self):
        """Test initialization with custom base prices from config."""
        from price_model import PriceModel
        
        custom_prices = {
            "diam_iron": 100.0,  # Override default
            "new_item_iron": 5.0  # New item
        }
        
        model = PriceModel(self.mock_client, base_prices=custom_prices)
        
        # Custom price should override default
        self.assertEqual(model.base_prices["diam_iron"], 100.0)
        # New item should be added
        self.assertEqual(model.base_prices["new_item_iron"], 5.0)
        # Non-overridden defaults should remain
        self.assertEqual(model.base_prices["ston_iron"], 0.1)
        
    def test_calculate_fair_price_unknown_market(self):
        """Test that unknown markets return 0."""
        from price_model import PriceModel
        
        model = PriceModel(self.mock_client)
        
        # Unknown market should return 0
        price = model.calculate_fair_price("unknown_iron")
        self.assertEqual(price, 0.0)
        
    def test_calculate_fair_price_scarcity_multiplier(self):
        """Test that scarcity increases price."""
        from price_model import PriceModel
        
        model = PriceModel(self.mock_client)
        
        # Mock low circulating supply -> high scarcity
        model.get_circulating_supply = MagicMock(return_value={"ston_iron": 0})
        model.world_supply = {"ston_iron": 1000}
        
        price = model.calculate_fair_price("ston_iron")
        
        # With 0 circulating and 1000 total, multiplier = 1000/1000 = 1
        # Base price is 0.1, so fair_price = 0.1 * 1 = 0.1
        self.assertGreater(price, 0)
        
    def test_calculate_fair_price_capped_multiplier(self):
        """Test that multiplier is capped at 20."""
        from price_model import PriceModel
        
        model = PriceModel(self.mock_client)
        
        # Mock very high scarcity (almost all extracted)
        model.get_circulating_supply = MagicMock(return_value={"ston_iron": 999})
        model.world_supply = {"ston_iron": 1000}
        
        price = model.calculate_fair_price("ston_iron")
        
        # Multiplier would be 1000/1 = 1000, but should cap at 20
        # Base 0.1 * 20 = 2.0
        self.assertEqual(price, 0.1 * 20)
        
    def test_circulating_supply_cache(self):
        """Test that supply data is cached."""
        from price_model import PriceModel
        import time
        
        model = PriceModel(self.mock_client)
        
        # First call should hit API
        model.get_circulating_supply()
        self.assertEqual(self.mock_client.get_supply_metrics.call_count, 1)
        
        # Second call within cache TTL should use cache
        model.get_circulating_supply()
        self.assertEqual(self.mock_client.get_supply_metrics.call_count, 1)
        
    def test_is_healthy(self):
        """Test health check method."""
        from price_model import PriceModel
        
        model = PriceModel(self.mock_client)
        
        # Initially healthy
        self.assertTrue(model.is_healthy())
        
        # Simulate failures
        model._consecutive_failures = 3
        self.assertFalse(model.is_healthy())


if __name__ == "__main__":
    unittest.main()
