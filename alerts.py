"""
Alert system for the Market Maker bot.
Supports webhook notifications (Discord, Slack, Telegram, custom HTTP).
"""
import os
import time
import logging
import requests
import threading
from typing import Optional, Callable, List
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Represents a single alert."""
    level: AlertLevel
    title: str
    message: str
    timestamp: float = field(default_factory=time.time)
    source: str = "MarketMaker"


class AlertManager:
    """
    Manages alerts and sends notifications via configured channels.
    
    Supports:
    - Discord webhooks
    - Slack webhooks
    - Telegram bot
    - Custom HTTP POST endpoints
    """
    
    def __init__(self, 
                 webhook_url: Optional[str] = None,
                 webhook_type: str = "discord",
                 min_level: AlertLevel = AlertLevel.WARNING,
                 rate_limit_seconds: float = 60.0):
        """
        Initialize AlertManager.
        
        Args:
            webhook_url: URL for webhook notifications.
            webhook_type: Type of webhook ("discord", "slack", "telegram", "custom").
            min_level: Minimum alert level to send (default: WARNING).
            rate_limit_seconds: Minimum seconds between alerts of same type.
        """
        self.webhook_url = webhook_url or os.environ.get("ALERT_WEBHOOK_URL")
        self.webhook_type = webhook_type
        self.min_level = min_level
        self.rate_limit_seconds = rate_limit_seconds
        
        self._last_alerts: dict = {}  # key -> timestamp (for rate limiting)
        self._lock = threading.Lock()
        self._history: List[Alert] = []
        
        # Level priority for comparison
        self._level_priority = {
            AlertLevel.INFO: 0,
            AlertLevel.WARNING: 1,
            AlertLevel.ERROR: 2,
            AlertLevel.CRITICAL: 3,
        }
        
        if self.webhook_url:
            logger.info(f"🔔 AlertManager initialized with {webhook_type} webhook")
        else:
            logger.info("🔔 AlertManager initialized (no webhook configured)")
    
    def _should_send(self, alert: Alert, rate_limit_key: str) -> bool:
        """Check if alert should be sent (level and rate limit)."""
        # Check level
        if self._level_priority[alert.level] < self._level_priority[self.min_level]:
            return False
        
        # Check rate limit
        with self._lock:
            last_time = self._last_alerts.get(rate_limit_key, 0)
            if time.time() - last_time < self.rate_limit_seconds:
                return False
            self._last_alerts[rate_limit_key] = time.time()
        
        return True
    
    def send(self, level: AlertLevel, title: str, message: str, 
             rate_limit_key: Optional[str] = None):
        """
        Send an alert if it passes level and rate limit checks.
        
        Args:
            level: Alert severity level.
            title: Short alert title.
            message: Detailed alert message.
            rate_limit_key: Key for rate limiting (defaults to title).
        """
        alert = Alert(level=level, title=title, message=message)
        self._history.append(alert)
        
        key = rate_limit_key or title
        if not self._should_send(alert, key):
            return
        
        # Log locally
        log_func = {
            AlertLevel.INFO: logger.info,
            AlertLevel.WARNING: logger.warning,
            AlertLevel.ERROR: logger.error,
            AlertLevel.CRITICAL: logger.critical,
        }.get(level, logger.info)
        
        log_func(f"🔔 [{level.value.upper()}] {title}: {message}")
        
        # Send to webhook (non-blocking)
        if self.webhook_url:
            threading.Thread(
                target=self._send_webhook,
                args=(alert,),
                daemon=True
            ).start()
    
    def _send_webhook(self, alert: Alert):
        """Send alert to configured webhook."""
        try:
            if self.webhook_type == "discord":
                self._send_discord(alert)
            elif self.webhook_type == "slack":
                self._send_slack(alert)
            elif self.webhook_type == "telegram":
                self._send_telegram(alert)
            else:
                self._send_custom(alert)
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
    
    def _send_discord(self, alert: Alert):
        """Send Discord webhook."""
        color_map = {
            AlertLevel.INFO: 3447003,      # Blue
            AlertLevel.WARNING: 16776960,  # Yellow
            AlertLevel.ERROR: 15158332,    # Red
            AlertLevel.CRITICAL: 10038562, # Dark Red
        }
        
        payload = {
            "embeds": [{
                "title": f"🔔 {alert.title}",
                "description": alert.message,
                "color": color_map.get(alert.level, 3447003),
                "footer": {"text": f"{alert.source} • {alert.level.value.upper()}"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(alert.timestamp))
            }]
        }
        
        requests.post(self.webhook_url, json=payload, timeout=10)
    
    def _send_slack(self, alert: Alert):
        """Send Slack webhook."""
        emoji_map = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🚨",
        }
        
        payload = {
            "blocks": [{
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji_map.get(alert.level, '🔔')} *{alert.title}*\n{alert.message}"
                }
            }]
        }
        
        requests.post(self.webhook_url, json=payload, timeout=10)
    
    def _send_telegram(self, alert: Alert):
        """Send Telegram message via bot."""
        emoji_map = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🚨",
        }
        
        text = f"{emoji_map.get(alert.level, '🔔')} *{alert.title}*\n\n{alert.message}"
        
        # Expecting URL format: https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHAT_ID>
        if "?" in self.webhook_url:
            url = f"{self.webhook_url}&text={text}&parse_mode=Markdown"
        else:
            url = f"{self.webhook_url}?text={text}&parse_mode=Markdown"
        
        requests.get(url, timeout=10)
    
    def _send_custom(self, alert: Alert):
        """Send to custom HTTP endpoint."""
        payload = {
            "level": alert.level.value,
            "title": alert.title,
            "message": alert.message,
            "timestamp": alert.timestamp,
            "source": alert.source
        }
        
        requests.post(self.webhook_url, json=payload, timeout=10)
    
    # Convenience methods
    def info(self, title: str, message: str, **kwargs):
        """Send INFO level alert."""
        self.send(AlertLevel.INFO, title, message, **kwargs)
    
    def warning(self, title: str, message: str, **kwargs):
        """Send WARNING level alert."""
        self.send(AlertLevel.WARNING, title, message, **kwargs)
    
    def error(self, title: str, message: str, **kwargs):
        """Send ERROR level alert."""
        self.send(AlertLevel.ERROR, title, message, **kwargs)
    
    def critical(self, title: str, message: str, **kwargs):
        """Send CRITICAL level alert."""
        self.send(AlertLevel.CRITICAL, title, message, **kwargs)
    
    def get_history(self, limit: int = 100) -> List[Alert]:
        """Returns recent alert history."""
        return self._history[-limit:]


# Global instance (can be replaced per-bot)
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create the global AlertManager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def configure_alerts(webhook_url: str = None, webhook_type: str = "discord", 
                     min_level: AlertLevel = AlertLevel.WARNING):
    """Configure the global AlertManager."""
    global _alert_manager
    _alert_manager = AlertManager(
        webhook_url=webhook_url,
        webhook_type=webhook_type,
        min_level=min_level
    )
    return _alert_manager
