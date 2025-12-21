"""
Backtesting module for the Market Maker bot.
Simulates strategy performance using historical OHLCV data.
"""
import time
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from config import get_config

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """OHLCV candle data."""
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class SimulatedOrder:
    """Represents a simulated order in backtesting."""
    id: int
    market: str
    side: str  # 'buy' or 'sell'
    price: float
    quantity: float
    timestamp: float
    filled: bool = False
    fill_price: float = 0.0
    fill_timestamp: float = 0.0


@dataclass
class BacktestResult:
    """Results of a backtest run."""
    start_time: float
    end_time: float
    initial_capital: float
    final_capital: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    markets_traded: List[str]
    trades: List[Dict]
    
    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades
    
    @property
    def return_pct(self) -> float:
        if self.initial_capital == 0:
            return 0.0
        return (self.final_capital - self.initial_capital) / self.initial_capital * 100


class BacktestEngine:
    """
    Simple backtesting engine for market making strategies.
    
    Usage:
        engine = BacktestEngine(initial_capital=1000.0)
        
        # Load historical data
        engine.load_candles('diam_iron', candles_list)
        
        # Run backtest with strategy parameters
        result = engine.run(spread=0.05, target_value=10.0)
        
        # Print results
        engine.print_summary(result)
    """
    
    def __init__(self, initial_capital: float = 1000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.inventory: Dict[str, float] = defaultdict(float)
        self.candles: Dict[str, List[Candle]] = {}
        self.orders: List[SimulatedOrder] = []
        self.trades: List[Dict] = []
        self._order_id = 0
    
    def load_candles(self, market: str, candles: List[Dict]):
        """
        Load candle data for a market.
        
        Args:
            market: Market symbol (e.g., 'diam_iron')
            candles: List of candle dicts with keys: timestamp, open, high, low, close, volume
        """
        self.candles[market] = [
            Candle(
                timestamp=c.get('timestamp', c.get('time', 0)),
                open=float(c.get('open', c.get('o', 0))),
                high=float(c.get('high', c.get('h', 0))),
                low=float(c.get('low', c.get('l', 0))),
                close=float(c.get('close', c.get('c', 0))),
                volume=float(c.get('volume', c.get('v', 0)))
            )
            for c in candles
        ]
        logger.info(f"Loaded {len(candles)} candles for {market}")
    
    def fetch_candles_from_api(self, client, market: str, timeframe: str = "1H", 
                                limit: int = 1000) -> List[Candle]:
        """
        Fetch candles from Blocky API.
        
        Args:
            client: Blocky client instance
            market: Market symbol
            timeframe: Candle timeframe (1m, 5m, 15m, 1H, 4H, 1D)
            limit: Maximum candles to fetch
        """
        try:
            response = client.get_ohlcv(market, timeframe=timeframe)
            if response.get('success') and 'candles' in response:
                self.load_candles(market, response['candles'][:limit])
                return self.candles.get(market, [])
        except Exception as e:
            logger.error(f"Failed to fetch candles for {market}: {e}")
        return []
    
    def _simulate_fill(self, order: SimulatedOrder, candle: Candle) -> bool:
        """Check if order would be filled during candle."""
        if order.side == 'buy':
            # Buy order fills if price drops to or below order price
            if candle.low <= order.price:
                order.filled = True
                order.fill_price = order.price  # Assume limit fill
                order.fill_timestamp = candle.timestamp
                return True
        else:
            # Sell order fills if price rises to or above order price
            if candle.high >= order.price:
                order.filled = True
                order.fill_price = order.price
                order.fill_timestamp = candle.timestamp
                return True
        return False
    
    def run(self, spread: float = None, target_value: float = None,
            min_spread_ticks: float = None) -> BacktestResult:
        """
        Run backtest simulation.
        
        Args:
            spread: Spread percentage (0.05 = 5%). Defaults to config value.
            target_value: Target order value. Defaults to config value.
            min_spread_ticks: Minimum spread in price units. Defaults to config value.
            
        Returns:
            BacktestResult with performance metrics
        """
        # Load defaults from config if not provided
        cfg = get_config()
        if spread is None:
            spread = cfg.trading.spread
        if target_value is None:
            target_value = cfg.trading.target_value
        if min_spread_ticks is None:
            min_spread_ticks = cfg.trading.min_spread_ticks
        
        logger.info(f"Backtest params: spread={spread}, target_value={target_value}, min_spread_ticks={min_spread_ticks}")
        self.capital = self.initial_capital
        self.inventory.clear()
        self.orders.clear()
        self.trades.clear()
        self._order_id = 0
        
        if not self.candles:
            logger.warning("No candle data loaded. Call load_candles() first.")
            return self._empty_result()
        
        # Find common time range across all markets
        all_timestamps = set()
        for market, candles in self.candles.items():
            for c in candles:
                all_timestamps.add(c.timestamp)
        
        if not all_timestamps:
            return self._empty_result()
        
        sorted_timestamps = sorted(all_timestamps)
        start_time = sorted_timestamps[0]
        end_time = sorted_timestamps[-1]
        
        equity_curve = [self.initial_capital]
        max_equity = self.initial_capital
        max_drawdown = 0.0
        
        # Simulate each time period
        for ts in sorted_timestamps:
            for market, candles in self.candles.items():
                # Find candle for this timestamp
                candle = next((c for c in candles if c.timestamp == ts), None)
                if not candle:
                    continue
                
                # Check existing orders for fills
                active_orders = [o for o in self.orders if not o.filled and o.market == market]
                for order in active_orders:
                    if self._simulate_fill(order, candle):
                        self._process_fill(order)
                
                # Place new orders based on current price
                mid_price = (candle.high + candle.low) / 2
                buy_price = round(mid_price * (1 - spread / 2), 2)
                sell_price = round(mid_price * (1 + spread / 2), 2)
                
                # Enforce minimum spread
                if sell_price - buy_price < min_spread_ticks:
                    buy_price = round(mid_price - min_spread_ticks / 2, 2)
                    sell_price = round(mid_price + min_spread_ticks / 2, 2)
                
                # Calculate quantity
                if buy_price > 0:
                    quantity = min(target_value / buy_price, 6400)
                else:
                    quantity = 0
                
                base = market.split('_')[0]
                
                # Place buy order if we have capital
                buy_cost = buy_price * quantity
                if self.capital >= buy_cost and quantity > 0:
                    if not any(o.market == market and o.side == 'buy' and not o.filled 
                              for o in self.orders):
                        self._place_order(market, 'buy', buy_price, quantity, ts)
                
                # Place sell order if we have inventory
                if self.inventory[base] >= quantity and quantity > 0:
                    if not any(o.market == market and o.side == 'sell' and not o.filled
                              for o in self.orders):
                        self._place_order(market, 'sell', sell_price, quantity, ts)
            
            # Calculate current equity
            current_equity = self.capital
            for base, qty in self.inventory.items():
                # Estimate inventory value using last known price
                for market, candles in self.candles.items():
                    if market.startswith(base):
                        last_candle = next((c for c in reversed(candles) if c.timestamp <= ts), None)
                        if last_candle:
                            current_equity += qty * last_candle.close
                            break
            
            equity_curve.append(current_equity)
            if current_equity > max_equity:
                max_equity = current_equity
            drawdown = (max_equity - current_equity) / max_equity if max_equity > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Calculate final metrics
        winning = sum(1 for t in self.trades if t.get('pnl', 0) > 0)
        losing = sum(1 for t in self.trades if t.get('pnl', 0) < 0)
        total_pnl = sum(t.get('pnl', 0) for t in self.trades)
        
        # Simple Sharpe approximation
        if len(equity_curve) > 1:
            returns = [(equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1] 
                      for i in range(1, len(equity_curve)) if equity_curve[i-1] > 0]
            if returns:
                import statistics
                avg_return = statistics.mean(returns)
                std_return = statistics.stdev(returns) if len(returns) > 1 else 1
                sharpe = avg_return / std_return * (len(returns) ** 0.5) if std_return > 0 else 0
            else:
                sharpe = 0
        else:
            sharpe = 0
        
        return BacktestResult(
            start_time=start_time,
            end_time=end_time,
            initial_capital=self.initial_capital,
            final_capital=self.capital + sum(self.inventory.values()),  # Simplified
            total_trades=len(self.trades),
            winning_trades=winning,
            losing_trades=losing,
            total_pnl=total_pnl,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            markets_traded=list(self.candles.keys()),
            trades=self.trades
        )
    
    def _place_order(self, market: str, side: str, price: float, 
                     quantity: float, timestamp: float):
        """Place a simulated order."""
        self._order_id += 1
        order = SimulatedOrder(
            id=self._order_id,
            market=market,
            side=side,
            price=price,
            quantity=quantity,
            timestamp=timestamp
        )
        self.orders.append(order)
    
    def _process_fill(self, order: SimulatedOrder):
        """Process a filled order."""
        base = order.market.split('_')[0]
        value = order.fill_price * order.quantity
        
        if order.side == 'buy':
            self.capital -= value
            self.inventory[base] += order.quantity
        else:
            self.capital += value
            self.inventory[base] -= order.quantity
        
        # Record trade
        self.trades.append({
            'order_id': order.id,
            'market': order.market,
            'side': order.side,
            'price': order.fill_price,
            'quantity': order.quantity,
            'value': value,
            'timestamp': order.fill_timestamp,
            'pnl': value if order.side == 'sell' else -value
        })
    
    def _empty_result(self) -> BacktestResult:
        """Return empty result for failed backtest."""
        return BacktestResult(
            start_time=0, end_time=0,
            initial_capital=self.initial_capital,
            final_capital=self.initial_capital,
            total_trades=0, winning_trades=0, losing_trades=0,
            total_pnl=0, max_drawdown=0, sharpe_ratio=0,
            markets_traded=[], trades=[]
        )
    
    def print_summary(self, result: BacktestResult):
        """Print a formatted backtest summary."""
        print("=" * 60)
        print("📊 BACKTEST RESULTS")
        print("=" * 60)
        print(f"Period: {time.strftime('%Y-%m-%d', time.localtime(result.start_time))} to "
              f"{time.strftime('%Y-%m-%d', time.localtime(result.end_time))}")
        print(f"Markets: {', '.join(result.markets_traded)}")
        print("-" * 40)
        print(f"Initial Capital: {result.initial_capital:.2f} Iron")
        print(f"Final Capital:   {result.final_capital:.2f} Iron")
        print(f"Total P&L:       {result.total_pnl:+.2f} Iron ({result.return_pct:+.2f}%)")
        print("-" * 40)
        print(f"Total Trades:    {result.total_trades}")
        print(f"Win Rate:        {result.win_rate*100:.1f}%")
        print(f"Max Drawdown:    {result.max_drawdown*100:.2f}%")
        print(f"Sharpe Ratio:    {result.sharpe_ratio:.2f}")
        print("=" * 60)


if __name__ == "__main__":
    # Example usage
    print("Backtesting module loaded.")
    print("Usage:")
    print("  engine = BacktestEngine(initial_capital=1000)")
    print("  engine.load_candles('diam_iron', [{'open': 50, 'high': 52, 'low': 49, 'close': 51, 'volume': 100, 'timestamp': 1234567890}])")
    print("  result = engine.run(spread=0.05)")
    print("  engine.print_summary(result)")
