#!/usr/bin/env python3
"""
CLI runner for Market Maker backtesting.
Fetches historical data from Blocky API and runs simulations.

Usage:
    python run_backtest.py
    python run_backtest.py --markets diam_iron gold_iron
    python run_backtest.py --capital 500 --timeframe 1H
    python run_backtest.py --spread 0.03 --target-value 5
"""
import argparse
import sys
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

from blocky import Blocky
from backtest import BacktestEngine
from config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s │ %(levelname)-8s │ %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Run Market Maker backtest simulation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_backtest.py
      Run with default settings from config.yaml
      
  python run_backtest.py --markets diam_iron gold_iron
      Backtest specific markets
      
  python run_backtest.py --capital 500 --spread 0.03
      Custom initial capital and spread
      
  python run_backtest.py --all-markets
      Backtest all available markets
"""
    )
    
    parser.add_argument(
        '--markets', 
        nargs='+', 
        help='Markets to backtest (e.g., diam_iron gold_iron)'
    )
    
    parser.add_argument(
        '--all-markets',
        action='store_true',
        help='Backtest all available markets'
    )
    
    parser.add_argument(
        '--capital', 
        type=float, 
        default=1000.0,
        help='Initial capital in Iron (default: 1000)'
    )
    
    parser.add_argument(
        '--timeframe', 
        default='1H',
        choices=['1m', '5m', '15m', '1H', '4H', '1D'],
        help='Candle timeframe (default: 1H)'
    )
    
    parser.add_argument(
        '--spread',
        type=float,
        help='Override spread from config (e.g., 0.05 for 5%%)'
    )
    
    parser.add_argument(
        '--target-value',
        type=float,
        help='Override target order value from config'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress progress messages'
    )
    
    return parser.parse_args()


def get_available_markets(client) -> list:
    """Fetch all available markets from API."""
    try:
        response = client.get_markets()
        if response.get('success'):
            return [m['market'] for m in response.get('markets', [])]
    except Exception as e:
        logger.error(f"Failed to fetch markets: {e}")
    return []


def main():
    """Main entry point."""
    args = parse_args()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    print("=" * 60)
    print("🧪 MARKET MAKER BACKTEST")
    print("=" * 60)
    
    # Load config
    config = get_config()
    
    if not config.api.api_key:
        print("❌ Error: BLOCKY_API_KEY not set. Please set it in .env file.")
        sys.exit(1)
    
    # Initialize API client
    client = Blocky(
        api_key=config.api.api_key, 
        endpoint=config.api.endpoint
    )
    
    # Determine markets to test
    if args.all_markets:
        markets = get_available_markets(client)
        if not markets:
            print("❌ Could not fetch markets from API")
            sys.exit(1)
        print(f"📊 Testing ALL {len(markets)} markets")
    elif args.markets:
        markets = args.markets
    else:
        # Default markets
        markets = ['diam_iron', 'gold_iron', 'coal_iron', 'lapi_iron', 'ston_iron']
    
    print(f"📈 Markets: {', '.join(markets)}")
    print(f"💰 Initial Capital: {args.capital} Iron")
    print(f"⏰ Timeframe: {args.timeframe}")
    
    # Create backtest engine
    engine = BacktestEngine(initial_capital=args.capital)
    
    # Fetch historical data
    print("-" * 40)
    print("📥 Fetching historical data...")
    
    loaded_markets = 0
    for market in markets:
        candles = engine.fetch_candles_from_api(client, market, args.timeframe)
        if candles:
            loaded_markets += 1
            if not args.quiet:
                print(f"   ✓ {market}: {len(candles)} candles")
        else:
            if not args.quiet:
                print(f"   ✗ {market}: No data available")
    
    if loaded_markets == 0:
        print("❌ No market data loaded. Cannot run backtest.")
        sys.exit(1)
    
    print(f"📊 Loaded data for {loaded_markets}/{len(markets)} markets")
    
    # Run backtest
    print("-" * 40)
    print("🚀 Running simulation...")
    
    # Prepare parameters (use overrides or config defaults)
    run_params = {}
    if args.spread is not None:
        run_params['spread'] = args.spread
        print(f"   Spread: {args.spread*100:.1f}% (override)")
    if args.target_value is not None:
        run_params['target_value'] = args.target_value
        print(f"   Target Value: {args.target_value} Iron (override)")
    
    result = engine.run(**run_params)
    
    # Display results
    print()
    engine.print_summary(result)
    
    # Return code based on profitability
    if result.total_pnl > 0:
        print("\n✅ Strategy was PROFITABLE")
        return 0
    elif result.total_pnl < 0:
        print("\n⚠️ Strategy had LOSSES")
        return 1
    else:
        print("\n➖ Strategy broke even")
        return 0


if __name__ == '__main__':
    sys.exit(main())
