"""
Trading helper functions extracted from the main MarketMaker class.
These functions handle specific trading logic components for better testability.
"""
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PriceQuote:
    """Represents calculated buy/sell prices for a market."""
    buy_price: float
    sell_price: float
    mid_price: float
    buy_spread: float
    sell_spread: float


@dataclass
class OrderDecision:
    """Represents the decision of what orders to place/cancel."""
    should_buy: bool
    should_sell: bool
    buy_quantity: float
    sell_quantity: float
    orders_to_cancel: List[Any]
    buy_active: bool
    sell_active: bool


def calculate_quotes(
    mid_price: float,
    buy_spread: float,
    sell_spread: float
) -> Tuple[float, float]:
    """
    Calculate buy and sell prices from mid price and spreads.
    
    Args:
        mid_price: The fair/mid price
        buy_spread: Spread percentage for buy side
        sell_spread: Spread percentage for sell side
        
    Returns:
        Tuple of (buy_price, sell_price)
    """
    buy_price = round(mid_price * (1 - buy_spread / 2), 2)
    sell_price = round(mid_price * (1 + sell_spread / 2), 2)
    return buy_price, sell_price


def apply_pennying(
    buy_price: float,
    sell_price: float,
    mid_price: float,
    ticker: Optional[Dict[str, Any]],
    open_orders: Optional[List[Dict[str, Any]]],
    min_spread_ticks: float = 0.01
) -> Tuple[float, float]:
    """
    Apply pennying strategy to beat competitors by 0.01.
    
    Args:
        buy_price: Initial buy price
        sell_price: Initial sell price  
        mid_price: Fair mid price
        ticker: Current market ticker with bid/ask
        open_orders: Our current open orders
        min_spread_ticks: Minimum price difference
        
    Returns:
        Tuple of (adjusted_buy_price, adjusted_sell_price)
    """
    MAX_BUY = mid_price * 0.99  # Ensure 1% margin from mid
    MIN_SELL = mid_price * 1.01  # Ensure 1% margin from mid
    
    # Identify our current top orders to prevent self-pennying
    my_best_bid = 0.0
    my_best_ask = 0.0
    
    if open_orders:
        for o in open_orders:
            p = float(o.get("price", 0))
            if o["side"] == "buy":
                if p > my_best_bid:
                    my_best_bid = p
            elif o["side"] == "sell":
                if my_best_ask == 0 or p < my_best_ask:
                    my_best_ask = p
    
    if ticker:
        best_bid = float(ticker.get("bid", 0) or 0)
        best_ask = float(ticker.get("ask", 0) or 0)
        
        # Pennying Buy
        is_our_bid = abs(best_bid - my_best_bid) < 0.001
        
        if best_bid > buy_price and best_bid < MAX_BUY:
            if not is_our_bid:
                buy_price = best_bid + 0.01
            else:
                buy_price = best_bid
        
        # Pennying Sell
        is_our_ask = abs(best_ask - my_best_ask) < 0.001 and my_best_ask > 0
        
        if best_ask > 0 and (best_ask < sell_price or sell_price == 0) and best_ask > MIN_SELL:
            if not is_our_ask:
                sell_price = best_ask - 0.01
            else:
                sell_price = best_ask
    
    # Enforce minimum spread
    if buy_price >= sell_price:
        buy_price -= min_spread_ticks
        
        if buy_price < 0:
            buy_price = 0.00
        
        current_spread = sell_price - buy_price
        if current_spread < min_spread_ticks:
            sell_price += (min_spread_ticks - current_spread)
        
        buy_price = round(buy_price, 2)
        sell_price = round(sell_price, 2)
    
    return buy_price, sell_price


def calculate_locked_funds(
    open_orders: List[Dict[str, Any]]
) -> Tuple[float, float]:
    """
    Calculate funds locked in open orders.
    
    Args:
        open_orders: List of open orders
        
    Returns:
        Tuple of (locked_base, locked_quote)
    """
    locked_base = 0.0
    locked_quote = 0.0
    
    for o in open_orders:
        try:
            q = float(o.get("quantity", 0))
            p = float(o.get("price", 0))
            if o["side"] == "sell":
                locked_base += q
            elif o["side"] == "buy":
                locked_quote += (q * p)
        except (ValueError, TypeError, KeyError):
            pass
    
    return locked_base, locked_quote


def calculate_order_quantities(
    buy_price: float,
    sell_price: float,
    quote_balance: float,
    base_balance: float,
    target_value: float,
    max_quantity: float
) -> Tuple[float, float, bool, bool]:
    """
    Calculate order quantities and determine if we should buy/sell.
    
    Args:
        buy_price: Price for buy orders
        sell_price: Price for sell orders
        quote_balance: Available quote currency (Iron)
        base_balance: Available base currency
        target_value: Target order value
        max_quantity: Maximum order quantity
        
    Returns:
        Tuple of (buy_quantity, sell_quantity, should_buy, should_sell)
    """
    check_price = buy_price if buy_price > 0 else (sell_price if sell_price > 0 else 0)
    
    # Dynamic sizing based on capital
    allocated_value = target_value
    if quote_balance < target_value:
        allocated_value = quote_balance
    
    # Min notional check
    if allocated_value < 0.05:
        allocated_value = 0
    
    if check_price > 0 and allocated_value > 0:
        required_qty = allocated_value / check_price
    else:
        required_qty = 0
    
    # Cap at max quantity
    if required_qty > max_quantity:
        required_qty = max_quantity
    
    required_qty = float(f"{required_qty:.2f}")
    
    should_buy = (quote_balance >= (buy_price * required_qty)) and (required_qty > 0)
    
    # Sell quantity logic
    if base_balance > 0 and base_balance < required_qty:
        sell_qty = base_balance
    else:
        sell_qty = required_qty
    
    sell_qty = float(f"{sell_qty:.2f}")
    should_sell = base_balance >= sell_qty and sell_qty > 0
    
    return required_qty, sell_qty, should_buy, should_sell


def is_order_match(
    order: Dict[str, Any],
    target_price: float,
    target_qty: float,
    side: str
) -> bool:
    """
    Check if an order matches the target parameters within tolerance.
    
    Args:
        order: Order dict with side, price, quantity
        target_price: Expected price
        target_qty: Expected quantity
        side: Expected side ('buy' or 'sell')
        
    Returns:
        True if order matches within tolerance
    """
    if order["side"] != side:
        return False
    
    o_price = float(order["price"])
    o_qty = float(order["quantity"])
    
    # Use percentage-based tolerance for price (2% tolerance)
    # and absolute tolerance for quantity (0.5 units)
    # This prevents excessive order flickering when prices fluctuate slightly
    price_tolerance = max(0.02, target_price * 0.02)  # At least 0.02, or 2% of price
    qty_tolerance = max(0.5, target_qty * 0.1)  # At least 0.5, or 10% of quantity
    
    return abs(o_price - target_price) < price_tolerance and abs(o_qty - target_qty) < qty_tolerance


def diff_orders(
    open_orders: List[Dict[str, Any]],
    buy_price: float,
    buy_quantity: float,
    sell_price: float,
    sell_quantity: float,
    should_buy: bool,
    should_sell: bool
) -> Tuple[List[Any], bool, bool]:
    """
    Determine which orders to cancel and which are still active.
    
    Args:
        open_orders: List of current open orders
        buy_price: Target buy price
        buy_quantity: Target buy quantity
        sell_price: Target sell price
        sell_quantity: Target sell quantity
        should_buy: Whether we should have a buy order
        should_sell: Whether we should have a sell order
        
    Returns:
        Tuple of (orders_to_cancel, buy_active, sell_active)
    """
    orders_to_cancel = []
    buy_active = False
    sell_active = False
    
    for o in open_orders:
        oid = o.get("id") or o.get("order_id")
        
        if not oid:
            logger.warning(f"Order missing ID: {o}")
            continue
        
        if o["side"] == "buy":
            if should_buy and is_order_match(o, buy_price, buy_quantity, "buy"):
                buy_active = True
            else:
                orders_to_cancel.append(oid)
        elif o["side"] == "sell":
            if should_sell and is_order_match(o, sell_price, sell_quantity, "sell"):
                sell_active = True
            else:
                orders_to_cancel.append(oid)
    
    return orders_to_cancel, buy_active, sell_active
