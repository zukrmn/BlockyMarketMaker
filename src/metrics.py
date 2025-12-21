"""
Performance metrics tracking for the Market Maker bot.
Tracks P&L, volume, spreads captured, and other trading statistics.
"""
import time
import logging
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

# Default persistence path
METRICS_FILE = os.path.join(os.path.dirname(__file__), "metrics_data.json")

@dataclass
class TradeRecord:
    """Record of a single trade."""
    timestamp: float
    market: str
    side: str  # 'buy' or 'sell'
    price: float
    quantity: float
    
    @property
    def value(self) -> float:
        return self.price * self.quantity


class MetricsTracker:
    """Tracks trading performance metrics for the Market Maker bot."""
    
    def __init__(self, persistence_path: Optional[str] = None, auto_save_interval: int = 60):
        """
        Initialize MetricsTracker with optional persistence.
        
        Args:
            persistence_path: Path to JSON file for saving metrics. None to disable persistence.
            auto_save_interval: Seconds between auto-saves (default: 60). 0 to disable.
        """
        self.persistence_path = persistence_path or METRICS_FILE
        self.auto_save_interval = auto_save_interval
        self._last_save_time = time.time()
        self._never_saved = True  # Flag to force first save after activity
        
        self.start_time = time.time()
        
        # Inventory tracking (cost basis)
        self.inventory: Dict[str, float] = defaultdict(float)  # base -> quantity
        self.cost_basis: Dict[str, float] = defaultdict(float)  # base -> total cost in Iron
        
        # Trade history
        self.trades: List[TradeRecord] = []
        
        # Aggregated metrics per market
        self.market_stats: Dict[str, dict] = defaultdict(lambda: {
            'buy_volume': 0.0,
            'sell_volume': 0.0,
            'buy_value': 0.0,
            'sell_value': 0.0,
            'trade_count': 0,
            'spreads_captured': [],  # List of (buy_price, sell_price) pairs
            'mid_price': 0.0,
            'change': 0.0,
            'recent_trades': deque(maxlen=50),  # Buffer for real-time dashboard display
            'strategy_prices': {},  # Recent calculated prices for each strategy
        })
        
        # Overall metrics
        self.total_iron_spent = 0.0
        self.total_iron_received = 0.0
        self.orders_placed = 0
        self.orders_cancelled = 0
        
        # Try to load existing metrics
        self._load()

    def record_trade(self, market: str, side: str, price: float, quantity: float):
        """Records a trade and updates metrics."""
        trade = TradeRecord(
            timestamp=time.time(),
            market=market,
            side=side,
            price=price,
            quantity=quantity
        )
        self.trades.append(trade)
        
        base = market.split('_')[0]
        stats = self.market_stats[market]
        stats['trade_count'] += 1
        
        if side == 'buy':
            # Bought base, spent Iron
            self.inventory[base] += quantity
            self.cost_basis[base] += trade.value
            self.total_iron_spent += trade.value
            stats['buy_volume'] += quantity
            stats['buy_value'] += trade.value
            
        elif side == 'sell':
            # Sold base, received Iron
            self.inventory[base] -= quantity
            self.total_iron_received += trade.value
            stats['sell_volume'] += quantity
            stats['sell_value'] += trade.value
            
            # Calculate realized P&L if we have cost basis
            if self.cost_basis[base] > 0 and self.inventory[base] > 0:
                avg_cost = self.cost_basis[base] / (self.inventory[base] + quantity)
                realized_pnl = (price - avg_cost) * quantity
                logger.info(f"📈 {market}: Realized P&L {realized_pnl:+.4f} Iron on {quantity:.2f} units")
    
    def record_spread(self, market: str, buy_price: float, sell_price: float):
        """Records the spread being quoted."""
        if buy_price > 0 and sell_price > 0:
            spread_pct = ((sell_price - buy_price) / buy_price) * 100
            self.market_stats[market]['spreads_captured'].append({
                'timestamp': time.time(),
                'buy': buy_price,
                'sell': sell_price,
                'spread_pct': spread_pct
            })

    def update_market_price(self, market: str, price: float, change_24h: float = 0.0):
        """Update current market price stats."""
        self.market_stats[market]['mid_price'] = price
        self.market_stats[market]['change'] = change_24h

    def record_public_trade(self, market: str, price: float, side: str, quantity: float):
        """Records a public trade from WebSocket for dashboard display."""
        try:
            trade_data = {
                'timestamp': time.time(),
                'time_str': time.strftime("%H:%M:%S"),
                'market': market,
                'price': price,
                'side': side.upper(),
                'quantity': quantity
            }
            self.market_stats[market]['recent_trades'].appendleft(trade_data)
        except Exception as e:
            logger.error(f"Error recording public trade: {e}")

    def update_strategy_prices(self, market: str, strategy_prices: Dict[str, dict]):
        """
        Update calculated prices for strategies for dashboard display.
        strategy_prices: dict like {'scarcity': {'price': 50.1, 'confidence': 85}, ...}
        """
        self.market_stats[market]['strategy_prices'] = strategy_prices
    
    def record_order_placed(self):
        """Increments order placement counter."""
        self.orders_placed += 1
    
    def record_order_cancelled(self):
        """Increments order cancellation counter."""
        self.orders_cancelled += 1

    def get_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        """
        Calculates unrealized P&L based on current market prices.
        current_prices: Dict of market -> current mid price
        """
        unrealized = 0.0
        for market, price in current_prices.items():
            base = market.split('_')[0]
            if self.inventory[base] > 0 and self.cost_basis[base] > 0:
                avg_cost = self.cost_basis[base] / self.inventory[base]
                unrealized += (price - avg_cost) * self.inventory[base]
        return unrealized

    def get_realized_pnl(self) -> float:
        """Returns total realized P&L (Iron received - Iron spent)."""
        return self.total_iron_received - self.total_iron_spent

    def get_summary(self) -> dict:
        """Returns a summary of all metrics."""
        runtime = time.time() - self.start_time
        
        # Calculate average spreads
        avg_spreads = {}
        for market, stats in self.market_stats.items():
            if stats['spreads_captured']:
                avg_spread = sum(s['spread_pct'] for s in stats['spreads_captured']) / len(stats['spreads_captured'])
                avg_spreads[market] = avg_spread
        
        return {
            'runtime_seconds': runtime,
            'runtime_formatted': self._format_duration(runtime),
            'total_trades': len(self.trades),
            'orders_placed': self.orders_placed,
            'orders_cancelled': self.orders_cancelled,
            'iron_spent': self.total_iron_spent,
            'iron_received': self.total_iron_received,
            'realized_pnl': self.get_realized_pnl(),
            'inventory': dict(self.inventory),
            'average_spreads_pct': avg_spreads,
            'market_stats': {k: dict(v) for k, v in self.market_stats.items()},
        }
    
    def print_summary(self):
        """Prints a formatted summary to the logger and saves metrics."""
        # Save before printing (ensures persistence on shutdown)
        self.save()
        
        summary = self.get_summary()
        
        logger.info("=" * 60)
        logger.info("📊 PERFORMANCE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Runtime: {summary['runtime_formatted']}")
        logger.info(f"Total Trades: {summary['total_trades']}")
        logger.info(f"Orders Placed: {summary['orders_placed']}")
        logger.info(f"Orders Cancelled: {summary['orders_cancelled']}")
        logger.info("-" * 40)
        logger.info(f"Iron Spent: {summary['iron_spent']:.4f}")
        logger.info(f"Iron Received: {summary['iron_received']:.4f}")
        logger.info(f"Realized P&L: {summary['realized_pnl']:+.4f} Iron")
        logger.info("-" * 40)
        
        if summary['inventory']:
            logger.info("Current Inventory:")
            for base, qty in summary['inventory'].items():
                if qty != 0:
                    logger.info(f"  {base}: {qty:.4f}")
        
        if summary['average_spreads_pct']:
            logger.info("-" * 40)
            logger.info("Average Spreads:")
            for market, spread in sorted(summary['average_spreads_pct'].items()):
                logger.info(f"  {market}: {spread:.2f}%")
        
        logger.info("=" * 60)
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Formats seconds into human-readable duration."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    def to_dict(self) -> dict:
        """Serializes metrics to a dictionary for JSON persistence."""
        # Helper to recursively convert deques/sets to lists
        stats_copy = {}
        for k, v in self.market_stats.items():
            stats_copy[k] = dict(v)
            if 'recent_trades' in stats_copy[k]:
                stats_copy[k]['recent_trades'] = list(stats_copy[k]['recent_trades'])

        return {
            'start_time': self.start_time,
            'inventory': dict(self.inventory),
            'cost_basis': dict(self.cost_basis),
            'trades': [asdict(t) for t in self.trades],
            'market_stats': stats_copy,
            'total_iron_spent': self.total_iron_spent,
            'total_iron_received': self.total_iron_received,
            'orders_placed': self.orders_placed,
            'orders_cancelled': self.orders_cancelled,
            'last_saved': time.time()
        }
    
    def _load(self):
        """Loads metrics from persistence file if it exists."""
        if not self.persistence_path or not os.path.exists(self.persistence_path):
            return
            
        try:
            with open(self.persistence_path, 'r') as f:
                data = json.load(f)
            
            # Restore state
            self.start_time = data.get('start_time', self.start_time)
            self.inventory = defaultdict(float, data.get('inventory', {}))
            self.cost_basis = defaultdict(float, data.get('cost_basis', {}))
            
            # Restore trades
            self.trades = [
                TradeRecord(**t) for t in data.get('trades', [])
            ]
            
            # Restore market stats
            for market, stats in data.get('market_stats', {}).items():
                # Backfill new keys for existing data
                if 'recent_trades' not in stats:
                    stats['recent_trades'] = deque(maxlen=50)
                if 'strategy_prices' not in stats:
                    stats['strategy_prices'] = {}
                else:
                    # Strategy prices might be loaded as dict, keep as is
                    pass
                
                # Ensure recent_trades is deque if loaded from list
                if isinstance(stats.get('recent_trades'), list):
                    stats['recent_trades'] = deque(stats['recent_trades'], maxlen=50)
                    
                self.market_stats[market] = stats
            
            self.total_iron_spent = data.get('total_iron_spent', 0.0)
            self.total_iron_received = data.get('total_iron_received', 0.0)
            self.orders_placed = data.get('orders_placed', 0)
            self.orders_cancelled = data.get('orders_cancelled', 0)
            
            logger.info(f"📂 Loaded metrics from {self.persistence_path} "
                       f"({len(self.trades)} trades, P&L: {self.get_realized_pnl():+.4f})")
                       
        except Exception as e:
            logger.warning(f"Could not load metrics from {self.persistence_path}: {e}")
    
    def save(self):
        """Saves metrics to persistence file."""
        if not self.persistence_path:
            return
            
        try:
            with open(self.persistence_path, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            self._last_save_time = time.time()
            logger.debug(f"💾 Metrics saved to {self.persistence_path}")
            
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def _maybe_auto_save(self):
        """Triggers auto-save if interval has passed or first activity detected."""
        if self.auto_save_interval <= 0:
            return
        
        # Force save on first activity (when we have orders and never saved)
        first_activity = self._never_saved and self.orders_placed > 0
            
        if first_activity or (time.time() - self._last_save_time >= self.auto_save_interval):
            self._never_saved = False
            self.save()
