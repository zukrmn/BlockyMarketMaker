"""
Dynamic Capital Allocation Module

Implements portfolio management principles for optimal capital distribution
across multiple markets with reserve management.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class AllocationConfig:
    """Configuration for capital allocation."""
    enabled: bool = True
    base_reserve_ratio: float = 0.10  # Minimum 10% reserve
    max_reserve_ratio: float = 0.30   # Maximum 30% reserve
    min_order_value: float = 0.10     # Minimum order value in Iron
    priority_markets: List[str] = None
    priority_boost: float = 1.5       # 50% more allocation for priority markets
    
    def __post_init__(self):
        if self.priority_markets is None:
            self.priority_markets = []


class CapitalAllocator:
    """
    Dynamic capital allocation based on portfolio management principles.
    
    Key Features:
    - Automatic reserve calculation based on market count
    - Equal-weight base allocation with priority boosting
    - Minimum order value enforcement
    - Real-time recalculation as capital changes
    
    Mathematical Foundation:
        Reserve Ratio = base_reserve + (num_markets / 100)
        Deployable = Total Capital × (1 - Reserve Ratio)
        Per Market = Deployable / num_markets (with priority weighting)
    """
    
    def __init__(self, config: AllocationConfig = None):
        self.config = config or AllocationConfig()
        self._last_allocation: Dict[str, float] = {}
        self._last_reserve: float = 0
    
    def calculate_reserve_ratio(self, num_markets: int) -> float:
        """
        Calculate dynamic reserve ratio based on market count.
        
        Formula: reserve = base + (markets / 100)
        Clamped between base and max.
        
        Rationale: More markets = more exposure = more reserve needed
        """
        base = self.config.base_reserve_ratio
        max_reserve = self.config.max_reserve_ratio
        
        # Add 1% per 10 markets
        dynamic = base + (num_markets / 100)
        
        return min(max_reserve, max(base, dynamic))
    
    def calculate_allocation(
        self, 
        total_capital: float, 
        num_markets: int,
        locked_capital: float = 0,
        priority_markets: List[str] = None
    ) -> Tuple[float, float, float]:
        """
        Calculate per-market allocation and reserve.
        
        Args:
            total_capital: Total Iron available (wallet + locked in orders)
            num_markets: Number of active markets
            locked_capital: Iron currently locked in existing orders
            priority_markets: Markets that get boosted allocation (optional)
            
        Returns:
            Tuple of (base_target_value, reserve_amount, deployable_capital)
        """
        if total_capital <= 0 or num_markets <= 0:
            return 0.0, 0.0, 0.0
        
        # Calculate dynamic reserve
        reserve_ratio = self.calculate_reserve_ratio(num_markets)
        reserve = total_capital * reserve_ratio
        
        # Deployable capital (what we can use for orders)
        deployable = total_capital - reserve
        
        # Base allocation per market (equal weight)
        base_allocation = deployable / num_markets
        
        # Enforce minimum order value
        if base_allocation < self.config.min_order_value:
            # If we can't meet minimum, reduce market count
            effective_markets = int(deployable / self.config.min_order_value)
            if effective_markets > 0:
                base_allocation = deployable / effective_markets
                logger.warning(
                    f"Capital too low for {num_markets} markets. "
                    f"Effective markets: {effective_markets}"
                )
            else:
                base_allocation = 0
                logger.warning("Insufficient capital for any market orders")
        
        self._last_reserve = reserve
        
        return base_allocation, reserve, deployable
    
    def get_market_allocation(
        self,
        market: str,
        base_allocation: float,
        total_markets: int
    ) -> float:
        """
        Get allocation for a specific market with priority boosting.
        
        Priority markets get boosted allocation at the expense of others.
        """
        if base_allocation <= 0:
            return 0
        
        # Check if priority market
        if market in self.config.priority_markets:
            # Boost allocation
            boosted = base_allocation * self.config.priority_boost
            self._last_allocation[market] = boosted
            return boosted
        
        # Regular markets get base allocation
        # (In a more sophisticated version, we'd rebalance to keep total constant)
        self._last_allocation[market] = base_allocation
        return base_allocation
    
    def get_allocation_summary(
        self,
        total_capital: float,
        num_markets: int
    ) -> Dict[str, any]:
        """
        Get a summary of allocation for logging/debugging.
        """
        base, reserve, deployable = self.calculate_allocation(
            total_capital, num_markets
        )
        reserve_ratio = self.calculate_reserve_ratio(num_markets)
        
        return {
            "total_capital": total_capital,
            "reserve_ratio": f"{reserve_ratio:.1%}",
            "reserve_amount": reserve,
            "deployable": deployable,
            "num_markets": num_markets,
            "base_per_market": base,
            "priority_markets": self.config.priority_markets,
            "priority_boost": self.config.priority_boost,
        }
    
    def log_allocation(self, total_capital: float, num_markets: int) -> None:
        """Log current allocation settings."""
        summary = self.get_allocation_summary(total_capital, num_markets)
        
        logger.info(
            f"💰 Capital Allocation: {summary['total_capital']:.2f} Iron | "
            f"Reserve: {summary['reserve_ratio']} ({summary['reserve_amount']:.2f}) | "
            f"Per Market: {summary['base_per_market']:.2f} Iron"
        )


def create_allocator_from_config(config_dict: dict) -> CapitalAllocator:
    """
    Factory function to create allocator from config dictionary.
    
    Expected config structure:
    capital_allocation:
        enabled: true
        base_reserve_ratio: 0.10
        max_reserve_ratio: 0.30
        min_order_value: 0.10
        priority_markets: [diam_iron, gold_iron]
        priority_boost: 1.5
    """
    alloc_config = config_dict.get("capital_allocation", {})
    
    return CapitalAllocator(AllocationConfig(
        enabled=alloc_config.get("enabled", True),
        base_reserve_ratio=alloc_config.get("base_reserve_ratio", 0.10),
        max_reserve_ratio=alloc_config.get("max_reserve_ratio", 0.30),
        min_order_value=alloc_config.get("min_order_value", 0.10),
        priority_markets=alloc_config.get("priority_markets", []),
        priority_boost=alloc_config.get("priority_boost", 1.5),
    ))
