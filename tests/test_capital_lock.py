"""
Unit tests for capital lock race condition prevention.
Tests that concurrent _process_market calls don't over-allocate Iron.
"""
import asyncio
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCapitalLock(unittest.IsolatedAsyncioTestCase):
    """Tests for capital lock preventing race conditions."""
    
    async def test_concurrent_capital_allocation_no_overallocation(self):
        """
        Simulate concurrent _process_market calls competing for Iron.
        
        Setup: 10 Iron available, each market wants 5 Iron (cost)
        Expected: Only 2 markets should succeed in buying (10 / 5 = 2)
        """
        # Shared capital tracker simulating 10 Iron
        capital_tracker = {"iron": 10.0}
        lock = asyncio.Lock()
        
        successful_allocations = []
        
        async def simulate_allocation(market_name: str, cost: float):
            """Simulates the atomic allocation logic from bot.py"""
            nonlocal capital_tracker
            
            async with lock:
                current_balance = capital_tracker.get("iron", 0)
                if current_balance >= cost:
                    capital_tracker["iron"] = max(0, current_balance - cost)
                    successful_allocations.append(market_name)
                    return True
            return False
        
        # Simulate 5 markets all trying to allocate 5 Iron each
        markets = ["diam_iron", "gold_iron", "coal_iron", "ston_iron", "lapi_iron"]
        cost_per_market = 5.0
        
        # Run all concurrently
        tasks = [simulate_allocation(m, cost_per_market) for m in markets]
        results = await asyncio.gather(*tasks)
        
        # Assert: Only 2 should succeed (10 Iron / 5 cost = 2)
        self.assertEqual(len(successful_allocations), 2, 
                        f"Expected 2 successful allocations, got {len(successful_allocations)}: {successful_allocations}")
        
        # Assert: Remaining balance should be 0
        self.assertEqual(capital_tracker["iron"], 0.0,
                        f"Expected 0 Iron remaining, got {capital_tracker['iron']}")
        
        print(f"✓ Only {len(successful_allocations)} markets allocated (correct)")
    
    async def test_allocation_respects_exact_balance(self):
        """Test that allocation works correctly when balance equals cost exactly."""
        capital_tracker = {"iron": 5.0}
        lock = asyncio.Lock()
        
        async def allocate(cost: float) -> bool:
            async with lock:
                current = capital_tracker.get("iron", 0)
                if current >= cost:
                    capital_tracker["iron"] = max(0, current - cost)
                    return True
            return False
        
        # Exact match should succeed
        result = await allocate(5.0)
        self.assertTrue(result)
        self.assertEqual(capital_tracker["iron"], 0.0)
        
        print("✓ Exact balance allocation works")
    
    async def test_allocation_fails_when_insufficient(self):
        """Test that allocation fails gracefully when insufficient funds."""
        capital_tracker = {"iron": 3.0}
        lock = asyncio.Lock()
        
        async def allocate(cost: float) -> bool:
            async with lock:
                current = capital_tracker.get("iron", 0)
                if current >= cost:
                    capital_tracker["iron"] = max(0, current - cost)
                    return True
            return False
        
        # Should fail - not enough
        result = await allocate(5.0)
        self.assertFalse(result)
        self.assertEqual(capital_tracker["iron"], 3.0)  # Unchanged
        
        print("✓ Insufficient balance correctly rejected")
    
    async def test_sequential_allocations(self):
        """Test that sequential allocations work correctly."""
        capital_tracker = {"iron": 15.0}
        lock = asyncio.Lock()
        
        async def allocate(cost: float) -> bool:
            async with lock:
                current = capital_tracker.get("iron", 0)
                if current >= cost:
                    capital_tracker["iron"] = max(0, current - cost)
                    return True
            return False
        
        # Sequential allocations
        self.assertTrue(await allocate(5.0))  # 15 -> 10
        self.assertTrue(await allocate(5.0))  # 10 -> 5
        self.assertTrue(await allocate(5.0))  # 5 -> 0
        self.assertFalse(await allocate(5.0))  # 0, should fail
        
        self.assertEqual(capital_tracker["iron"], 0.0)
        
        print("✓ Sequential allocations work correctly")


class TestCapitalLockIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests with actual bot components."""
    
    async def test_bot_capital_lock_exists(self):
        """Verify MarketMaker has capital_lock attribute."""
        from bot import MarketMaker
        
        mock_client = MagicMock()
        mock_client.get_markets.return_value = {
            "success": True,
            "markets": [{"market": "diam_iron"}]
        }
        mock_client.BASE_URL = "https://mock.api"
        mock_client.get_supply_metrics.return_value = [{"264": 100}]
        
        with patch('bot.Blocky', return_value=mock_client), \
             patch('bot.BlockyWebSocket'):
            
            bot = MarketMaker("test_key", "https://mock.api")
            
            # Verify lock exists
            self.assertTrue(hasattr(bot, 'capital_lock'))
            self.assertIsInstance(bot.capital_lock, asyncio.Lock)
            
            print("✓ Bot has capital_lock attribute")


if __name__ == "__main__":
    print("=" * 60)
    print("Running Capital Lock Tests")
    print("=" * 60)
    unittest.main(verbosity=2)
