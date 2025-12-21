#!/usr/bin/env python3
"""
LLM-Optimized Report Generator for Blocky Market Maker

Generates daily reports and market profiles in markdown format,
optimized for LLM analysis and strategy development.

Usage:
    python scripts/generate_reports.py              # Generate today's report
    python scripts/generate_reports.py --all        # Generate reports for all available data
    python scripts/generate_reports.py --date 2025-12-21  # Specific date
"""

import os
import sys
import json
import argparse
from datetime import datetime, date
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
METRICS_FILE = PROJECT_ROOT / "src" / "metrics_data.json"


def ensure_dirs():
    """Ensure report directories exist."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "daily").mkdir(exist_ok=True)
    (REPORTS_DIR / "analysis").mkdir(exist_ok=True)


def load_jsonl(filepath: Path) -> List[Dict]:
    """Load JSONL file into list of dicts."""
    if not filepath.exists():
        return []
    entries = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def load_metrics() -> Dict:
    """Load metrics data."""
    if METRICS_FILE.exists():
        with open(METRICS_FILE, 'r') as f:
            return json.load(f)
    return {}


def analyze_snapshots(market: str) -> Dict[str, Any]:
    """Analyze snapshot data for a market."""
    filepath = DATA_DIR / f"snapshot_{market}.jsonl"
    entries = load_jsonl(filepath)
    
    if not entries:
        return {"status": "no_data"}
    
    # Extract time series
    prices = []
    spreads = []
    inventories = []
    
    for e in entries:
        data = e.get("data", {})
        mid = data.get("mid_price", 0)
        buy = data.get("buy_price", 0)
        sell = data.get("sell_price", 0)
        inv = data.get("inventory_base", 0)
        
        if mid > 0:
            prices.append(mid)
        if buy > 0 and sell > 0:
            spread = (sell - buy) / mid * 100
            spreads.append(spread)
        inventories.append(inv)
    
    if not prices:
        return {"status": "no_price_data"}
    
    # Calculate statistics
    avg_price = sum(prices) / len(prices)
    min_price = min(prices)
    max_price = max(prices)
    volatility = (max_price - min_price) / avg_price * 100 if avg_price > 0 else 0
    
    avg_spread = sum(spreads) / len(spreads) if spreads else 0
    avg_inventory = sum(inventories) / len(inventories) if inventories else 0
    
    # Detect anomalies
    anomalies = []
    for i, e in enumerate(entries):
        data = e.get("data", {})
        # Check for inventory fluctuations
        if i > 0:
            prev_inv = entries[i-1].get("data", {}).get("inventory_base", 0)
            curr_inv = data.get("inventory_base", 0)
            if abs(curr_inv - prev_inv) > 50:
                anomalies.append({
                    "type": "inventory_spike",
                    "time": e.get("ts", ""),
                    "change": curr_inv - prev_inv
                })
    
    return {
        "status": "ok",
        "entries_count": len(entries),
        "avg_price": round(avg_price, 4),
        "min_price": round(min_price, 4),
        "max_price": round(max_price, 4),
        "volatility_pct": round(volatility, 2),
        "avg_spread_pct": round(avg_spread, 2),
        "avg_inventory": round(avg_inventory, 2),
        "anomalies": anomalies[:5]  # Limit to 5
    }


def analyze_orderbook(market: str) -> Dict[str, Any]:
    """Analyze orderbook data for a market."""
    filepath = DATA_DIR / f"orderbook_{market}.jsonl"
    entries = load_jsonl(filepath)
    
    if not entries:
        return {"status": "no_data"}
    
    # Check for empty orderbooks
    empty_count = 0
    for e in entries:
        ob = e.get("data", {}).get("orderbook", {})
        asks = ob.get("asks", {}).get("price", [])
        bids = ob.get("bids", {}).get("price", [])
        if not asks and not bids:
            empty_count += 1
    
    empty_pct = (empty_count / len(entries)) * 100 if entries else 0
    
    return {
        "status": "ok",
        "entries_count": len(entries),
        "empty_orderbooks_pct": round(empty_pct, 1),
        "is_problematic": empty_pct > 50
    }


def get_markets() -> List[str]:
    """Get list of markets from snapshot files."""
    markets = []
    for f in DATA_DIR.glob("snapshot_*.jsonl"):
        market = f.stem.replace("snapshot_", "")
        markets.append(market)
    return sorted(markets)


def generate_daily_report(target_date: date = None) -> str:
    """Generate daily report in markdown format."""
    if target_date is None:
        target_date = date.today()
    
    date_str = target_date.strftime("%Y-%m-%d")
    metrics = load_metrics()
    markets = get_markets()
    
    # Analyze all markets
    market_analysis = {}
    problematic_markets = []
    top_performers = []
    
    for market in markets:
        snapshot = analyze_snapshots(market)
        orderbook = analyze_orderbook(market)
        
        market_analysis[market] = {
            "snapshot": snapshot,
            "orderbook": orderbook
        }
        
        if orderbook.get("is_problematic"):
            problematic_markets.append(market)
        
        if snapshot.get("status") == "ok":
            top_performers.append({
                "market": market,
                "volatility": snapshot.get("volatility_pct", 0),
                "spread": snapshot.get("avg_spread_pct", 0),
                "price": snapshot.get("avg_price", 0)
            })
    
    # Sort by spread (lower is better for market making)
    top_performers.sort(key=lambda x: x["spread"])
    
    # Build markdown report
    report = f"""# Daily Report - {date_str}

## Executive Summary

- **Markets Analyzed**: {len(markets)}
- **Problematic Markets**: {len(problematic_markets)}
- **Data Quality**: {"Good" if len(problematic_markets) < 3 else "Issues Detected"}

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Total Trades | {metrics.get('total_trades', 0)} |
| Orders Placed | {metrics.get('orders_placed', 0)} |
| Orders Cancelled | {metrics.get('orders_cancelled', 0)} |
| Realized P&L | {metrics.get('realized_pnl', 0):+.4f} Iron |

---

## Top Markets by Spread (Best for Market Making)

| Market | Avg Price | Spread | Volatility |
|--------|-----------|--------|------------|
"""
    
    for m in top_performers[:10]:
        report += f"| {m['market']} | {m['price']:.4f} | {m['spread']:.2f}% | {m['volatility']:.2f}% |\n"
    
    report += """
---

## Problematic Markets

"""
    if problematic_markets:
        report += "| Market | Issue |\n|--------|-------|\n"
        for m in problematic_markets:
            report += f"| {m} | Empty orderbook >50% of time |\n"
    else:
        report += "*No problematic markets detected.*\n"
    
    report += """
---

## Anomalies Detected

"""
    anomaly_count = 0
    for market, data in market_analysis.items():
        anomalies = data.get("snapshot", {}).get("anomalies", [])
        for a in anomalies:
            report += f"- **{market}** ({a.get('time', '')[:19]}): {a.get('type')} - change: {a.get('change')}\n"
            anomaly_count += 1
    
    if anomaly_count == 0:
        report += "*No anomalies detected.*\n"
    
    report += """
---

## Market Details

<details>
<summary>Click to expand full market analysis</summary>

| Market | Status | Entries | Avg Price | Volatility | Spread |
|--------|--------|---------|-----------|------------|--------|
"""
    
    for market in sorted(market_analysis.keys()):
        data = market_analysis[market]
        snap = data.get("snapshot", {})
        if snap.get("status") == "ok":
            report += f"| {market} | ✓ | {snap.get('entries_count', 0)} | {snap.get('avg_price', 0):.4f} | {snap.get('volatility_pct', 0):.2f}% | {snap.get('avg_spread_pct', 0):.2f}% |\n"
        else:
            report += f"| {market} | ✗ | 0 | - | - | - |\n"
    
    report += """
</details>

---

## Recommendations for LLM Analysis

1. **Strategy Optimization**: Consider widening spreads for high-volatility markets
2. **Capital Allocation**: Focus capital on top 10 markets by spread efficiency
3. **Risk Management**: Monitor problematic markets for API issues

---

*Generated at: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "*\n"
    
    return report


def generate_market_profiles() -> str:
    """Generate market profiles YAML for LLM context."""
    markets = get_markets()
    
    yaml_content = """# Market Profiles
# Auto-generated for LLM context
# Last updated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """

"""
    
    for market in markets:
        snapshot = analyze_snapshots(market)
        orderbook = analyze_orderbook(market)
        
        base, quote = market.split("_")
        
        # Determine characteristics
        if snapshot.get("status") == "ok":
            vol = snapshot.get("volatility_pct", 0)
            spread = snapshot.get("avg_spread_pct", 0)
            price = snapshot.get("avg_price", 0)
            
            vol_level = "low" if vol < 5 else ("medium" if vol < 15 else "high")
            liquidity = "high" if spread < 4 else ("medium" if spread < 10 else "low")
            
            status = "disabled" if orderbook.get("is_problematic") else "active"
            
            yaml_content += f"""{market}:
  base_asset: {base}
  quote_asset: {quote}
  avg_price: {price:.4f}
  avg_spread: {spread:.2f}%
  volatility: {vol_level}
  liquidity: {liquidity}
  status: {status}
  data_points: {snapshot.get('entries_count', 0)}
  notes: "{
    'API issues - empty orderbooks' if orderbook.get('is_problematic') 
    else 'Stable market' if vol_level == 'low' 
    else 'Volatile - adjust spreads'}"

"""
        else:
            yaml_content += f"""{market}:
  base_asset: {base}
  quote_asset: {quote}
  status: no_data
  notes: "No snapshot data available"

"""
    
    return yaml_content


def main():
    parser = argparse.ArgumentParser(description="Generate LLM-optimized reports")
    parser.add_argument("--date", type=str, help="Specific date (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true", help="Generate all reports")
    args = parser.parse_args()
    
    ensure_dirs()
    
    # Generate daily report
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = date.today()
    
    print(f"Generating daily report for {target_date}...")
    report = generate_daily_report(target_date)
    
    report_path = REPORTS_DIR / "daily" / f"{target_date}.md"
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"  Saved: {report_path}")
    
    # Generate market profiles
    print("Generating market profiles...")
    profiles = generate_market_profiles()
    
    profiles_path = REPORTS_DIR / "analysis" / "market_profiles.yaml"
    with open(profiles_path, 'w') as f:
        f.write(profiles)
    print(f"  Saved: {profiles_path}")
    
    print("\nDone! Reports generated successfully.")
    print(f"\nFor LLM analysis, share these files:")
    print(f"  - {report_path}")
    print(f"  - {profiles_path}")


if __name__ == "__main__":
    main()
