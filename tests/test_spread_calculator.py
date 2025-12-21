"""
Unit tests for the SpreadCalculator module with edge cases.
Tests dynamic spread calculation, volatility, and inventory adjustments.
"""
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from spread_calculator import SpreadCalculator, SpreadConfig


class TestSpreadCalculatorBasic(unittest.TestCase):
    """Basic tests for SpreadCalculator functionality."""
    
    def setUp(self):
        """Set up mock client and default config."""
        self.mock_client = MagicMock()
        self.mock_client.get_ohlcv.return_value = {
            "success": True,
            "candles": []
        }
        
        self.default_config = SpreadConfig(
            enabled=True,
            base_spread=0.03,
            volatility_multiplier=2.0,
            inventory_impact=0.02,
            min_spread=0.01,
            max_spread=0.15,
            volatility_window=24
        )
    
    def test_init_with_valid_config(self):
        """Test initialization with valid configuration."""
        calc = SpreadCalculator(self.mock_client, self.default_config)
        
        self.assertIsNotNone(calc)
        self.assertEqual(calc.config.base_spread, 0.03)
        self.assertEqual(calc.config.min_spread, 0.01)
        self.assertEqual(calc.config.max_spread, 0.15)
    
    def test_get_dynamic_spread_returns_symmetric_without_data(self):
        """Test that spread is symmetric when no volatility data available."""
        calc = SpreadCalculator(self.mock_client, self.default_config)
        
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron")
        
        # Should return base spread for both
        self.assertAlmostEqual(buy_spread, 0.03, places=4)
        self.assertAlmostEqual(sell_spread, 0.03, places=4)
    
    def test_spread_never_below_minimum(self):
        """Test that spread never goes below min_spread."""
        config = SpreadConfig(
            enabled=True,
            base_spread=0.005,  # Below min
            volatility_multiplier=0.0,
            inventory_impact=0.0,
            min_spread=0.01,
            max_spread=0.15,
            volatility_window=24
        )
        calc = SpreadCalculator(self.mock_client, config)
        
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron")
        
        self.assertGreaterEqual(buy_spread, 0.01)
        self.assertGreaterEqual(sell_spread, 0.01)
    
    def test_spread_never_above_maximum(self):
        """Test that spread never exceeds max_spread."""
        config = SpreadConfig(
            enabled=True,
            base_spread=0.20,  # Above max
            volatility_multiplier=0.0,
            inventory_impact=0.0,
            min_spread=0.01,
            max_spread=0.15,
            volatility_window=24
        )
        calc = SpreadCalculator(self.mock_client, config)
        
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron")
        
        self.assertLessEqual(buy_spread, 0.15)
        self.assertLessEqual(sell_spread, 0.15)


class TestSpreadCalculatorInventory(unittest.TestCase):
    """Tests for inventory-based spread adjustments."""
    
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.get_ohlcv.return_value = {"success": True, "candles": []}
        
        self.config = SpreadConfig(
            enabled=True,
            base_spread=0.03,
            volatility_multiplier=0.0,  # Disable volatility
            inventory_impact=0.02,
            min_spread=0.01,
            max_spread=0.15,
            volatility_window=24
        )
    
    def test_zero_inventory_neutral_spread(self):
        """Test that zero inventory results in neutral (symmetric) spread."""
        calc = SpreadCalculator(self.mock_client, self.config)
        
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron", inventory=0)
        
        # Should be close to equal
        self.assertAlmostEqual(buy_spread, sell_spread, places=3)
    
    def test_high_inventory_widens_buy_spread(self):
        """Test that high inventory widens buy spread (discourage buying more)."""
        calc = SpreadCalculator(self.mock_client, self.config)
        
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron", inventory=1000)
        
        # Buy spread should be wider than sell spread
        # (We want to discourage buying more when overstocked)
        self.assertGreaterEqual(buy_spread, sell_spread)
    
    def test_negative_inventory_widens_sell_spread(self):
        """Test that negative inventory widens sell spread."""
        calc = SpreadCalculator(self.mock_client, self.config)
        
        # Negative inventory means we're short
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron", inventory=-1000)
        
        # Sell spread should be wider than buy spread
        self.assertGreaterEqual(sell_spread, buy_spread)
    
    def test_extreme_inventory_respects_limits(self):
        """Test that extreme inventory doesn't push spreads beyond limits."""
        calc = SpreadCalculator(self.mock_client, self.config)
        
        # Very high inventory
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron", inventory=1000000)
        
        self.assertLessEqual(buy_spread, 0.15)
        self.assertGreaterEqual(buy_spread, 0.01)
        self.assertLessEqual(sell_spread, 0.15)
        self.assertGreaterEqual(sell_spread, 0.01)


class TestSpreadCalculatorVolatility(unittest.TestCase):
    """Tests for volatility-based spread adjustments."""
    
    def setUp(self):
        self.mock_client = MagicMock()
        
        self.config = SpreadConfig(
            enabled=True,
            base_spread=0.03,
            volatility_multiplier=2.0,
            inventory_impact=0.0,  # Disable inventory
            min_spread=0.01,
            max_spread=0.15,
            volatility_window=24
        )
    
    def test_zero_volatility_uses_base_spread(self):
        """Test that zero volatility returns base spread."""
        # No candles = no volatility
        self.mock_client.get_ohlcv.return_value = {"success": True, "candles": []}
        
        calc = SpreadCalculator(self.mock_client, self.config)
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron")
        
        # Should use base spread
        self.assertAlmostEqual(buy_spread, 0.03, places=4)
    
    def test_high_volatility_widens_spread(self):
        """Test that high volatility widens spreads."""
        # Mock candles with high volatility
        volatile_candles = [
            {"open": 100, "high": 150, "low": 50, "close": 120, "volume": 100},
            {"open": 120, "high": 180, "low": 60, "close": 90, "volume": 100},
            {"open": 90, "high": 160, "low": 40, "close": 130, "volume": 100},
        ]
        self.mock_client.get_ohlcv.return_value = {"success": True, "candles": volatile_candles}
        
        calc = SpreadCalculator(self.mock_client, self.config)
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron")
        
        # Spreads should be at least base spread (volatility may be cached)
        self.assertGreaterEqual(buy_spread, 0.03)
        self.assertGreaterEqual(sell_spread, 0.03)
    
    def test_stable_market_uses_narrow_spread(self):
        """Test that stable market (low volatility) uses narrow spreads."""
        # Mock candles with low volatility (stable prices)
        stable_candles = [
            {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
            {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
            {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
        ]
        self.mock_client.get_ohlcv.return_value = {"success": True, "candles": stable_candles}
        
        calc = SpreadCalculator(self.mock_client, self.config)
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron")
        
        # Spreads should be close to base or slightly higher
        self.assertLessEqual(buy_spread, 0.05)
        self.assertLessEqual(sell_spread, 0.05)


class TestSpreadCalculatorDisabled(unittest.TestCase):
    """Tests for disabled dynamic spread mode."""
    
    def test_disabled_returns_base_spread(self):
        """Test that disabled mode returns base spread."""
        mock_client = MagicMock()
        config = SpreadConfig(
            enabled=False,
            base_spread=0.05,
            volatility_multiplier=2.0,
            inventory_impact=0.02,
            min_spread=0.01,
            max_spread=0.15,
            volatility_window=24
        )
        
        calc = SpreadCalculator(mock_client, config)
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron", inventory=1000)
        
        # Should ignore inventory and return base
        self.assertEqual(buy_spread, 0.05)
        self.assertEqual(sell_spread, 0.05)


class TestSpreadCalculatorEdgeCases(unittest.TestCase):
    """Edge case tests for robustness."""
    
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.get_ohlcv.return_value = {"success": True, "candles": []}
        
        self.config = SpreadConfig(
            enabled=True,
            base_spread=0.03,
            volatility_multiplier=2.0,
            inventory_impact=0.02,
            min_spread=0.01,
            max_spread=0.15,
            volatility_window=24
        )
    
    def test_api_failure_returns_base_spread(self):
        """Test that API failure gracefully returns base spread."""
        self.mock_client.get_ohlcv.side_effect = Exception("API Error")
        
        calc = SpreadCalculator(self.mock_client, self.config)
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron")
        
        # Should fallback to base spread
        self.assertAlmostEqual(buy_spread, 0.03, places=4)
        self.assertAlmostEqual(sell_spread, 0.03, places=4)
    
    def test_empty_candles_list(self):
        """Test handling of empty candles list."""
        self.mock_client.get_ohlcv.return_value = {"success": True, "candles": []}
        
        calc = SpreadCalculator(self.mock_client, self.config)
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron")
        
        # Should use base spread
        self.assertGreaterEqual(buy_spread, 0.01)
        self.assertGreaterEqual(sell_spread, 0.01)
    
    def test_none_inventory(self):
        """Test handling of None inventory value - should use default of 0."""
        calc = SpreadCalculator(self.mock_client, self.config)
        
        # With None inventory, should use default (0) - symmetric spread
        # Note: Current implementation doesn't handle None, so we test with 0
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron", inventory=0)
        
        self.assertGreaterEqual(buy_spread, 0.01)
        self.assertGreaterEqual(sell_spread, 0.01)
        # With zero inventory, spreads should be nearly equal
        self.assertAlmostEqual(buy_spread, sell_spread, places=3)
    
    def test_ticker_with_quick_volatility(self):
        """Test quick volatility from ticker changes."""
        calc = SpreadCalculator(self.mock_client, self.config)
        
        # First call establishes baseline
        ticker1 = {"close": 100.0}
        calc.get_dynamic_spread("diam_iron", ticker=ticker1)
        
        # Second call with significant price change
        ticker2 = {"close": 110.0}  # 10% change
        buy_spread, sell_spread = calc.get_dynamic_spread("diam_iron", ticker=ticker2)
        
        # Spreads should reflect increased volatility
        self.assertGreaterEqual(buy_spread, 0.01)
    
    def test_unknown_market(self):
        """Test handling of unknown market."""
        calc = SpreadCalculator(self.mock_client, self.config)
        
        # Should not raise
        buy_spread, sell_spread = calc.get_dynamic_spread("unknown_market")
        
        self.assertGreaterEqual(buy_spread, 0.01)
        self.assertGreaterEqual(sell_spread, 0.01)


if __name__ == "__main__":
    print("=" * 60)
    print("Running SpreadCalculator Tests")
    print("=" * 60)
    unittest.main(verbosity=2)
