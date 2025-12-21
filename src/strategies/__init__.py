"""
Pricing strategies module for the Market Maker bot.
Provides multiple selectable pricing strategies.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass
import logging

if TYPE_CHECKING:
    from blocky import Blocky

logger = logging.getLogger(__name__)


@dataclass
class PriceResult:
    """Result of a price calculation."""
    mid_price: float
    confidence: float = 1.0  # 0-1 confidence in the price
    source: str = "unknown"


class PricingStrategy(ABC):
    """Abstract base class for pricing strategies."""
    
    name: str = "base"
    description: str = "Base pricing strategy"
    
    @abstractmethod
    def calculate_price(
        self,
        market: str,
        client: 'Blocky',
        **kwargs
    ) -> PriceResult:
        """
        Calculate the fair/mid price for a market.
        
        Args:
            market: Market symbol (e.g., 'diam_iron')
            client: Blocky API client
            **kwargs: Additional strategy-specific parameters
            
        Returns:
            PriceResult with calculated price
        """
        pass


class ScarcityStrategy(PricingStrategy):
    """
    Price based on world scarcity model.
    
    Formula: fair_price = base_price × (total_supply / remaining_supply)
    """
    
    name = "scarcity"
    description = "Price based on remaining world supply scarcity"
    
    def __init__(self, base_prices: Optional[Dict[str, float]] = None):
        self.base_prices = base_prices or {
            "diam_iron": 50.0,
            "gold_iron": 5.0,
            "coal_iron": 0.5,
            "ston_iron": 0.1,
        }
        self._supply_cache: Dict = {}
    
    def calculate_price(
        self,
        market: str,
        client: 'Blocky',
        **kwargs
    ) -> PriceResult:
        base_price = self.base_prices.get(market, 1.0)
        
        # Try to get supply metrics
        try:
            circulating = self._get_circulating(market, client)
            total = 1000000  # Estimated world supply
            
            if circulating > 0 and circulating < total:
                remaining = total - circulating
                multiplier = min(total / remaining, 10.0)  # Cap at 10x
                return PriceResult(
                    mid_price=base_price * multiplier,
                    confidence=0.8,
                    source="scarcity"
                )
        except Exception as e:
            logger.debug(f"Scarcity calculation failed: {e}")
        
        return PriceResult(mid_price=base_price, confidence=0.5, source="base_fallback")
    
    def _get_circulating(self, market: str, client: 'Blocky') -> int:
        # Simplified - would use cached supply metrics
        return 0


class TickerStrategy(PricingStrategy):
    """
    Price based on current market ticker.
    Uses midpoint of bid/ask as fair price.
    """
    
    name = "ticker"
    description = "Price based on current bid/ask midpoint"
    
    def calculate_price(
        self,
        market: str,
        client: 'Blocky',
        ticker: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> PriceResult:
        try:
            if not ticker:
                ticker = client.get_ticker(market)
            
            bid = float(ticker.get("bid", 0) or 0)
            ask = float(ticker.get("ask", 0) or 0)
            close = float(ticker.get("close", 0) or 0)
            
            if bid > 0 and ask > 0:
                mid_price = (bid + ask) / 2
                return PriceResult(mid_price=mid_price, confidence=0.9, source="ticker_mid")
            elif close > 0:
                return PriceResult(mid_price=close, confidence=0.7, source="ticker_close")
                
        except Exception as e:
            logger.debug(f"Ticker strategy failed: {e}")
        
        return PriceResult(mid_price=0, confidence=0, source="ticker_failed")


class VWAPStrategy(PricingStrategy):
    """
    Price based on Volume Weighted Average Price.
    Uses recent trade data to calculate VWAP.
    """
    
    name = "vwap"
    description = "Volume-weighted average price from recent trades"
    
    def __init__(self, lookback_hours: int = 1):
        self.lookback_hours = lookback_hours
    
    def calculate_price(
        self,
        market: str,
        client: 'Blocky',
        **kwargs
    ) -> PriceResult:
        try:
            # Get OHLCV data
            response = client.get_ohlcv(market, timeframe="1H", limit=self.lookback_hours)
            
            if not response.get("success"):
                return PriceResult(mid_price=0, confidence=0, source="vwap_failed")
            
            candles = response.get("candles", [])
            if not candles:
                return PriceResult(mid_price=0, confidence=0, source="vwap_no_data")
            
            # Calculate VWAP
            total_pv = 0.0  # price × volume
            total_v = 0.0   # volume
            
            for candle in candles:
                # Typical price: (high + low + close) / 3
                high = float(candle.get("high", 0) or 0)
                low = float(candle.get("low", 0) or 0)
                close = float(candle.get("close", 0) or 0)
                volume = float(candle.get("volume", 0) or 0)
                
                if volume > 0:
                    typical_price = (high + low + close) / 3
                    total_pv += typical_price * volume
                    total_v += volume
            
            if total_v > 0:
                vwap = total_pv / total_v
                confidence = min(0.95, 0.5 + (len(candles) / 48))  # More data = more confidence
                return PriceResult(mid_price=vwap, confidence=confidence, source="vwap")
                
        except Exception as e:
            logger.debug(f"VWAP strategy failed: {e}")
        
        return PriceResult(mid_price=0, confidence=0, source="vwap_failed")


class CompositeStrategy(PricingStrategy):
    """
    Combines multiple strategies with weighted averaging.
    Falls back through strategies until one succeeds.
    """
    
    name = "composite"
    description = "Weighted combination of multiple strategies"
    
    def __init__(self, strategies: Optional[list] = None):
        self.strategies = strategies or [
            (ScarcityStrategy(), 0.4),
            (TickerStrategy(), 0.4),
            (VWAPStrategy(), 0.2),
        ]
    
    def calculate_price(
        self,
        market: str,
        client: 'Blocky',
        **kwargs
    ) -> PriceResult:
        total_weighted_price = 0.0
        total_weight = 0.0
        sources = []
        
        for strategy, weight in self.strategies:
            try:
                result = strategy.calculate_price(market, client, **kwargs)
                
                if result.mid_price > 0 and result.confidence > 0:
                    adjusted_weight = weight * result.confidence
                    total_weighted_price += result.mid_price * adjusted_weight
                    total_weight += adjusted_weight
                    sources.append(f"{strategy.name}:{result.confidence:.2f}")
                    
            except Exception as e:
                logger.debug(f"Composite sub-strategy {strategy.name} failed: {e}")
        
        if total_weight > 0:
            final_price = total_weighted_price / total_weight
            return PriceResult(
                mid_price=final_price,
                confidence=min(total_weight, 1.0),
                source="+".join(sources)
            )
        
        return PriceResult(mid_price=0, confidence=0, source="composite_failed")


# Strategy registry
STRATEGIES: Dict[str, type] = {
    "scarcity": ScarcityStrategy,
    "ticker": TickerStrategy,
    "vwap": VWAPStrategy,
    "composite": CompositeStrategy,
}


def get_strategy(name: str, **kwargs) -> PricingStrategy:
    """
    Get a pricing strategy by name.
    
    Args:
        name: Strategy name (scarcity, ticker, vwap, composite)
        **kwargs: Strategy-specific configuration
        
    Returns:
        Configured PricingStrategy instance
    """
    if name not in STRATEGIES:
        logger.warning(f"Unknown strategy '{name}', using scarcity")
        name = "scarcity"
    
    return STRATEGIES[name](**kwargs)
