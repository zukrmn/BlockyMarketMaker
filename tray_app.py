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
# In frozen mode (PyInstaller), use executable directory for config files
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
    SRC_DIR = Path(sys._MEIPASS) / "src"
else:
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
                import traceback
                traceback.print_exc()
            finally:
                self.running = False
                if self.loop:
                    self.loop.close()
        
        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()
        print("Bot started in background thread")
    
    def wait_for_server(self, url: str, timeout: int = 30) -> bool:
        """Wait for HTTP server to be ready."""
        import time
        import urllib.request
        import urllib.error
        
        print(f"Waiting for server at {url}...")
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                # Try to connect to server
                urllib.request.urlopen(url, timeout=2)
                print(f"Server ready after {time.time() - start:.1f}s")
                return True
            except urllib.error.URLError:
                # Server not ready yet
                time.sleep(0.5)
            except Exception as e:
                print(f"Connection check error: {e}")
                time.sleep(0.5)
        
        print(f"Server not ready after {timeout}s")
        return False
    
    def start_dashboard_only(self):
        """Start only the dashboard server (for setup wizard)."""
        def run_dashboard():
            """Run dashboard server in asyncio event loop."""
            try:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                
                # Import dashboard server
                from dashboard.server import TradingDashboard
                
                self.running = True
                dashboard = TradingDashboard(bot=None, port=8081)
                
                async def serve():
                    await dashboard.start()
                    print("Dashboard server started on http://localhost:8081")
                    # Keep running
                    while self.running:
                        await asyncio.sleep(1)
                
                self.loop.run_until_complete(serve())
            except Exception as e:
                print(f"Dashboard error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.running = False
                if self.loop:
                    self.loop.close()
        
        self.bot_thread = threading.Thread(target=run_dashboard, daemon=True)
        self.bot_thread.start()
        print("Dashboard-only mode started")
    
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
            print("First-time setup required. Starting dashboard-only mode...")
            # Start dashboard without full bot (for setup wizard)
            self.start_dashboard_only()
            # Wait for dashboard server
            server_ready = self.wait_for_server("http://localhost:8081/api/needs-setup", timeout=15)
            if server_ready:
                print("Opening setup wizard...")
                webbrowser.open(self.SETUP_URL)
            else:
                print("ERROR: Dashboard failed to start. Check console for errors.")
        else:
            # Start full bot with dashboard
            self.start_bot()
            # Wait for server to be ready
            server_ready = self.wait_for_server("http://localhost:8081/api/stats", timeout=30)
            if not server_ready:
                print("WARNING: Server did not start in time. Try refreshing browser manually.")
            print("Opening dashboard...")
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
