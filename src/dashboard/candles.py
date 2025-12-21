"""
ACMaker Dashboard - Candle Data Collector
Collects and stores historical price data for chart display
"""
import time
import logging
from typing import Dict, List, Optional, Any
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """Single candlestick data point."""
    time: int  # Unix timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "time": self.time,
            "open": round(self.open, 6),
            "high": round(self.high, 6),
            "low": round(self.low, 6),
            "close": round(self.close, 6),
            "volume": round(self.volume, 2)
        }


@dataclass
class CandleBuffer:
    """Buffer for accumulating ticks into candles."""
    interval: int  # seconds
    current_candle: Optional[Candle] = None
    candle_start_time: int = 0
    
    def add_tick(self, price: float, volume: float = 0.0) -> Optional[Candle]:
        """Add a price tick. Returns completed candle if interval elapsed."""
        now = int(time.time())
        candle_time = (now // self.interval) * self.interval
        
        if self.current_candle is None or candle_time != self.candle_start_time:
            # Start new candle, return previous if exists
            completed = self.current_candle
            self.current_candle = Candle(
                time=candle_time,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume
            )
            self.candle_start_time = candle_time
            return completed
        else:
            # Update current candle
            self.current_candle.high = max(self.current_candle.high, price)
            self.current_candle.low = min(self.current_candle.low, price)
            self.current_candle.close = price
            self.current_candle.volume += volume
            return None


class CandleCollector:
    """
    Collects price data and generates candles for multiple markets and timeframes.
    
    Usage:
        collector = CandleCollector()
        
        # When a trade or price update happens:
        collector.add_price("diam_iron", 50.25, volume=10.0)
        
        # Get candles for display:
        candles = collector.get_candles("diam_iron", "4H", count=50)
    """
    
    # Supported timeframes with their intervals in seconds
    TIMEFRAMES = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1H": 3600,
        "4H": 14400,
        "1D": 86400,
        "1W": 604800,
    }
    
    def __init__(self, max_candles: int = 500):
        """
        Initialize collector.
        
        Args:
            max_candles: Maximum candles to keep per market/timeframe
        """
        self.max_candles = max_candles
        
        # Storage: market -> timeframe -> list of candles
        self._candles: Dict[str, Dict[str, List[Candle]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        # Buffers for building candles: market -> timeframe -> buffer
        self._buffers: Dict[str, Dict[str, CandleBuffer]] = defaultdict(dict)
        
        # Last known price per market
        self._last_prices: Dict[str, float] = {}
    
    def add_price(self, market: str, price: float, volume: float = 0.0) -> None:
        """
        Add a price tick for a market.
        
        Args:
            market: Market identifier (e.g., "diam_iron")
            price: Current price
            volume: Trade volume (optional)
        """
        self._last_prices[market] = price
        
        # Update all timeframe buffers
        for tf_name, interval in self.TIMEFRAMES.items():
            if tf_name not in self._buffers[market]:
                self._buffers[market][tf_name] = CandleBuffer(interval=interval)
            
            buffer = self._buffers[market][tf_name]
            completed = buffer.add_tick(price, volume)
            
            if completed:
                candles = self._candles[market][tf_name]
                candles.append(completed)
                
                # Trim old candles
                if len(candles) > self.max_candles:
                    self._candles[market][tf_name] = candles[-self.max_candles:]
    
    def get_candles(
        self, 
        market: str, 
        timeframe: str = "4H", 
        count: int = 50
    ) -> List[dict]:
        """
        Get candle data for a market and timeframe.
        
        Args:
            market: Market identifier
            timeframe: Timeframe string (e.g., "1m", "4H", "1D")
            count: Number of candles to return
            
        Returns:
            List of candle dictionaries for chart display
        """
        if timeframe not in self.TIMEFRAMES:
            timeframe = "4H"
        
        candles = self._candles[market][timeframe]
        
        # Include current building candle if exists
        buffer = self._buffers.get(market, {}).get(timeframe)
        if buffer and buffer.current_candle:
            all_candles = candles + [buffer.current_candle]
        else:
            all_candles = candles
        
        # Return last N candles
        result = all_candles[-count:] if len(all_candles) > count else all_candles
        return [c.to_dict() for c in result]
    
    def get_last_price(self, market: str) -> Optional[float]:
        """Get last known price for a market."""
        return self._last_prices.get(market)
    
    def has_data(self, market: str) -> bool:
        """Check if we have any candle data for a market."""
        return market in self._candles and any(
            len(candles) > 0 
            for candles in self._candles[market].values()
        )
    
    def get_markets_with_data(self) -> List[str]:
        """Get list of markets that have candle data."""
        return [m for m in self._candles.keys() if self.has_data(m)]
    
    def clear(self, market: Optional[str] = None) -> None:
        """Clear candle data for a market or all markets."""
        if market:
            self._candles.pop(market, None)
            self._buffers.pop(market, None)
            self._last_prices.pop(market, None)
        else:
            self._candles.clear()
            self._buffers.clear()
            self._last_prices.clear()


# Global collector instance for easy access
_collector: Optional[CandleCollector] = None


def get_collector() -> CandleCollector:
    """Get or create the global candle collector instance."""
    global _collector
    if _collector is None:
        _collector = CandleCollector()
    return _collector
