"""
ACMaker Dashboard Package
Trading dashboard with real-time charts and drawing tools
"""
from .server import TradingDashboard, DashboardServer, AdvancedDashboard
from .candles import CandleCollector, get_collector

__all__ = [
    'TradingDashboard', 
    'DashboardServer', 
    'AdvancedDashboard',
    'CandleCollector',
    'get_collector'
]
