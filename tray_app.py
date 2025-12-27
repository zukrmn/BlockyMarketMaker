"""
BlockyMarketMaker - System Tray Application
Entry point for Windows/Mac/Linux distribution.
Runs the bot in background with system tray icon for control.
"""

import os
import sys
import asyncio
import threading
import webbrowser
from pathlib import Path

# Add src to path BEFORE any imports
BASE_DIR = Path(__file__).parent
SRC_DIR = BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(BASE_DIR))

# Now import dependencies
try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    print("Missing dependencies. Please run: pip install pystray Pillow")
    sys.exit(1)


class BlockyTrayApp:
    """System tray application for BlockyMarketMaker."""
    
    DASHBOARD_URL = "http://localhost:8081/dashboard"
    SETUP_URL = "http://localhost:8081/setup"
    
    def __init__(self):
        self.bot = None
        self.bot_thread = None
        self.running = False
        self.icon = None
        self.loop = None
        
    def create_icon_image(self):
        """Create a simple icon image programmatically."""
        # Create a simple 64x64 icon with "B" for Blocky
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw a rounded rectangle background
        draw.rounded_rectangle(
            [(4, 4), (60, 60)],
            radius=12,
            fill=(75, 85, 99)  # Gray-700
        )
        
        # Draw "B" in the center
        draw.text(
            (size // 2, size // 2),
            "B",
            fill=(255, 255, 255),
            anchor="mm"
        )
        
        return image
    
    def load_icon(self):
        """Load icon from file or create default."""
        icon_paths = [
            BASE_DIR / "img" / "icon.png",
            BASE_DIR / "img" / "icon.ico",
        ]
        
        for path in icon_paths:
            if path.exists():
                try:
                    return Image.open(path)
                except Exception:
                    pass
        
        # Create default icon
        return self.create_icon_image()
    
    def needs_setup(self) -> bool:
        """Check if first-time setup is needed."""
        env_path = BASE_DIR / ".env"
        if not env_path.exists():
            return True
        
        # Check if API key is set
        with open(env_path, 'r') as f:
            content = f.read()
            if 'BLOCKY_API_KEY=' not in content:
                return True
            # Check if key is empty
            for line in content.splitlines():
                if line.startswith('BLOCKY_API_KEY='):
                    key = line.split('=', 1)[1].strip()
                    if not key or key == '""' or key == "''":
                        return True
        return False
    
    def start_bot(self):
        """Start the bot in a separate thread."""
        if self.running:
            return
        
        def run_bot():
            """Run bot in asyncio event loop."""
            try:
                # Create new event loop for this thread
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                
                # Import and run bot
                from main import main as bot_main
                self.running = True
                self.loop.run_until_complete(bot_main())
            except Exception as e:
                print(f"Bot error: {e}")
            finally:
                self.running = False
                if self.loop:
                    self.loop.close()
        
        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()
        print("Bot started in background thread")
    
    def stop_bot(self):
        """Stop the bot gracefully."""
        if not self.running:
            return
        
        self.running = False
        
        # Signal the event loop to stop
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        print("Bot stopping...")
    
    def open_dashboard(self, icon=None, item=None):
        """Open dashboard in browser."""
        webbrowser.open(self.DASHBOARD_URL)
    
    def open_setup(self, icon=None, item=None):
        """Open setup wizard in browser."""
        webbrowser.open(self.SETUP_URL)
    
    def on_quit(self, icon=None, item=None):
        """Quit the application."""
        self.stop_bot()
        if self.icon:
            self.icon.stop()
    
    def get_status_text(self):
        """Get current status text."""
        if self.running:
            return "● Bot Running"
        return "○ Bot Stopped"
    
    def create_menu(self):
        """Create system tray menu."""
        return pystray.Menu(
            pystray.MenuItem(
                lambda item: self.get_status_text(),
                None,
                enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Abrir Dashboard",
                self.open_dashboard,
                default=True
            ),
            pystray.MenuItem(
                "Configurações",
                self.open_setup
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Sair",
                self.on_quit
            )
        )
    
    def run(self):
        """Main entry point."""
        print("BlockyMarketMaker starting...")
        
        # Check if setup is needed
        if self.needs_setup():
            print("First-time setup required. Opening browser...")
            # Start bot anyway (it will fail but dashboard will be available)
            self.start_bot()
            # Give it a moment to start the dashboard
            import time
            time.sleep(2)
            # Open setup wizard
            webbrowser.open(self.SETUP_URL)
        else:
            # Start bot and open dashboard
            self.start_bot()
            import time
            time.sleep(2)
            webbrowser.open(self.DASHBOARD_URL)
        
        # Create and run system tray icon
        self.icon = pystray.Icon(
            "BlockyMarketMaker",
            self.load_icon(),
            "BlockyMarketMaker",
            self.create_menu()
        )
        
        print("System tray icon ready. Right-click for options.")
        self.icon.run()


def main():
    """Entry point."""
    app = BlockyTrayApp()
    try:
        app.run()
    except KeyboardInterrupt:
        app.on_quit()


if __name__ == "__main__":
    main()
