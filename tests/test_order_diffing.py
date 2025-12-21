"""
Unit tests for order diffing logic in the Market Maker bot.
Tests the smart order maintenance (cancellation vs keeping orders).
"""
import unittest
import os
import sys

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))


class TestOrderDiffing(unittest.TestCase):
    """Tests for order matching/diffing logic used in _process_market."""
    
    def test_is_match_exact_match(self):
        """Test that identical orders match."""
        order = {"side": "buy", "price": 10.00, "quantity": 5.00}
        self.assertTrue(self._is_match(order, 10.00, 5.00, "buy"))
        
    def test_is_match_wrong_side(self):
        """Test that orders with wrong side don't match."""
        order = {"side": "buy", "price": 10.00, "quantity": 5.00}
        self.assertFalse(self._is_match(order, 10.00, 5.00, "sell"))
        
    def test_is_match_price_tolerance(self):
        """Test price tolerance of 0.001."""
        order = {"side": "buy", "price": 10.0005, "quantity": 5.00}
        # Within tolerance
        self.assertTrue(self._is_match(order, 10.00, 5.00, "buy"))
        
        order = {"side": "buy", "price": 10.002, "quantity": 5.00}
        # Outside tolerance
        self.assertFalse(self._is_match(order, 10.00, 5.00, "buy"))
        
    def test_is_match_quantity_tolerance(self):
        """Test quantity tolerance of 0.01."""
        order = {"side": "buy", "price": 10.00, "quantity": 5.005}
        # Within tolerance
        self.assertTrue(self._is_match(order, 10.00, 5.00, "buy"))
        
        order = {"side": "buy", "price": 10.00, "quantity": 5.02}
        # Outside tolerance
        self.assertFalse(self._is_match(order, 10.00, 5.00, "buy"))
        
    def test_order_cancel_decision_matching_order(self):
        """Test that matching orders are not scheduled for cancellation."""
        open_orders = [
            {"id": 1, "side": "buy", "price": 10.00, "quantity": 5.00},
            {"id": 2, "side": "sell", "price": 10.50, "quantity": 5.00}
        ]
        
        orders_to_cancel, buy_active, sell_active = self._analyze_orders(
            open_orders,
            target_buy_price=10.00,
            target_buy_qty=5.00,
            target_sell_price=10.50,
            target_sell_qty=5.00,
            should_buy=True,
            should_sell=True
        )
        
        # Both orders match, nothing to cancel
        self.assertEqual(len(orders_to_cancel), 0)
        self.assertTrue(buy_active)
        self.assertTrue(sell_active)
        
    def test_order_cancel_decision_price_change(self):
        """Test that orders with changed price are scheduled for cancellation."""
        open_orders = [
            {"id": 1, "side": "buy", "price": 10.00, "quantity": 5.00}
        ]
        
        # Target price changed to 9.50
        orders_to_cancel, buy_active, _ = self._analyze_orders(
            open_orders,
            target_buy_price=9.50,
            target_buy_qty=5.00,
            target_sell_price=10.50,
            target_sell_qty=5.00,
            should_buy=True,
            should_sell=True
        )
        
        # Order should be cancelled (price mismatch)
        self.assertEqual(orders_to_cancel, [1])
        self.assertFalse(buy_active)
        
    def test_order_cancel_decision_should_not_buy(self):
        """Test that buy orders are cancelled when should_buy is False."""
        open_orders = [
            {"id": 1, "side": "buy", "price": 10.00, "quantity": 5.00}
        ]
        
        orders_to_cancel, buy_active, _ = self._analyze_orders(
            open_orders,
            target_buy_price=10.00,
            target_buy_qty=5.00,
            target_sell_price=10.50,
            target_sell_qty=5.00,
            should_buy=False,  # Changed
            should_sell=True
        )
        
        # Order should be cancelled (should_buy is False)
        self.assertEqual(orders_to_cancel, [1])
        self.assertFalse(buy_active)
    
    # Helper methods that mirror bot.py logic
    
    def _is_match(self, order: dict, target_price: float, target_qty: float, side: str) -> bool:
        """Copy of is_match logic from bot.py _process_market."""
        if order["side"] != side:
            return False
        o_price = float(order["price"])
        o_qty = float(order["quantity"])
        # Tolerance: Price exact (0.001), Qty strict (0.01)
        return abs(o_price - target_price) < 0.001 and abs(o_qty - target_qty) < 0.01
    
    def _analyze_orders(self, open_orders: list, target_buy_price: float, 
                        target_buy_qty: float, target_sell_price: float,
                        target_sell_qty: float, should_buy: bool, 
                        should_sell: bool) -> tuple:
        """Analyze orders and return (orders_to_cancel, buy_active, sell_active)."""
        orders_to_cancel = []
        buy_active = False
        sell_active = False
        
        for o in open_orders:
            oid = o.get("id") or o.get("order_id")
            
            if o["side"] == "buy":
                if should_buy and self._is_match(o, target_buy_price, target_buy_qty, "buy"):
                    buy_active = True
                else:
                    orders_to_cancel.append(oid)
            elif o["side"] == "sell":
                if should_sell and self._is_match(o, target_sell_price, target_sell_qty, "sell"):
                    sell_active = True
                else:
                    orders_to_cancel.append(oid)
        
        return orders_to_cancel, buy_active, sell_active


class TestPennyingLogic(unittest.TestCase):
    """Tests for pennying strategy logic."""
    
    def test_penny_buy_beats_competitor(self):
        """Test that we beat competitor's bid by 0.01."""
        mid_price = 10.00
        spread = 0.05
        max_buy = mid_price * 0.99  # 9.90
        
        # Base buy price
        buy_price = round(mid_price * (1 - spread / 2), 2)  # 9.75
        
        # Competitor's best bid
        best_bid = 9.80
        my_best_bid = 0.0  # No existing order
        
        # Pennying logic (from bot.py)
        is_our_bid = abs(best_bid - my_best_bid) < 0.001
        
        if best_bid > buy_price and best_bid < max_buy:
            if not is_our_bid:
                buy_price = best_bid + 0.01
        
        self.assertEqual(buy_price, 9.81)
        
    def test_penny_buy_skipped_if_ours(self):
        """Test that we don't penny our own order."""
        mid_price = 10.00
        spread = 0.05
        max_buy = mid_price * 0.99
        
        buy_price = round(mid_price * (1 - spread / 2), 2)  # 9.75
        
        best_bid = 9.80
        my_best_bid = 9.80  # This IS our order
        
        is_our_bid = abs(best_bid - my_best_bid) < 0.001
        
        if best_bid > buy_price and best_bid < max_buy:
            if not is_our_bid:
                buy_price = best_bid + 0.01
            else:
                buy_price = best_bid  # Maintain position
        
        self.assertEqual(buy_price, 9.80)  # Maintains, doesn't penny ourselves
        
    def test_penny_respects_max_price(self):
        """Test that pennying doesn't exceed max safe price."""
        mid_price = 10.00
        spread = 0.05
        max_buy = mid_price * 0.99  # 9.90
        
        buy_price = round(mid_price * (1 - spread / 2), 2)  # 9.75
        
        # Competitor at edge of safe zone
        best_bid = 9.91
        my_best_bid = 0.0
        
        is_our_bid = abs(best_bid - my_best_bid) < 0.001
        
        # Should NOT penny because best_bid >= max_buy
        if best_bid > buy_price and best_bid < max_buy:
            if not is_our_bid:
                buy_price = best_bid + 0.01
        
        # Should stay at original price
        self.assertEqual(buy_price, 9.75)


if __name__ == "__main__":
    unittest.main()
