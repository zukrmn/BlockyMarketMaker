#!/usr/bin/env python3
"""
LLM-Friendly Report Generator for Blocky Market Maker

Generates daily/weekly reports in Markdown format optimized for LLM analysis.
These reports help AI assistants understand trading performance, identify
patterns, and suggest strategy improvements.

Usage:
    python scripts/generate_reports.py [--date YYYY-MM-DD] [--weekly]
"""

import os
import sys
import json
import glob
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"
METRICS_FILE = PROJECT_ROOT / "src" / "metrics_data.json"


def ensure_dirs():
    """Create necessary directories."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "daily").mkdir(exist_ok=True)
    (REPORTS_DIR / "weekly").mkdir(exist_ok=True)


def load_metrics() -> Dict[str, Any]:
    """Load metrics from the bot's metrics file."""
    if METRICS_FILE.exists():
        with open(METRICS_FILE, 'r') as f:
            return json.load(f)
    return {}


def parse_snapshots(date_str: str) -> Dict[str, List[Dict]]:
    """Parse snapshot files for a specific date."""
    snapshots = defaultdict(list)
    
    for filepath in DATA_DIR.glob("snapshot_*.jsonl"):
        market = filepath.stem.replace("snapshot_", "")
        
        with open(filepath, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    ts = data.get("ts", "")
                    if ts.startswith(date_str):
                        snapshots[market].append(data)
                except json.JSONDecodeError:
                    continue
    
    return dict(snapshots)


def parse_orderbooks(date_str: str) -> Dict[str, List[Dict]]:
    """Parse orderbook files for a specific date."""
    orderbooks = defaultdict(list)
    
    for filepath in DATA_DIR.glob("orderbook_*.jsonl"):
        market = filepath.stem.replace("orderbook_", "")
        
        with open(filepath, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    ts = data.get("ts", "")
                    if ts.startswith(date_str):
                        orderbooks[market].append(data)
                except json.JSONDecodeError:
                    continue
    
    return dict(orderbooks)


def parse_log_file(date_str: str) -> Dict[str, Any]:
    """Parse bot log file for insights."""
    log_file = LOGS_DIR / "bot.log"
    
    stats = {
        "orders_placed": 0,
        "orders_cancelled": 0,
        "errors": [],
        "warnings": [],
        "markets_active": set(),
        "integrity_checks": 0,
    }
    
    if not log_file.exists():
        return stats
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if date_str not in line:
                continue
            
            if "Placed buy order" in line or "Placed sell order" in line:
                stats["orders_placed"] += 1
                # Extract market name
                parts = line.split("│")
                if len(parts) >= 3:
                    market = parts[2].strip().split(":")[0]
                    stats["markets_active"].add(market)
            
            elif "Cancelling order" in line:
                stats["orders_cancelled"] += 1
            
            elif "ERROR" in line:
                stats["errors"].append(line.strip()[-200:])  # Last 200 chars
            
            elif "WARNING" in line:
                stats["warnings"].append(line.strip()[-200:])
            
            elif "Integrity Check" in line:
                stats["integrity_checks"] += 1
    
    stats["markets_active"] = list(stats["markets_active"])
    return stats


def analyze_market_performance(snapshots: Dict[str, List[Dict]]) -> Dict[str, Dict]:
    """Analyze performance per market from snapshots."""
    performance = {}
    
    for market, snaps in snapshots.items():
        if not snaps:
            continue
        
        mid_prices = [s["data"].get("mid_price", 0) for s in snaps if "data" in s]
        buy_active = sum(1 for s in snaps if s.get("data", {}).get("buy_active", False))
        sell_active = sum(1 for s in snaps if s.get("data", {}).get("sell_active", False))
        
        if mid_prices:
            performance[market] = {
                "avg_mid_price": sum(mid_prices) / len(mid_prices),
                "min_price": min(mid_prices),
                "max_price": max(mid_prices),
                "price_volatility": (max(mid_prices) - min(mid_prices)) / max(mid_prices) * 100 if max(mid_prices) > 0 else 0,
                "buy_active_pct": buy_active / len(snaps) * 100,
                "sell_active_pct": sell_active / len(snaps) * 100,
                "samples": len(snaps),
            }
    
    return performance


def detect_anomalies(log_stats: Dict, snapshots: Dict) -> List[str]:
    """Detect anomalies worth mentioning to LLM."""
    anomalies = []
    
    # High cancellation rate
    if log_stats["orders_placed"] > 0:
        cancel_rate = log_stats["orders_cancelled"] / log_stats["orders_placed"]
        if cancel_rate > 2:
            anomalies.append(f"High cancellation rate: {cancel_rate:.1f}x orders cancelled vs placed")
    
    # Markets with low activity
    for market, snaps in snapshots.items():
        if len(snaps) < 5:
            anomalies.append(f"{market}: Very few snapshots ({len(snaps)}), possible connectivity issue")
        
        # Check for constant sell_active=false (inventory issue)
        sell_inactive = sum(1 for s in snaps if not s.get("data", {}).get("sell_active", True))
        if sell_inactive > len(snaps) * 0.8 and len(snaps) > 5:
            anomalies.append(f"{market}: sell_active=false {sell_inactive}/{len(snaps)} times (no inventory?)")
    
    # Error patterns
    error_counts = defaultdict(int)
    for err in log_stats.get("errors", []):
        # Simplify error message to group similar ones
        key = err[:50] if len(err) > 50 else err
        error_counts[key] += 1
    
    for err, count in error_counts.items():
        if count > 5:
            anomalies.append(f"Repeated error ({count}x): {err[:80]}...")
    
    return anomalies


def generate_daily_report(date_str: str) -> str:
    """Generate a daily report in Markdown format."""
    
    # Gather data
    metrics = load_metrics()
    snapshots = parse_snapshots(date_str)
    orderbooks = parse_orderbooks(date_str)
    log_stats = parse_log_file(date_str)
    market_perf = analyze_market_performance(snapshots)
    anomalies = detect_anomalies(log_stats, snapshots)
    
    # Build report
    report = []
    report.append(f"# Daily Report - {date_str}\n")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Executive Summary
    report.append("## Executive Summary\n")
    report.append(f"- **Markets Monitored**: {len(snapshots)}")
    report.append(f"- **Orders Placed**: {log_stats['orders_placed']}")
    report.append(f"- **Orders Cancelled**: {log_stats['orders_cancelled']}")
    report.append(f"- **Integrity Checks**: {log_stats['integrity_checks']}")
    report.append(f"- **Realized P&L**: {metrics.get('realized_pnl', 0):.4f} Iron")
    report.append(f"- **Total Trades**: {len(metrics.get('trades', []))}")
    report.append("")
    
    # Anomalies (for LLM attention)
    if anomalies:
        report.append("## Anomalies Detected\n")
        report.append("> [!WARNING]")
        report.append("> The following issues were detected and may need attention:\n")
        for anomaly in anomalies[:10]:  # Limit to 10
            report.append(f"- {anomaly}")
        report.append("")
    
    # Market Performance Table
    if market_perf:
        report.append("## Market Performance\n")
        report.append("| Market | Avg Price | Volatility | Buy Active % | Sell Active % |")
        report.append("|--------|-----------|------------|--------------|---------------|")
        
        # Sort by volatility (most volatile first)
        sorted_markets = sorted(market_perf.items(), key=lambda x: x[1].get("price_volatility", 0), reverse=True)
        
        for market, perf in sorted_markets[:15]:  # Top 15
            report.append(
                f"| {market} | {perf['avg_mid_price']:.4f} | "
                f"{perf['price_volatility']:.2f}% | "
                f"{perf['buy_active_pct']:.0f}% | "
                f"{perf['sell_active_pct']:.0f}% |"
            )
        report.append("")
    
    # Error Summary
    if log_stats.get("errors"):
        report.append("## Error Summary\n")
        report.append(f"Total errors: {len(log_stats['errors'])}\n")
        
        # Group and count errors
        error_types = defaultdict(int)
        for err in log_stats["errors"]:
            if "Circuit" in err:
                error_types["Circuit Breaker"] += 1
            elif "timeout" in err.lower():
                error_types["Timeout"] += 1
            elif "connection" in err.lower():
                error_types["Connection"] += 1
            else:
                error_types["Other"] += 1
        
        for err_type, count in error_types.items():
            report.append(f"- {err_type}: {count}")
        report.append("")
    
    # Recommendations for LLM
    report.append("## Analysis Context for LLM\n")
    report.append("When analyzing this data, consider:\n")
    report.append("1. **High volatility markets** may benefit from wider spreads")
    report.append("2. **Low sell_active %** indicates inventory shortage - consider reducing buy quantity")
    report.append("3. **High cancellation rate** suggests order pricing misalignment with market")
    report.append("4. **Repeated errors** may indicate API issues or configuration problems")
    report.append("")
    
    # Raw Data Summary (compact JSON for LLM)
    report.append("## Raw Metrics Snapshot\n")
    report.append("```json")
    summary = {
        "date": date_str,
        "orders_placed": log_stats["orders_placed"],
        "orders_cancelled": log_stats["orders_cancelled"],
        "realized_pnl": metrics.get("realized_pnl", 0),
        "active_markets": len(snapshots),
        "top_volatile": [m for m, p in sorted_markets[:5]] if market_perf else [],
    }
    report.append(json.dumps(summary, indent=2))
    report.append("```\n")
    
    return "\n".join(report)


def generate_weekly_report(end_date: str) -> str:
    """Generate a weekly summary report."""
    end = datetime.strptime(end_date, "%Y-%m-%d")
    start = end - timedelta(days=7)
    
    report = []
    report.append(f"# Weekly Report: {start.strftime('%Y-%m-%d')} to {end_date}\n")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Aggregate daily reports
    daily_summaries = []
    for i in range(7):
        date = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        daily_file = REPORTS_DIR / "daily" / f"{date}.md"
        
        if daily_file.exists():
            daily_summaries.append(f"- [{date}](daily/{date}.md)")
        else:
            daily_summaries.append(f"- {date}: No data")
    
    report.append("## Daily Reports\n")
    report.extend(daily_summaries)
    report.append("")
    
    # Load metrics for weekly summary
    metrics = load_metrics()
    
    report.append("## Weekly Summary\n")
    report.append(f"- **Total Trades**: {len(metrics.get('trades', []))}")
    report.append(f"- **Realized P&L**: {metrics.get('realized_pnl', 0):.4f} Iron")
    report.append("")
    
    report.append("## Strategy Recommendations\n")
    report.append("> [!TIP]")
    report.append("> Review the daily reports above for detailed anomalies and patterns.\n")
    report.append("Consider adjusting:")
    report.append("1. Spread percentages for volatile markets")
    report.append("2. Target values for low-inventory markets")
    report.append("3. Disabled markets list if API issues persist")
    report.append("")
    
    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Generate LLM-friendly trading reports")
    parser.add_argument("--date", type=str, default=None, help="Date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--weekly", action="store_true", help="Generate weekly report")
    args = parser.parse_args()
    
    ensure_dirs()
    
    if args.date:
        date_str = args.date
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    if args.weekly:
        report = generate_weekly_report(date_str)
        output_file = REPORTS_DIR / "weekly" / f"week_ending_{date_str}.md"
    else:
        report = generate_daily_report(date_str)
        output_file = REPORTS_DIR / "daily" / f"{date_str}.md"
    
    with open(output_file, 'w') as f:
        f.write(report)
    
    print(f"Report generated: {output_file}")
    print("\n--- Preview ---\n")
    print(report[:2000])  # Print first 2000 chars as preview
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
