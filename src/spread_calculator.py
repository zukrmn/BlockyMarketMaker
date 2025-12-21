"""
Dynamic spread calculator for the Market Maker bot.
Calculates optimal spreads based on volatility, inventory position, and competition.
"""
import logging
import time
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class SpreadConfig:
    """Configuration for dynamic spread calculation."""
    enabled: bool = True
    base_spread: float = 0.03          # 3% base spread
    volatility_multiplier: float = 2.0  # How much volatility affects spread
    inventory_impact: float = 0.02      # Max adjustment from inventory imbalance
    min_spread: float = 0.01            # 1% minimum spread
    max_spread: float = 0.15            # 15% maximum spread
    volatility_window: int = 24         # Hours of OHLCV data to consider


class SpreadCalculator:
    """
    Calculates dynamic spreads based on market conditions.
    
    Spread Formula:
        spread = base_spread + volatility_adjustment + inventory_adjustment
        
    Where:
        - volatility_adjustment = normalized_volatility * volatility_multiplier
        - inventory_adjustment = (inventory_ratio - 0.5) * inventory_impact
          (positive: buy spread wider, sell spread tighter when overstocked)
    """
    
    def __init__(self, client, config: SpreadConfig = None):
        """
        Initialize SpreadCalculator.
        
        Args:
            client: Blocky API client for fetching OHLCV data.
            config: SpreadConfig with calculation parameters.
        """
        self.client = client
        self.config = config or SpreadConfig()
        
        # Cache for volatility calculations
        self._volatility_cache: Dict[str, float] = {}
        self._volatility_cache_time: Dict[str, float] = {}
        self._cache_ttl = 300  # 5 minutes
        
        # Price history for quick volatility estimates
        self._price_history: Dict[str, deque] = {}
        self._max_history = 100
        
    async def calculate_volatility(self, market: str) -> float:
        """
        Calculate historical volatility for a market.
        
        Uses OHLCV data to compute standard deviation of returns.
        Returns normalized volatility (0.0 to 1.0 scale).
        """
        now = time.time()
        
        # Check cache
        if market in self._volatility_cache:
            cache_age = now - self._volatility_cache_time.get(market, 0)
            if cache_age < self._cache_ttl:
                return self._volatility_cache[market]
        
        try:
            # Fetch OHLCV data (1 hour candles, last 24 hours) - Async
            response = await self.client.get_ohlcv(market, timeframe="1H")
            
            if not response.get("success"):
                logger.debug(f"{market}: Failed to fetch OHLCV for volatility")
                return 0.0
            
            candles = response.get("candles", [])
            if len(candles) < 2:
                return 0.0
            
            # Calculate returns
            closes = [float(c.get("close", c.get("c", 0))) for c in candles if c.get("close") or c.get("c")]
            if len(closes) < 2:
                return 0.0
            
            # Calculate percentage returns
            returns = []
            for i in range(1, len(closes)):
                if closes[i-1] > 0:
                    ret = (closes[i] - closes[i-1]) / closes[i-1]
                    returns.append(ret)
            
            if not returns:
                return 0.0
            
            # Standard deviation of returns
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            std_dev = variance ** 0.5
            
            # Normalize to 0-1 range (assuming 20% daily std dev is "max")
            # Hourly std dev * sqrt(24) ≈ daily std dev
            hourly_to_daily = (24 ** 0.5)
            daily_vol = std_dev * hourly_to_daily
            normalized_vol = min(daily_vol / 0.20, 1.0)  # Cap at 1.0
            
            # Cache result
            self._volatility_cache[market] = normalized_vol
            self._volatility_cache_time[market] = now
            
            logger.debug(f"{market}: Volatility = {normalized_vol:.2%}")
            return normalized_vol
            
        except Exception as e:
            logger.warning(f"{market}: Error calculating volatility: {e}")
            return 0.0
    
    def update_price(self, market: str, price: float):
        """
        Update price history for quick volatility estimates.
        Called on each trade/ticker update for real-time adjustment.
        """
        if market not in self._price_history:
            self._price_history[market] = deque(maxlen=self._max_history)
        
        self._price_history[market].append(price)
    
    def get_quick_volatility(self, market: str) -> float:
        """
        Quick volatility estimate from recent price history.
        Used between OHLCV cache updates.
        """
        if market not in self._price_history or len(self._price_history[market]) < 5:
            return self._volatility_cache.get(market, 0.0)
        
        prices = list(self._price_history[market])
        
        # Simple volatility: range / mean
        mean_price = sum(prices) / len(prices)
        if mean_price == 0:
            return 0.0
        
        price_range = max(prices) - min(prices)
        quick_vol = price_range / mean_price
        
        # Blend with cached OHLCV volatility (70% OHLCV, 30% quick)
        cached_vol = self._volatility_cache.get(market, 0.0)
        return cached_vol * 0.7 + quick_vol * 0.3
    
    def calculate_inventory_adjustment(
        self, 
        market: str, 
        inventory: float,
        target_inventory: float = 0.0
    ) -> Tuple[float, float]:
        """
        Calculate buy/sell spread adjustments based on inventory position.
        
        Returns:
            (buy_adjustment, sell_adjustment) - positive values widen spread
            
        Logic:
            - Overstocked (inventory > target): widen buy spread, tighten sell spread
            - Understocked (inventory < target): tighten buy spread, widen sell spread
        """
        if target_inventory == 0:
            # Default: neutral position
            target_inventory = 0
        
        # Calculate imbalance (-1 to +1)
        # Positive = overstocked, negative = understocked
        if abs(inventory) < 0.01:
            imbalance = 0.0
        else:
            # Normalize: If inventory >> target, imbalance -> 1
            # Use sigmoid-like function to cap at +/- 1
            diff = inventory - target_inventory
            max_inventory = max(abs(inventory), abs(target_inventory), 1.0) * 10
            imbalance = max(-1.0, min(1.0, diff / max_inventory))
        
        impact = self.config.inventory_impact
        
        # Overstocked: widen buy (discourage buying), tighten sell (encourage selling)
        buy_adj = imbalance * impact      # Positive when overstocked
        sell_adj = -imbalance * impact    # Negative when overstocked (tighter)
        
        return (buy_adj, sell_adj)
    
    def get_competitor_spread(self, ticker: dict) -> Optional[float]:
        """
        Extract competitor spread from ticker data.
        
        Returns the current bid/ask spread percentage, or None if unavailable.
        """
        if not ticker:
            return None
        
        bid = float(ticker.get("bid", 0) or 0)
        ask = float(ticker.get("ask", 0) or 0)
        
        if bid <= 0 or ask <= 0:
            return None
        
        spread = (ask - bid) / bid
        return spread
    
    async def get_dynamic_spread(
        self,
        market: str,
        inventory: float = 0.0,
        ticker: dict = None,
        use_cache: bool = True
    ) -> Tuple[float, float]:
        """
        Calculate dynamic buy and sell spreads for a market.
        
        Args:
            market: Market symbol (e.g., 'diam_iron')
            inventory: Current inventory of base asset
            ticker: Current ticker data (for competitor spread)
            use_cache: Whether to use cached volatility
            
        Returns:
            (buy_spread, sell_spread) - as percentages (0.05 = 5%)
        """
        if not self.config.enabled:
            # Return fixed spread if dynamic is disabled
            return (self.config.base_spread, self.config.base_spread)
        
        # 1. Base spread
        base = self.config.base_spread
        
        # 2. Volatility adjustment
        if use_cache:
            vol = self.get_quick_volatility(market)
        else:
            vol = await self.calculate_volatility(market)
        
        vol_adj = vol * self.config.volatility_multiplier * 0.01  # Convert to spread %
        
        # 3. Inventory adjustment
        buy_inv_adj, sell_inv_adj = self.calculate_inventory_adjustment(market, inventory)
        
        # 4. Combine
        buy_spread = base + vol_adj + buy_inv_adj
        sell_spread = base + vol_adj + sell_inv_adj
        
        # 5. Clamp to min/max
        buy_spread = max(self.config.min_spread, min(self.config.max_spread, buy_spread))
        sell_spread = max(self.config.min_spread, min(self.config.max_spread, sell_spread))
        
        logger.debug(
            f"{market}: Dynamic spread - buy={buy_spread:.2%}, sell={sell_spread:.2%} "
            f"(vol={vol:.2f}, inv_adj=({buy_inv_adj:+.3f}, {sell_inv_adj:+.3f}))"
        )
        
        return (buy_spread, sell_spread)
    
    def warm_cache(self, markets: list):
        """
        Pre-calculate volatility for all markets (call on startup).
        """
        logger.info(f"Warming volatility cache for {len(markets)} markets...")
        for market in markets:
            try:
                self.calculate_volatility(market)
            except Exception as e:
                logger.debug(f"{market}: Warmup failed: {e}")
        logger.info("Volatility cache warmed.")
