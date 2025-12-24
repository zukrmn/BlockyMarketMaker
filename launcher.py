"""
BlockyMarketMaker Launcher
Entry point for the Windows executable
Runs the bot directly (not via subprocess) for PyInstaller compatibility
"""

import os
import sys
import asyncio
import threading
import queue
import io
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr

# Add src to path BEFORE any imports
BASE_DIR = Path(__file__).parent
SRC_DIR = BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(BASE_DIR))


def get_base_path() -> Path:
    """Get base path for config files."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent


def needs_setup() -> bool:
    """Check if first-time setup is needed."""
    env_path = get_base_path() / ".env"
    if not env_path.exists():
        return True
    
    # Check if API key is set
    with open(env_path, "r") as f:
        content = f.read()
        if "BLOCKY_API_KEY=" not in content:
            return True
        # Check if key has value
        for line in content.split("\n"):
            if line.startswith("BLOCKY_API_KEY="):
                value = line.split("=", 1)[1].strip()
                if not value or value == "your-api-key-here":
                    return True
    
    return False


def load_env_file():
    """Load .env file into os.environ manually (no dotenv dependency)."""
    try:
        env_path = get_base_path() / ".env"
        
        print(f"[ENV] Base path: {get_base_path()}")
        print(f"[ENV] Looking for .env at: {env_path}")
        print(f"[ENV] File exists: {env_path.exists()}")
        
        if not env_path.exists():
            print(f"[ENV] ERROR: .env file not found!")
            return False
        
        # Try reading with different encodings (Windows BOM issue)
        content = None
        for encoding in ['utf-8-sig', 'utf-8', 'latin-1']:
            try:
                with open(env_path, "r", encoding=encoding) as f:
                    content = f.read()
                print(f"[ENV] Read file with encoding: {encoding}")
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            print("[ENV] ERROR: Could not read .env file with any encoding")
            return False
        
        loaded_keys = []
        for line in content.splitlines():
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value and len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                os.environ[key] = value
                loaded_keys.append(key)
        
        print(f"[ENV] Loaded {len(loaded_keys)} variables: {loaded_keys}")
        
        # Verify BLOCKY_API_KEY
        api_key = os.environ.get('BLOCKY_API_KEY', '')
        print(f"[ENV] BLOCKY_API_KEY set: {bool(api_key)}")
        print(f"[ENV] BLOCKY_API_KEY length: {len(api_key)}")
        
        return bool(api_key)
        
    except Exception as e:
        print(f"[ENV] EXCEPTION: {e}")
        import traceback
        print(traceback.format_exc())
        return False


class LogCapture:
    """Capture stdout/stderr and send to queue."""
    
    def __init__(self, log_queue: queue.Queue, original):
        self.log_queue = log_queue
        self.original = original
    
    def write(self, text):
        if text.strip():
            self.log_queue.put(text)
        if self.original:
            self.original.write(text)
    
    def flush(self):
        if self.original:
            self.original.flush()


class BotRunner:
    """GUI window that runs the bot and displays logs."""
    
    def __init__(self, root):
        self.root = root
        self.running = False
        self.bot_thread = None
        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        self.root.title("BlockyMarketMaker")
        self.root.geometry("900x650")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.setup_ui()
        self.start_bot()
        self.check_log_queue()
    
    def setup_ui(self):
        """Setup the UI."""
        # Top frame with buttons
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)
        
        self.status_label = ttk.Label(
            top_frame, 
            text="Starting bot...",
            font=("", 10, "bold")
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Buttons on right
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(side=tk.RIGHT)
        
        ttk.Button(
            btn_frame,
            text="Open Dashboard",
            command=self.open_dashboard
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame,
            text="Reconfigure",
            command=self.reconfigure
        ).pack(side=tk.LEFT, padx=5)
        
        self.btn_stop = ttk.Button(
            btn_frame,
            text="Stop Bot",
            command=self.stop_bot
        )
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        # Notifications toggle
        self.notifications_var = tk.BooleanVar(value=True)
        try:
            from notifications import is_notifications_enabled
            self.notifications_var.set(is_notifications_enabled())
        except:
            pass
            
        self.notifications_check = ttk.Checkbutton(
            btn_frame,
            text="🔔 Notifications",
            variable=self.notifications_var,
            command=self.toggle_notifications
        )
        self.notifications_check.pack(side=tk.LEFT, padx=10)
        
        # Log area
        log_frame = ttk.Frame(self.root, padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(log_frame, text="Bot Output:").pack(anchor=tk.W)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Configure tags for colored output
        self.log_text.tag_configure("info", foreground="#4ec9b0")
        self.log_text.tag_configure("warning", foreground="#dcdcaa")
        self.log_text.tag_configure("error", foreground="#f14c4c")
        self.log_text.tag_configure("success", foreground="#6a9955")
        
        # Bottom status bar
        self.bottom_frame = ttk.Frame(self.root)
        self.bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.bottom_status = ttk.Label(
            self.bottom_frame,
            text="Dashboard: http://localhost:8081/dashboard",
            foreground="gray"
        )
        self.bottom_status.pack(side=tk.LEFT, padx=10, pady=5)
    
    def start_bot(self):
        """Start the bot in a separate thread."""
        self.running = True
        self.stop_event.clear()
        self.status_label.configure(text="Bot is running", foreground="green")
        
        def run_bot():
            """Run the bot's async main function."""
            # Set working directory
            os.chdir(str(get_base_path()))
            
            # Capture stdout/stderr
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = LogCapture(self.log_queue, original_stdout)
            sys.stderr = LogCapture(self.log_queue, original_stderr)
            
            try:
                # Load environment variables from .env file
                load_env_file()
                
                # Import here to ensure paths are set
                from main import main
                
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Run the main function
                loop.run_until_complete(main())
                
            except KeyboardInterrupt:
                self.log_queue.put("Bot stopped by user.\n")
            except Exception as e:
                self.log_queue.put(f"ERROR: {e}\n")
                import traceback
                self.log_queue.put(traceback.format_exc())
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr
                
                if self.running:
                    self.root.after(0, self._on_bot_stopped)
        
        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()
    
    def _on_bot_stopped(self):
        """Called when bot stops unexpectedly."""
        self.status_label.configure(text="Bot stopped", foreground="red")
        self.btn_stop.configure(text="Restart Bot", command=self.start_bot)
    
    def check_log_queue(self):
        """Check log queue and update text widget."""
        try:
            while True:
                text = self.log_queue.get_nowait()
                self.append_log(text)
        except queue.Empty:
            pass
        
        # Schedule next check
        if self.running or not self.log_queue.empty():
            self.root.after(100, self.check_log_queue)
    
    def append_log(self, text):
        """Append text to log area."""
        # Determine tag based on content
        tag = None
        text_upper = text.upper()
        if "ERROR" in text_upper:
            tag = "error"
        elif "WARNING" in text_upper:
            tag = "warning"
        elif "INFO" in text_upper:
            tag = "info"
        elif "SUCCESS" in text_upper or "✓" in text:
            tag = "success"
        
        self.log_text.insert(tk.END, text if text.endswith('\n') else text + '\n', tag)
        self.log_text.see(tk.END)
        
        # Limit log size
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 1000:
            self.log_text.delete('1.0', '100.0')
    
    def stop_bot(self):
        """Stop the bot gracefully."""
        self.running = False
        self.stop_event.set()
        self.status_label.configure(text="Stopping...", foreground="orange")
        
        # Signal the asyncio loop to stop
        # This is tricky with threads - we'll just set a flag and let it timeout
        self.append_log("Stopping bot... (please wait)")
        
        def check_stopped():
            if self.bot_thread and self.bot_thread.is_alive():
                # Still running, check again
                self.root.after(500, check_stopped)
            else:
                self.status_label.configure(text="Bot stopped", foreground="gray")
                self.btn_stop.configure(text="Start Bot", command=self.start_bot)
        
        self.root.after(500, check_stopped)
    
    def open_dashboard(self):
        """Open dashboard in browser."""
        import webbrowser
        webbrowser.open("http://localhost:8081/dashboard")
    
    def toggle_notifications(self):
        """Toggle notifications on/off."""
        enabled = self.notifications_var.get()
        try:
            from notifications import set_notifications_enabled
            set_notifications_enabled(enabled)
            status = "enabled" if enabled else "disabled"
            self.append_log(f"🔔 Notifications {status}\n")
        except Exception as e:
            self.append_log(f"Failed to toggle notifications: {e}\n")
    
    def reconfigure(self):
        """Open setup wizard for reconfiguration."""
        if self.running:
            if not messagebox.askyesno("Reconfigure", "This will stop the bot. Continue?"):
                return
            self.stop_bot()
        
        self.root.destroy()
        
        # Delete .env to force setup
        env_path = get_base_path() / ".env"
        if env_path.exists():
            env_path.unlink()
        
        # Restart
        main()
    
    def on_close(self):
        """Handle window close."""
        if self.running:
            if messagebox.askokcancel("Quit", "This will stop the bot. Continue?"):
                self.running = False
                self.stop_event.set()
                self.root.after(1000, self.root.destroy)
        else:
            self.root.destroy()


def run_bot_gui():
    """Run the bot with GUI."""
    root = tk.Tk()
    BotRunner(root)
    root.mainloop()


def main():
    """Main entry point."""
    # Change to base directory
    os.chdir(str(get_base_path()))
    
    if needs_setup():
        # Import and run setup wizard
        try:
            from scripts.gui_setup import run_setup
        except ImportError:
            # Fallback for when running from different location
            sys.path.insert(0, str(get_base_path() / "scripts"))
            from gui_setup import run_setup
        
        def on_setup_complete(data):
            # Setup complete, run the bot
            run_bot_gui()
        
        run_setup(on_complete=on_setup_complete)
    else:
        run_bot_gui()


if __name__ == "__main__":
    main()
