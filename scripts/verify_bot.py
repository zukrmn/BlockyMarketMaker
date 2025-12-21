import asyncio
import unittest
from unittest.mock import MagicMock, patch
from bot import MarketMaker

class TestMarketMaker(unittest.IsolatedAsyncioTestCase):
    async def test_run_logic(self):
        # Mock the Blocky client
        mock_client = MagicMock()
        
        # Mock get_markets
        mock_client.get_markets.return_value = {
            "success": True, 
            "markets": [{"market": "ston_iron"}, {"market": "olog_iron"}]
        }
        
        # Mock get_wallets (Crucial for inventory check)
        mock_client.get_wallets.return_value = {
            "success": True,
            "wallets": [
                {"currency": "ston", "balance": "100"},
                {"currency": "iron", "balance": "1000000"}, # Enough for buys
                {"currency": "olog", "balance": "100"}
            ]
        }
        
        # Mock get_orders (Empty list = no current orders)
        mock_client.get_orders.return_value = {
            "success": True,
            "orders": []
        }

        # Mock ticker/price fallback if needed (though PriceModel is patched inside bot, we might need to patch it too or rely on its internal mocks)
        # But wait, PriceModel does network calls. usage in bot.py: self.price_model.calculate_fair_price(market)
        # We need to patch PriceModel inside bot.py to avoid real network calls
        
        mock_client.create_order.return_value = {"order_id": 123, "status": "open"}
        
        # Patch Blocky AND PriceModel AND WebSocket
        with patch('bot.Blocky', return_value=mock_client), \
             patch('bot.PriceModel') as MockPriceModel, \
             patch('bot.BlockyWebSocket') as MockWS:
            
            # Setup MockPrice
            mock_price_instance = MockPriceModel.return_value
            mock_price_instance.calculate_fair_price.return_value = 10.00 # Reasonable price for testing qty > 0.01

            # Setup Mock WS
            mock_ws_instance = MockWS.return_value
            mock_ws_instance.connect = MagicMock(return_value=asyncio.Future())
            mock_ws_instance.connect.return_value.set_result(None)
            mock_ws_instance.subscribe_transactions = MagicMock(return_value=asyncio.Future())
            mock_ws_instance.subscribe_transactions.return_value.set_result(None)
            mock_ws_instance.subscribe_orderbook = MagicMock(return_value=asyncio.Future())
            mock_ws_instance.subscribe_orderbook.return_value.set_result(None)
            mock_ws_instance.run_forever = MagicMock(return_value=asyncio.Future())
            
            bot = MarketMaker("fake_key", "endpoint")
            
            # Ensure markets were loaded
            self.assertEqual(len(bot.markets), 2)
            
            # Run one iteration of place_orders_parallel
            await bot.place_orders_parallel()
                
            # Verify calls
            mock_client.get_orders.assert_called()
            mock_client.get_wallets.assert_called()
            # mock_client.get_balances.assert_called()
            
            # Verify orders were placed (4 total: 2 per market)
            # Since async, order isn't guaranteed, but count is
            self.assertEqual(mock_client.create_order.call_count, 4)
            
            print("Test Passed: Bot placed correct orders for multiple markets with async logic.")

if __name__ == '__main__':
    unittest.main()
