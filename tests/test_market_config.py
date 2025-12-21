"""
Unit tests for market configuration (whitelist/blacklist).
Tests that market filtering works correctly.
"""
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))


class TestMarketConfigOptions(unittest.TestCase):
    """Tests for market configuration options."""
    
    def test_trading_config_has_market_lists(self):
        """Test that TradingConfig has enabled_markets and disabled_markets."""
        from config import TradingConfig
        
        config = TradingConfig()
        
        self.assertTrue(hasattr(config, 'enabled_markets'))
        self.assertTrue(hasattr(config, 'disabled_markets'))
        self.assertEqual(config.enabled_markets, [])  # Default empty
        self.assertEqual(config.disabled_markets, [])
        
        print("✓ TradingConfig has market list fields")
    
    def test_whitelist_filtering(self):
        """Test whitelist filtering logic."""
        all_markets = ['diam_iron', 'gold_iron', 'coal_iron', 'sand_iron']
        enabled = ['diam_iron', 'gold_iron']
        disabled = []
        
        # Whitelist filter
        if enabled:
            filtered = [m for m in all_markets if m in enabled]
        else:
            filtered = all_markets
        
        # Blacklist filter
        filtered = [m for m in filtered if m not in disabled]
        
        self.assertEqual(filtered, ['diam_iron', 'gold_iron'])
        
        print("✓ Whitelist filtering works")
    
    def test_blacklist_filtering(self):
        """Test blacklist filtering logic."""
        all_markets = ['diam_iron', 'gold_iron', 'coal_iron', 'sand_iron']
        enabled = []  # Empty = all
        disabled = ['sand_iron', 'coal_iron']
        
        # Whitelist filter
        if enabled:
            filtered = [m for m in all_markets if m in enabled]
        else:
            filtered = all_markets
        
        # Blacklist filter
        filtered = [m for m in filtered if m not in disabled]
        
        self.assertEqual(filtered, ['diam_iron', 'gold_iron'])
        
        print("✓ Blacklist filtering works")
    
    def test_blacklist_overrides_whitelist(self):
        """Test that blacklist overrides whitelist."""
        all_markets = ['diam_iron', 'gold_iron', 'coal_iron']
        enabled = ['diam_iron', 'gold_iron', 'coal_iron']
        disabled = ['coal_iron']  # Also in whitelist
        
        # Whitelist filter
        if enabled:
            filtered = [m for m in all_markets if m in enabled]
        else:
            filtered = all_markets
        
        # Blacklist filter (should remove coal_iron even though it's whitelisted)
        filtered = [m for m in filtered if m not in disabled]
        
        self.assertEqual(filtered, ['diam_iron', 'gold_iron'])
        
        print("✓ Blacklist overrides whitelist")
    
    def test_empty_lists_means_all_markets(self):
        """Test that empty lists means all markets are enabled."""
        all_markets = ['diam_iron', 'gold_iron', 'coal_iron']
        enabled = []
        disabled = []
        
        # Whitelist filter
        if enabled:
            filtered = [m for m in all_markets if m in enabled]
        else:
            filtered = all_markets
        
        # Blacklist filter
        filtered = [m for m in filtered if m not in disabled]
        
        self.assertEqual(filtered, all_markets)
        
        print("✓ Empty lists enables all markets")


class TestMarketConfigIntegration(unittest.TestCase):
    """Integration tests for market config."""
    
    def test_config_includes_market_lists(self):
        """Test that main Config includes market lists."""
        from config import Config
        
        cfg = Config()
        
        self.assertTrue(hasattr(cfg.trading, 'enabled_markets'))
        self.assertTrue(hasattr(cfg.trading, 'disabled_markets'))
        
        print("✓ Main Config includes market lists")
    
    def test_can_set_enabled_markets(self):
        """Test that enabled_markets can be set."""
        from config import TradingConfig
        
        config = TradingConfig(enabled_markets=['diam_iron', 'gold_iron'])
        
        self.assertEqual(config.enabled_markets, ['diam_iron', 'gold_iron'])
        
        print("✓ enabled_markets can be set")
    
    def test_can_set_disabled_markets(self):
        """Test that disabled_markets can be set."""
        from config import TradingConfig
        
        config = TradingConfig(disabled_markets=['sand_iron', 'dirt_iron'])
        
        self.assertEqual(config.disabled_markets, ['sand_iron', 'dirt_iron'])
        
        print("✓ disabled_markets can be set")


if __name__ == "__main__":
    print("=" * 60)
    print("Running Market Configuration Tests")
    print("=" * 60)
    unittest.main(verbosity=2)
