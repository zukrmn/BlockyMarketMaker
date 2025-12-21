"""
BlockyMarketMaker Launcher
Entry point for the Windows executable
"""

import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path

# Add src to path
BASE_DIR = Path(__file__).parent
SRC_DIR = BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))


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


class BotRunner:
    """GUI window that runs the bot and displays logs."""
    
    def __init__(self, root):
        self.root = root
        self.process = None
        self.running = False
        
        self.root.title("BlockyMarketMaker")
        self.root.geometry("800x600")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.setup_ui()
        self.start_bot()
    
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
        """Start the bot process."""
        self.running = True
        self.status_label.configure(text="Bot is running", foreground="green")
        
        # Determine the correct Python and run.py path
        if getattr(sys, 'frozen', False):
            # Running as exe - run.py should be next to exe
            run_script = get_base_path() / "run.py"
            python_exe = sys.executable
        else:
            run_script = BASE_DIR / "run.py"
            python_exe = sys.executable
        
        def run():
            try:
                # Use subprocess to run the bot
                self.process = subprocess.Popen(
                    [python_exe, str(run_script)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(get_base_path())
                )
                
                # Read output line by line
                for line in self.process.stdout:
                    if not self.running:
                        break
                    self.append_log(line)
                
                self.process.wait()
                
                if self.running:
                    self.root.after(0, lambda: self.status_label.configure(
                        text="Bot stopped unexpectedly", 
                        foreground="red"
                    ))
                    
            except Exception as e:
                self.append_log(f"Error starting bot: {e}\n")
                self.root.after(0, lambda: self.status_label.configure(
                    text="Failed to start", 
                    foreground="red"
                ))
        
        self.bot_thread = threading.Thread(target=run, daemon=True)
        self.bot_thread.start()
    
    def append_log(self, text):
        """Append text to log area (thread-safe)."""
        def update():
            # Determine tag based on content
            tag = None
            if "ERROR" in text or "Error" in text:
                tag = "error"
            elif "WARNING" in text or "Warning" in text:
                tag = "warning"
            elif "INFO" in text:
                tag = "info"
            
            self.log_text.insert(tk.END, text, tag)
            self.log_text.see(tk.END)
        
        self.root.after(0, update)
    
    def stop_bot(self):
        """Stop the bot gracefully."""
        self.running = False
        self.status_label.configure(text="Stopping...", foreground="orange")
        
        if self.process:
            try:
                # Send interrupt signal
                if sys.platform == "win32":
                    self.process.terminate()
                else:
                    import signal
                    self.process.send_signal(signal.SIGINT)
                
                # Wait for graceful shutdown
                self.process.wait(timeout=10)
            except:
                self.process.kill()
        
        self.status_label.configure(text="Bot stopped", foreground="gray")
        self.btn_stop.configure(text="Start Bot", command=self.start_bot)
    
    def open_dashboard(self):
        """Open dashboard in browser."""
        import webbrowser
        webbrowser.open("http://localhost:8081/dashboard")
    
    def reconfigure(self):
        """Open setup wizard for reconfiguration."""
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
            if tk.messagebox.askokcancel("Quit", "This will stop the bot. Continue?"):
                self.stop_bot()
                self.root.destroy()
        else:
            self.root.destroy()


def run_bot_gui():
    """Run the bot with GUI."""
    root = tk.Tk()
    BotRunner(root)
    root.mainloop()


def main():
    """Main entry point."""
    if needs_setup():
        # Import and run setup wizard
        from scripts.gui_setup import run_setup
        
        def on_setup_complete(data):
            # Setup complete, run the bot
            run_bot_gui()
        
        run_setup(on_complete=on_setup_complete)
    else:
        run_bot_gui()


if __name__ == "__main__":
    main()
