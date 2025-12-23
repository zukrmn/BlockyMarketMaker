"""
BlockyMarketMaker GUI Setup Wizard
Tkinter-based setup for first-time users
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import yaml
import random
from pathlib import Path


class SetupWizard:
    """Multi-step setup wizard for BlockyMarketMaker configuration."""
    
    # Available markets
    MARKETS = [
        ("diam_iron", "Diamond", 50.0),
        ("gold_iron", "Gold", 5.0),
        ("lapi_iron", "Lapis", 2.0),
        ("coal_iron", "Coal", 0.5),
        ("slme_iron", "Slime", 5.0),
        ("obsn_iron", "Obsidian", 2.5),
        ("olog_iron", "Oak Log", 0.45),
        ("ston_iron", "Stone", 0.1),
        ("cobl_iron", "Cobblestone", 0.05),
        ("sand_iron", "Sand", 0.05),
        ("dirt_iron", "Dirt", 0.01),
    ]
    
    def __init__(self, root, on_complete=None):
        self.root = root
        self.on_complete = on_complete
        self.current_step = 0
        
        # Data storage
        self.data = {
            "api_key": "",
            "webhook_url": "",
            "base_spread": 0.03,
            "target_value": 10.0,
            "dry_run": False,
            "enabled_markets": [],
        }
        
        # Setup window
        self.root.title("BlockyMarketMaker - Setup")
        self.root.geometry("600x600")
        self.root.resizable(True, True)
        self.root.minsize(600, 550)
        
        # Center window
        self.center_window()
        
        # Main container
        self.main_frame = ttk.Frame(root, padding=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Progress indicator
        self.progress_frame = ttk.Frame(self.main_frame)
        self.progress_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.steps = ["API Config", "Trading", "Markets", "Confirm"]
        self.step_labels = []
        for i, step in enumerate(self.steps):
            lbl = ttk.Label(self.progress_frame, text=f"{i+1}. {step}")
            lbl.pack(side=tk.LEFT, expand=True)
            self.step_labels.append(lbl)
        
        # Content frame
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Navigation buttons
        self.nav_frame = ttk.Frame(self.main_frame)
        self.nav_frame.pack(fill=tk.X, pady=(20, 0))
        
        self.btn_back = ttk.Button(self.nav_frame, text="Back", command=self.prev_step)
        self.btn_back.pack(side=tk.LEFT)
        
        self.btn_next = ttk.Button(self.nav_frame, text="Next", command=self.next_step)
        self.btn_next.pack(side=tk.RIGHT)
        
        # Show first step
        self.show_step(0)
    
    def center_window(self):
        """Center the window on screen."""
        self.root.update_idletasks()
        w = 600
        h = 600
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
    
    def update_progress(self):
        """Update progress indicator styling."""
        for i, lbl in enumerate(self.step_labels):
            if i < self.current_step:
                lbl.configure(foreground="green")
            elif i == self.current_step:
                lbl.configure(foreground="blue", font=("", 10, "bold"))
            else:
                lbl.configure(foreground="gray", font=("", 10, "normal"))
    
    def clear_content(self):
        """Clear content frame."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def show_step(self, step):
        """Show specific step."""
        self.current_step = step
        self.clear_content()
        self.update_progress()
        
        # Update button states
        self.btn_back.configure(state=tk.NORMAL if step > 0 else tk.DISABLED)
        self.btn_next.configure(text="Finish" if step == len(self.steps) - 1 else "Next")
        
        # Show step content
        if step == 0:
            self.show_api_step()
        elif step == 1:
            self.show_trading_step()
        elif step == 2:
            self.show_markets_step()
        elif step == 3:
            self.show_confirm_step()
    
    def show_api_step(self):
        """Step 1: API Configuration."""
        ttk.Label(
            self.content_frame, 
            text="API Configuration",
            font=("", 14, "bold")
        ).pack(anchor=tk.W, pady=(0, 10))
        
        ttk.Label(
            self.content_frame,
            text="Enter your Blocky API credentials. You can find your API key\n"
                 "in the Blocky panel at craft.blocky.com.br",
            foreground="gray"
        ).pack(anchor=tk.W, pady=(0, 20))
        
        # API Key
        ttk.Label(self.content_frame, text="API Key (required):").pack(anchor=tk.W)
        self.api_key_var = tk.StringVar(value=self.data["api_key"])
        self.api_key_entry = ttk.Entry(
            self.content_frame, 
            textvariable=self.api_key_var,
            width=60,
            show="*"
        )
        self.api_key_entry.pack(anchor=tk.W, pady=(5, 15))
        
        # Show/Hide toggle
        self.show_key_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.content_frame,
            text="Show API Key",
            variable=self.show_key_var,
            command=self.toggle_api_key_visibility
        ).pack(anchor=tk.W)
        
        ttk.Separator(self.content_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=20)
        
        # Discord Webhook
        ttk.Label(self.content_frame, text="Discord Webhook URL (optional):").pack(anchor=tk.W)
        ttk.Label(
            self.content_frame,
            text="Receive alerts about errors and important events",
            foreground="gray",
            font=("", 9)
        ).pack(anchor=tk.W)
        self.webhook_var = tk.StringVar(value=self.data["webhook_url"])
        ttk.Entry(
            self.content_frame,
            textvariable=self.webhook_var,
            width=60
        ).pack(anchor=tk.W, pady=(5, 0))
    
    def toggle_api_key_visibility(self):
        """Toggle API key visibility."""
        self.api_key_entry.configure(show="" if self.show_key_var.get() else "*")
    
    def show_trading_step(self):
        """Step 2: Trading Configuration."""
        ttk.Label(
            self.content_frame,
            text="Trading Configuration",
            font=("", 14, "bold")
        ).pack(anchor=tk.W, pady=(0, 10))
        
        ttk.Label(
            self.content_frame,
            text="Configure your trading parameters. These values will have a small\n"
                 "random variation applied to avoid identical configs across users.",
            foreground="gray"
        ).pack(anchor=tk.W, pady=(0, 20))
        
        # Create scrollable frame for settings
        settings_frame = ttk.Frame(self.content_frame)
        settings_frame.pack(fill=tk.BOTH, expand=True)
        
        # Base Spread
        spread_frame = ttk.LabelFrame(settings_frame, text="Base Spread (Profit Margin)", padding=10)
        spread_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(
            spread_frame,
            text="The difference between your buy and sell prices.\n"
                 "• Higher (5-10%): More profit per trade, but fewer trades\n"
                 "• Lower (1-3%): Less profit per trade, but more trades\n"
                 "• Recommended for beginners: 3-5%",
            foreground="gray",
            justify=tk.LEFT
        ).pack(anchor=tk.W)
        
        spread_input_frame = ttk.Frame(spread_frame)
        spread_input_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.spread_var = tk.DoubleVar(value=self.data["base_spread"] * 100)
        ttk.Scale(
            spread_input_frame,
            from_=1.0,
            to=15.0,
            variable=self.spread_var,
            orient=tk.HORIZONTAL,
            length=300,
            command=self.update_spread_label
        ).pack(side=tk.LEFT)
        
        self.spread_label = ttk.Label(spread_input_frame, text=f"{self.spread_var.get():.1f}%")
        self.spread_label.pack(side=tk.LEFT, padx=10)
        
        # Target Value
        value_frame = ttk.LabelFrame(settings_frame, text="Target Order Value (Iron)", padding=10)
        value_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(
            value_frame,
            text="How much Iron to use per order.\n"
                 "• Higher (50-100): Bigger orders, more profit potential, more risk\n"
                 "• Lower (5-20): Smaller orders, less risk, good for testing\n"
                 "• Start small and increase as you gain confidence",
            foreground="gray",
            justify=tk.LEFT
        ).pack(anchor=tk.W)
        
        value_input_frame = ttk.Frame(value_frame)
        value_input_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.value_var = tk.DoubleVar(value=self.data["target_value"])
        ttk.Scale(
            value_input_frame,
            from_=5.0,
            to=100.0,
            variable=self.value_var,
            orient=tk.HORIZONTAL,
            length=300,
            command=self.update_value_label
        ).pack(side=tk.LEFT)
        
        self.value_label = ttk.Label(value_input_frame, text=f"{self.value_var.get():.0f} Iron")
        self.value_label.pack(side=tk.LEFT, padx=10)
        
        # Dry Run
        dry_frame = ttk.LabelFrame(settings_frame, text="Test Mode", padding=10)
        dry_frame.pack(fill=tk.X)
        
        self.dry_run_var = tk.BooleanVar(value=self.data["dry_run"])
        ttk.Checkbutton(
            dry_frame,
            text="Enable Dry Run (simulate without real orders)",
            variable=self.dry_run_var
        ).pack(anchor=tk.W)
        
        ttk.Label(
            dry_frame,
            text="Recommended for first-time users to test configuration",
            foreground="gray",
            font=("", 9)
        ).pack(anchor=tk.W)
    
    def update_spread_label(self, value):
        """Update spread label."""
        self.spread_label.configure(text=f"{float(value):.1f}%")
    
    def update_value_label(self, value):
        """Update value label."""
        self.value_label.configure(text=f"{float(value):.0f} Iron")
    
    def show_markets_step(self):
        """Step 3: Market Selection."""
        ttk.Label(
            self.content_frame,
            text="Market Selection",
            font=("", 14, "bold")
        ).pack(anchor=tk.W, pady=(0, 10))
        
        ttk.Label(
            self.content_frame,
            text="Select which markets to trade. Start with a few markets\n"
                 "and expand as you gain experience.",
            foreground="gray"
        ).pack(anchor=tk.W, pady=(0, 15))
        
        # All markets option
        self.all_markets_var = tk.BooleanVar(value=len(self.data["enabled_markets"]) == 0)
        ttk.Checkbutton(
            self.content_frame,
            text="Trade ALL markets (advanced users)",
            variable=self.all_markets_var,
            command=self.toggle_all_markets
        ).pack(anchor=tk.W, pady=(0, 10))
        
        ttk.Separator(self.content_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Market checkboxes
        self.market_frame = ttk.Frame(self.content_frame)
        self.market_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            self.market_frame,
            text="Or select specific markets:",
            font=("", 10, "bold")
        ).pack(anchor=tk.W, pady=(0, 10))
        
        self.market_vars = {}
        
        # Create two columns
        left_frame = ttk.Frame(self.market_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        right_frame = ttk.Frame(self.market_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        for i, (market_id, name, price) in enumerate(self.MARKETS):
            var = tk.BooleanVar(value=market_id in self.data["enabled_markets"])
            self.market_vars[market_id] = var
            
            frame = left_frame if i < len(self.MARKETS) // 2 + 1 else right_frame
            
            cb = ttk.Checkbutton(
                frame,
                text=f"{name} ({market_id}) - ~{price} Iron",
                variable=var,
                command=self.update_market_selection
            )
            cb.pack(anchor=tk.W, pady=2)
        
        self.toggle_all_markets()
    
    def toggle_all_markets(self):
        """Toggle individual market checkboxes based on 'all markets' selection."""
        state = tk.DISABLED if self.all_markets_var.get() else tk.NORMAL
        for widget in self.market_frame.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Checkbutton):
                        child.configure(state=state)
    
    def update_market_selection(self):
        """Update when individual market is selected."""
        if any(var.get() for var in self.market_vars.values()):
            self.all_markets_var.set(False)
    
    def show_confirm_step(self):
        """Step 4: Confirmation."""
        ttk.Label(
            self.content_frame,
            text="Configuration Summary",
            font=("", 14, "bold")
        ).pack(anchor=tk.W, pady=(0, 10))
        
        ttk.Label(
            self.content_frame,
            text="Review your configuration before starting the bot.",
            foreground="gray"
        ).pack(anchor=tk.W, pady=(0, 20))
        
        # Summary
        summary_frame = ttk.LabelFrame(self.content_frame, text="Settings", padding=10)
        summary_frame.pack(fill=tk.X)
        
        # Apply random variation to spread
        base = self.spread_var.get() / 100
        variation = random.uniform(-0.005, 0.005)
        final_spread = base + variation
        
        self.data["base_spread"] = final_spread
        self.data["target_value"] = self.value_var.get()
        self.data["dry_run"] = self.dry_run_var.get()
        
        summary_text = f"""
API Key: {'*' * 20}...{self.api_key_var.get()[-4:] if len(self.api_key_var.get()) > 4 else '****'}
Discord Webhook: {'Configured' if self.webhook_var.get() else 'Not configured'}

Base Spread: {final_spread * 100:.2f}% (includes ±0.5% random variation)
Target Value: {self.value_var.get():.0f} Iron per order
Dry Run Mode: {'Yes (no real orders)' if self.dry_run_var.get() else 'No (real orders)'}

Markets: {'All markets' if self.all_markets_var.get() else ', '.join([m for m, v in self.market_vars.items() if v.get()]) or 'None selected'}
        """
        
        ttk.Label(
            summary_frame,
            text=summary_text.strip(),
            justify=tk.LEFT,
            font=("Consolas", 10)
        ).pack(anchor=tk.W)
        
        # Warning for no markets
        if not self.all_markets_var.get() and not any(v.get() for v in self.market_vars.values()):
            ttk.Label(
                self.content_frame,
                text="Warning: No markets selected. The bot will not trade.",
                foreground="red"
            ).pack(anchor=tk.W, pady=(10, 0))
    
    def validate_step(self):
        """Validate current step before proceeding."""
        if self.current_step == 0:
            # Validate API key
            api_key = self.api_key_var.get().strip()
            if not api_key:
                messagebox.showerror("Error", "API Key is required")
                return False
            if len(api_key) < 10:
                messagebox.showerror("Error", "API Key seems too short")
                return False
            
            self.data["api_key"] = api_key
            self.data["webhook_url"] = self.webhook_var.get().strip()
        
        elif self.current_step == 1:
            self.data["base_spread"] = self.spread_var.get() / 100
            self.data["target_value"] = self.value_var.get()
            self.data["dry_run"] = self.dry_run_var.get()
        
        elif self.current_step == 2:
            if self.all_markets_var.get():
                self.data["enabled_markets"] = []
            else:
                self.data["enabled_markets"] = [m for m, v in self.market_vars.items() if v.get()]
        
        return True
    
    def next_step(self):
        """Go to next step."""
        if not self.validate_step():
            return
        
        if self.current_step < len(self.steps) - 1:
            self.show_step(self.current_step + 1)
        else:
            self.finish_setup()
    
    def prev_step(self):
        """Go to previous step."""
        if self.current_step > 0:
            self.show_step(self.current_step - 1)
    
    def finish_setup(self):
        """Save configuration and complete setup."""
        try:
            self.save_env()
            self.save_config()
            
            messagebox.showinfo(
                "Setup Complete",
                "Configuration saved successfully!\n\n"
                "The bot will now start. You can access the dashboard at:\n"
                "http://localhost:8081/dashboard"
            )
            
            if self.on_complete:
                self.on_complete(self.data)
            
            self.root.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration:\n{e}")
    
    def save_env(self):
        """Save .env file."""
        env_path = self.get_base_path() / ".env"
        
        lines = [
            f"BLOCKY_API_KEY={self.data['api_key']}",
        ]
        
        if self.data["webhook_url"]:
            lines.append(f"ALERT_WEBHOOK_URL={self.data['webhook_url']}")
            lines.append("ALERT_WEBHOOK_TYPE=discord")
        
        with open(env_path, "w") as f:
            f.write("\n".join(lines) + "\n")
    
    def save_config(self):
        """Save config.yaml with user settings."""
        config_path = self.get_base_path() / "config.yaml"
        
        # Load existing config or create new
        if config_path.exists():
            with open(config_path, "r") as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {}
        
        # Update trading settings
        if "trading" not in config:
            config["trading"] = {}
        
        config["trading"]["dry_run"] = self.data["dry_run"]
        config["trading"]["target_value"] = self.data["target_value"]
        
        if self.data["enabled_markets"]:
            config["trading"]["enabled_markets"] = self.data["enabled_markets"]
        elif "enabled_markets" in config["trading"]:
            del config["trading"]["enabled_markets"]
        
        # Update spread settings
        if "dynamic_spread" not in config:
            config["dynamic_spread"] = {}
        
        config["dynamic_spread"]["base_spread"] = round(self.data["base_spread"], 4)
        
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    def get_base_path(self) -> Path:
        """Get base path for config files."""
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            return Path(sys.executable).parent
        else:
            # Running as script
            return Path(__file__).parent.parent


def run_setup(on_complete=None):
    """Run the setup wizard."""
    root = tk.Tk()
    SetupWizard(root, on_complete)
    root.mainloop()


if __name__ == "__main__":
    run_setup()
