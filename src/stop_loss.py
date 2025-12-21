"""
Stop-loss module for the Market Maker bot.
Monitors P&L and automatically pauses trading if losses exceed threshold.
"""
import asyncio
import logging
import time
from typing import TYPE_CHECKING, Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

if TYPE_CHECKING:
    from metrics import MetricsTracker

logger = logging.getLogger(__name__)


class StopLossState(Enum):
    """Stop-loss states."""
    ACTIVE = "active"      # Trading normally
    TRIGGERED = "triggered"  # Stop-loss triggered, orders cancelled
    COOLDOWN = "cooldown"   # In cooldown period
    DISABLED = "disabled"   # Stop-loss system disabled


@dataclass
class StopLossConfig:
    """Stop-loss configuration."""
    enabled: bool = True
    max_drawdown: float = 100.0  # Maximum loss in Iron before triggering
    max_drawdown_percent: float = 0.10  # Maximum loss as percentage of capital (10%)
    cooldown_seconds: int = 300  # 5 minutes cooldown after trigger
    check_interval: int = 30  # Check P&L every 30 seconds


class StopLoss:
    """
    Automatic stop-loss system.
    
    Monitors realized and unrealized P&L and triggers protective measures
    when losses exceed configurable thresholds.
    """
    
    def __init__(
        self,
        metrics: 'MetricsTracker',
        config: Optional[StopLossConfig] = None,
        on_trigger: Optional[Callable[[], Awaitable[None]]] = None
    ):
        """
        Initialize stop-loss system.
        
        Args:
            metrics: MetricsTracker instance for P&L data
            config: Stop-loss configuration
            on_trigger: Async callback to execute when stop-loss triggers
        """
        self.metrics = metrics
        self.config = config or StopLossConfig()
        self.on_trigger = on_trigger
        
        self.state = StopLossState.ACTIVE if self.config.enabled else StopLossState.DISABLED
        self.trigger_time: Optional[float] = None
        self.trigger_reason: Optional[str] = None
        
        # Track initial capital for percentage-based stop-loss
        self.initial_capital: float = 0.0
        self.highest_equity: float = 0.0
        
        # Monitoring task
        self._monitor_task: Optional[asyncio.Task] = None
    
    def set_initial_capital(self, capital: float) -> None:
        """Set initial capital for percentage calculations."""
        self.initial_capital = capital
        self.highest_equity = capital
        logger.info(f"🛡️ Stop-loss initialized with capital: {capital:.2f}")
    
    async def start_monitoring(self) -> None:
        """Start the P&L monitoring loop."""
        if not self.config.enabled:
            logger.info("Stop-loss system disabled")
            return
        
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"🛡️ Stop-loss monitoring started (max drawdown: {self.config.max_drawdown:.2f})")
    
    async def stop_monitoring(self) -> None:
        """Stop the monitoring loop."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while True:
            try:
                await asyncio.sleep(self.config.check_interval)
                
                if self.state == StopLossState.COOLDOWN:
                    self._check_cooldown()
                    continue
                
                if self.state == StopLossState.ACTIVE:
                    await self._check_stop_loss()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stop-loss monitor error: {e}")
    
    async def _check_stop_loss(self) -> None:
        """Check if stop-loss conditions are met."""
        realized_pnl = self.metrics.realized_pnl
        unrealized_pnl = self.metrics.get_unrealized_pnl()
        total_pnl = realized_pnl + unrealized_pnl
        
        # Update highest equity (for drawdown calculation)
        current_equity = self.initial_capital + total_pnl
        if current_equity > self.highest_equity:
            self.highest_equity = current_equity
        
        # Check absolute loss
        if total_pnl < -self.config.max_drawdown:
            await self._trigger_stop_loss(
                f"Total P&L ({total_pnl:.2f}) exceeded max drawdown ({-self.config.max_drawdown:.2f})"
            )
            return
        
        # Check percentage loss
        if self.initial_capital > 0:
            loss_percent = abs(total_pnl) / self.initial_capital
            if total_pnl < 0 and loss_percent > self.config.max_drawdown_percent:
                await self._trigger_stop_loss(
                    f"Loss ({loss_percent:.1%}) exceeded max ({self.config.max_drawdown_percent:.1%})"
                )
                return
        
        # Check drawdown from peak
        if self.highest_equity > 0:
            drawdown = (self.highest_equity - current_equity) / self.highest_equity
            if drawdown > self.config.max_drawdown_percent:
                await self._trigger_stop_loss(
                    f"Drawdown ({drawdown:.1%}) from peak ({self.highest_equity:.2f})"
                )
    
    async def _trigger_stop_loss(self, reason: str) -> None:
        """Trigger stop-loss protection."""
        self.state = StopLossState.TRIGGERED
        self.trigger_time = time.time()
        self.trigger_reason = reason
        
        logger.warning(f"🛑 STOP-LOSS TRIGGERED: {reason}")
        
        # Execute callback (e.g., cancel all orders)
        if self.on_trigger:
            try:
                await self.on_trigger()
            except Exception as e:
                logger.error(f"Stop-loss callback error: {e}")
        
        # Enter cooldown
        self.state = StopLossState.COOLDOWN
        logger.info(f"⏳ Entering cooldown for {self.config.cooldown_seconds}s")
    
    def _check_cooldown(self) -> None:
        """Check if cooldown period has elapsed."""
        if self.trigger_time is None:
            self.state = StopLossState.ACTIVE
            return
        
        elapsed = time.time() - self.trigger_time
        if elapsed >= self.config.cooldown_seconds:
            self.state = StopLossState.ACTIVE
            self.trigger_time = None
            self.trigger_reason = None
            logger.info("✅ Stop-loss cooldown ended, resuming trading")
    
    def should_trade(self) -> bool:
        """Check if trading is allowed."""
        return self.state == StopLossState.ACTIVE
    
    def get_status(self) -> dict:
        """Get current stop-loss status."""
        return {
            "state": self.state.value,
            "enabled": self.config.enabled,
            "max_drawdown": self.config.max_drawdown,
            "max_drawdown_percent": self.config.max_drawdown_percent,
            "trigger_time": self.trigger_time,
            "trigger_reason": self.trigger_reason,
            "initial_capital": self.initial_capital,
            "highest_equity": self.highest_equity,
        }
