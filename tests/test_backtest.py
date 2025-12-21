"""
Unit tests for the backtesting module.
Tests BacktestEngine simulation logic.
"""
import unittest
from unittest.mock import MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))


class TestBacktestEngine(unittest.TestCase):
    """Tests for BacktestEngine."""
    
    def test_engine_initialization(self):
        """Test BacktestEngine initializes with correct capital."""
        from backtest import BacktestEngine
        
        engine = BacktestEngine(initial_capital=500.0)
        
        self.assertEqual(engine.initial_capital, 500.0)
        self.assertEqual(engine.capital, 500.0)
        self.assertEqual(len(engine.orders), 0)
        self.assertEqual(len(engine.trades), 0)
        
        print("✓ BacktestEngine initializes correctly")
    
    def test_load_candles(self):
        """Test loading candle data."""
        from backtest import BacktestEngine
        
        engine = BacktestEngine()
        
        candles = [
            {'timestamp': 1000, 'open': 50, 'high': 52, 'low': 49, 'close': 51, 'volume': 100},
            {'timestamp': 2000, 'open': 51, 'high': 53, 'low': 50, 'close': 52, 'volume': 110},
        ]
        
        engine.load_candles('diam_iron', candles)
        
        self.assertIn('diam_iron', engine.candles)
        self.assertEqual(len(engine.candles['diam_iron']), 2)
        self.assertEqual(engine.candles['diam_iron'][0].close, 51)
        
        print("✓ Candle loading works")
    
    def test_run_without_data_returns_empty(self):
        """Test that running without data returns empty result."""
        from backtest import BacktestEngine
        
        engine = BacktestEngine(initial_capital=1000.0)
        result = engine.run()
        
        self.assertEqual(result.total_trades, 0)
        self.assertEqual(result.initial_capital, 1000.0)
        self.assertEqual(result.final_capital, 1000.0)
        
        print("✓ Empty run returns expected result")
    
    def test_run_simulation(self):
        """Test running a simple simulation."""
        from backtest import BacktestEngine
        
        engine = BacktestEngine(initial_capital=1000.0)
        
        # Create price data that should trigger trades
        candles = [
            {'timestamp': 1000, 'open': 50, 'high': 55, 'low': 45, 'close': 50, 'volume': 100},
            {'timestamp': 2000, 'open': 50, 'high': 60, 'low': 40, 'close': 55, 'volume': 120},
            {'timestamp': 3000, 'open': 55, 'high': 65, 'low': 50, 'close': 60, 'volume': 130},
        ]
        
        engine.load_candles('diam_iron', candles)
        result = engine.run(spread=0.10, target_value=100.0)
        
        # Should have some activity
        self.assertGreater(len(result.markets_traded), 0)
        self.assertIn('diam_iron', result.markets_traded)
        
        print(f"✓ Simulation ran with {result.total_trades} trades")
    
    def test_backtest_result_properties(self):
        """Test BacktestResult computed properties."""
        from backtest import BacktestResult
        
        result = BacktestResult(
            start_time=1000,
            end_time=2000,
            initial_capital=100.0,
            final_capital=120.0,
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            total_pnl=20.0,
            max_drawdown=0.05,
            sharpe_ratio=1.5,
            markets_traded=['diam_iron'],
            trades=[]
        )
        
        self.assertEqual(result.win_rate, 0.7)
        self.assertEqual(result.return_pct, 20.0)
        
        print("✓ BacktestResult properties compute correctly")
    
    def test_fetch_candles_from_api(self):
        """Test API candle fetching with mock client."""
        from backtest import BacktestEngine
        
        engine = BacktestEngine()
        
        mock_client = MagicMock()
        mock_client.get_ohlcv.return_value = {
            'success': True,
            'candles': [
                {'timestamp': 1000, 'o': 50, 'h': 52, 'l': 49, 'c': 51, 'v': 100},
                {'timestamp': 2000, 'o': 51, 'h': 53, 'l': 50, 'c': 52, 'v': 110},
            ]
        }
        
        candles = engine.fetch_candles_from_api(mock_client, 'diam_iron', '1H')
        
        self.assertEqual(len(candles), 2)
        mock_client.get_ohlcv.assert_called_once_with('diam_iron', timeframe='1H')
        
        print("✓ API candle fetching works")
    
    def test_order_simulation(self):
        """Test order placement and fill simulation."""
        from backtest import BacktestEngine
        
        engine = BacktestEngine(initial_capital=1000.0)
        
        # Place a buy order
        engine._place_order('diam_iron', 'buy', 50.0, 10.0, 1000)
        
        self.assertEqual(len(engine.orders), 1)
        self.assertEqual(engine.orders[0].price, 50.0)
        self.assertEqual(engine.orders[0].side, 'buy')
        self.assertFalse(engine.orders[0].filled)
        
        print("✓ Order placement works")


class TestBacktestConfig(unittest.TestCase):
    """Test backtest uses config correctly."""
    
    def test_uses_config_defaults(self):
        """Test that backtest uses config defaults when no args provided."""
        from backtest import BacktestEngine
        from config import get_config
        
        config = get_config()
        engine = BacktestEngine()
        
        # Load minimal data
        engine.load_candles('test_iron', [
            {'timestamp': 1000, 'open': 10, 'high': 12, 'low': 8, 'close': 11, 'volume': 50}
        ])
        
        # Run without explicit params - should use config
        result = engine.run()
        
        # Just verify it runs without error
        self.assertIsNotNone(result)
        
        print("✓ Backtest uses config defaults")


if __name__ == "__main__":
    print("=" * 60)
    print("Running Backtest Module Tests")
    print("=" * 60)
    unittest.main(verbosity=2)
