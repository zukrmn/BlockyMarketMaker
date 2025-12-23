"""
Desktop Notifications Module
Provides desktop notifications with sound for trade events
Works on Linux (ZorinOS/Ubuntu), macOS, and Windows
"""

import os
import sys
import platform
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Try to load config
try:
    from config import get_config
    _config = get_config()
    NOTIFICATIONS_ENABLED = _config.notifications.enabled
    SOUND_ENABLED = _config.notifications.sound_enabled
    NOTIFY_ON_TRADE = _config.notifications.notify_on_trade
    NOTIFY_ON_ERROR = _config.notifications.notify_on_error
except Exception:
    # Fallback defaults if config not available
    NOTIFICATIONS_ENABLED = True
    SOUND_ENABLED = True
    NOTIFY_ON_TRADE = True
    NOTIFY_ON_ERROR = False


class DesktopNotifier:
    """Cross-platform desktop notification system with sound support."""
    
    def __init__(self, app_name: str = "BlockyMarketMaker"):
        self.app_name = app_name
        self.system = platform.system().lower()
        self.enabled = NOTIFICATIONS_ENABLED
        self.sound_enabled = SOUND_ENABLED
        
        # Try to find notification sound
        self.sound_file = self._find_sound_file()
        
    def _find_sound_file(self) -> Optional[str]:
        """Find a suitable notification sound file."""
        # Check for custom sound in project
        project_sounds = [
            Path(__file__).parent.parent / "sounds" / "trade.wav",
            Path(__file__).parent.parent / "sounds" / "notification.wav",
        ]
        
        for sound_path in project_sounds:
            if sound_path.exists():
                return str(sound_path)
        
        # System sounds on Linux
        linux_sounds = [
            "/usr/share/sounds/freedesktop/stereo/complete.oga",
            "/usr/share/sounds/freedesktop/stereo/message.oga",
            "/usr/share/sounds/gnome/default/alerts/glass.ogg",
            "/usr/share/sounds/Yaru/stereo/complete.oga",
            "/usr/share/sounds/Yaru/stereo/message.oga",
        ]
        
        if self.system == "linux":
            for sound in linux_sounds:
                if os.path.exists(sound):
                    return sound
        
        return None
    
    def _play_sound(self):
        """Play notification sound."""
        if not self.sound_enabled:
            return
            
        try:
            if self.system == "linux":
                if self.sound_file:
                    # Try paplay (PulseAudio) first, then aplay
                    try:
                        subprocess.Popen(
                            ["paplay", self.sound_file],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                    except FileNotFoundError:
                        try:
                            subprocess.Popen(
                                ["aplay", "-q", self.sound_file],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL
                            )
                        except FileNotFoundError:
                            pass
                else:
                    # Fallback: system beep via terminal bell
                    print("\a", end="", flush=True)
                    
            elif self.system == "darwin":  # macOS
                if self.sound_file:
                    subprocess.Popen(
                        ["afplay", self.sound_file],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    subprocess.Popen(
                        ["afplay", "/System/Library/Sounds/Glass.aiff"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    
            elif self.system == "windows":
                import winsound
                if self.sound_file:
                    winsound.PlaySound(self.sound_file, winsound.SND_ASYNC)
                else:
                    winsound.MessageBeep()
                    
        except Exception as e:
            logger.debug(f"Failed to play sound: {e}")
    
    def notify(
        self, 
        title: str, 
        message: str, 
        urgency: str = "normal",
        icon: str = "dialog-information",
        play_sound: bool = True
    ):
        """Send a desktop notification.
        
        Args:
            title: Notification title
            message: Notification body text
            urgency: low, normal, or critical
            icon: Icon name (Linux) or path
            play_sound: Whether to play notification sound
        """
        # Check if notifications are enabled
        if not self.enabled:
            return
            
        try:
            if self.system == "linux":
                # Use notify-send (most Linux distros)
                cmd = [
                    "notify-send",
                    "--app-name", self.app_name,
                    "--urgency", urgency,
                    "--icon", icon,
                    title,
                    message
                ]
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
            elif self.system == "darwin":  # macOS
                script = f'''
                display notification "{message}" with title "{title}"
                '''
                subprocess.Popen(
                    ["osascript", "-e", script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
            elif self.system == "windows":
                try:
                    from win10toast import ToastNotifier
                    toaster = ToastNotifier()
                    toaster.show_toast(title, message, duration=5, threaded=True)
                except ImportError:
                    # Fallback: use PowerShell
                    script = f'''
                    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                    $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
                    $template.SelectSingleNode("//text[@id='1']").InnerText = "{title}"
                    $template.SelectSingleNode("//text[@id='2']").InnerText = "{message}"
                    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{self.app_name}").Show($template)
                    '''
                    subprocess.Popen(
                        ["powershell", "-Command", script],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    
            if play_sound:
                self._play_sound()
                
        except Exception as e:
            logger.debug(f"Failed to send notification: {e}")
    
    def notify_trade(
        self, 
        side: str, 
        market: str, 
        quantity: float, 
        price: float,
        pnl: Optional[float] = None
    ):
        """Send a trade notification.
        
        Args:
            side: "buy" or "sell"
            market: Market name (e.g., "diam_iron")
            quantity: Trade quantity
            price: Trade price
            pnl: Optional current P&L
        """
        # Format market name nicely
        base, quote = market.split('_') if '_' in market else (market, "")
        market_name = f"{base.upper()}/{quote.upper()}" if quote else market.upper()
        
        # Choose icon and emoji based on side
        if side.lower() == "buy":
            emoji = "🟢"
            icon = "emblem-money"
            action = "COMPRA"
        else:
            emoji = "🔴"
            icon = "emblem-money"
            action = "VENDA"
        
        title = f"{emoji} {action} Executada"
        message = f"{quantity:.2f} {base.upper()} @ {price:.4f} {quote.upper()}"
        
        if pnl is not None:
            pnl_str = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"
            message += f"\nP&L: {pnl_str} Iron"
        
        self.notify(
            title=title,
            message=message,
            urgency="normal",
            icon=icon,
            play_sound=True
        )


# Global notifier instance
_notifier: Optional[DesktopNotifier] = None


def get_notifier() -> DesktopNotifier:
    """Get the global notifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = DesktopNotifier()
    return _notifier


def notify_trade(side: str, market: str, quantity: float, price: float, pnl: Optional[float] = None):
    """Convenience function to send trade notification."""
    if not NOTIFY_ON_TRADE:
        return
    get_notifier().notify_trade(side, market, quantity, price, pnl)


def set_notifications_enabled(enabled: bool):
    """Enable or disable notifications at runtime."""
    global NOTIFICATIONS_ENABLED
    NOTIFICATIONS_ENABLED = enabled
    notifier = get_notifier()
    notifier.enabled = enabled


def set_sound_enabled(enabled: bool):
    """Enable or disable notification sounds at runtime."""
    global SOUND_ENABLED
    SOUND_ENABLED = enabled
    notifier = get_notifier()
    notifier.sound_enabled = enabled


def is_notifications_enabled() -> bool:
    """Check if notifications are enabled."""
    return NOTIFICATIONS_ENABLED
