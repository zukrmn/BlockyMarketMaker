#!/usr/bin/env python
"""
Advanced dashboard demo with realistic mock market data.
Run this to preview the dashboard at http://localhost:8081/dashboard
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dashboard import TradingDashboard


class MockMetrics:
    """Mock metrics for dashboard demo with realistic market data."""
    
    def __init__(self):
        self.trades = [
            {"market": "diam_iron", "side": "buy", "price": 48.5, "quantity": 10},
            {"market": "diam_iron", "side": "sell", "price": 52.0, "quantity": 10},
            {"market": "gold_iron", "side": "buy", "price": 4.8, "quantity": 50},
            {"market": "gold_iron", "side": "sell", "price": 5.2, "quantity": 45},
            {"market": "coal_iron", "side": "buy", "price": 0.45, "quantity": 200},
            {"market": "lapi_iron", "side": "buy", "price": 2.1, "quantity": 30},
            {"market": "ston_iron", "side": "sell", "price": 0.12, "quantity": 500},
        ]
        self.orders_placed = 347
        self.orders_cancelled = 23
        
        # Market stats with strategy info
        self.market_stats = {
            "diam_iron": {
                "strategy": "scarcity",
                "mid_price": 50.0,
                "spread": 0.032,
                "buy_volume": 520.0,
                "sell_volume": 485.0,
                "buy_qty": 10,
                "sell_qty": 10,
                "change": 2.5,
            },
            "gold_iron": {
                "strategy": "composite",
                "mid_price": 5.0,
                "spread": 0.028,
                "buy_volume": 1240.0,
                "sell_volume": 1180.0,
                "buy_qty": 100,
                "sell_qty": 100,
                "change": -1.2,
            },
            "coal_iron": {
                "strategy": "ticker",
                "mid_price": 0.45,
                "spread": 0.035,
                "buy_volume": 3500.0,
                "sell_volume": 3200.0,
                "buy_qty": 500,
                "sell_qty": 500,
                "change": 0.8,
            },
            "lapi_iron": {
                "strategy": "vwap",
                "mid_price": 2.0,
                "spread": 0.030,
                "buy_volume": 890.0,
                "sell_volume": 920.0,
                "buy_qty": 50,
                "sell_qty": 50,
                "change": 1.5,
            },
            "ston_iron": {
                "strategy": "scarcity",
                "mid_price": 0.10,
                "spread": 0.10,
                "buy_volume": 12000.0,
                "sell_volume": 11500.0,
                "buy_qty": 1000,
                "sell_qty": 1000,
                "change": -0.5,
            },
            "obsn_iron": {
                "strategy": "composite",
                "mid_price": 2.5,
                "spread": 0.035,
                "buy_volume": 450.0,
                "sell_volume": 420.0,
                "buy_qty": 20,
                "sell_qty": 20,
                "change": 3.2,
            },
            "slme_iron": {
                "strategy": "ticker",
                "mid_price": 5.0,
                "spread": 0.028,
                "buy_volume": 280.0,
                "sell_volume": 310.0,
                "buy_qty": 25,
                "sell_qty": 25,
                "change": -2.1,
            },
            "sand_iron": {
                "strategy": "vwap",
                "mid_price": 0.04,
                "spread": 0.25,
                "buy_volume": 8000.0,
                "sell_volume": 7500.0,
                "buy_qty": 2000,
                "sell_qty": 2000,
                "change": 0.3,
            },
        }
    
    def get_realized_pnl(self):
        return 127.45


class MockBot:
    """Mock bot for dashboard demo."""
    
    def __init__(self):
        self.metrics = MockMetrics()
        self.markets = list(self.metrics.market_stats.keys())


async def main():
    print("=" * 60)
    print("🚀 ACMaker Dashboard Demo")
    print("=" * 60)
    
    mock_bot = MockBot()
    dashboard = TradingDashboard(bot=mock_bot, port=8081)
    
    await dashboard.start()
    
    print()
    print("📊 Dashboard: http://localhost:8081/dashboard")
    print("📈 API Stats: http://localhost:8081/api/stats")
    print()
    print("Encaminhe a porta 8081 no VS Code para acessar!")
    print("Press Ctrl+C to stop...")
    print()
    
    # Create stop event
    stop_event = asyncio.Event()
    
    def signal_handler():
        stop_event.set()
    
    loop = asyncio.get_event_loop()
    try:
        import signal
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
    except NotImplementedError:
        pass  # Windows doesn't support signal handlers in asyncio
    
    await stop_event.wait()
    
    print("\n🛑 Stopping dashboard...")
    await dashboard.stop()
    print("✅ Dashboard stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Already handled

