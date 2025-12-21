import asyncio
import os
import sys
import logging
from typing import List

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from config import get_config
from blocky.async_client import AsyncBlocky

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("cleaner")

async def clean_orders():
    try:
        config = get_config()
    except Exception as e:
        logger.error(f"Config error: {e}")
        return

    client = AsyncBlocky(
        api_key=config.api.api_key,
        endpoint=config.api.endpoint
    )

    logger.info("🔪 Starting Order Cleanup Tool...")
    logger.info(f"Target: {config.api.endpoint}")

    total_cancelled = 0
    
    try:
        while True:
            # 1. Fetch all open orders
            logger.info("Fetching open orders...")
            all_orders = []
            cursor = None
            
            while True:
                response = await client.get_orders(
                    statuses=["open", "pending", "new"], 
                    limit=100, 
                    cursor=cursor
                )
                
                if not response.get("success"):
                    logger.error(f"Failed to fetch orders: {response}")
                    break
                
                page_orders = response.get("orders", [])
                # Filter out already cancelled ones just in case API returns them
                page_orders = [o for o in page_orders if o.get("status") in ["open", "pending", "new"]]
                
                all_orders.extend(page_orders)
                
                cursor = response.get("next_cursor")
                if not cursor:
                    break
            
            if not all_orders:
                logger.info("✅ No open orders found! Cleanup complete.")
                break
                
            logger.info(f"Found {len(all_orders)} open orders. Cancelling...")
            
            # 2. Cancel in batches
            batch_size = 20 # Rate limit safe batch
            for i in range(0, len(all_orders), batch_size):
                batch = all_orders[i:i+batch_size]
                tasks = []
                for order in batch:
                    oid = order.get("id") or order.get("order_id")
                    tasks.append(client.cancel_order(oid))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Count success
                for res in results:
                    if not isinstance(res, Exception):
                        total_cancelled += 1
                
                print(f"\rProgress: {total_cancelled} orders cancelled...", end="")
                await asyncio.sleep(0.5) # Rate limit checking mechanism
            
            print("") # Newline
            logger.info("Batch complete. Re-checking...")
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("\nStopped by user.")
    finally:
        await client.close()
        logger.info(f"Cleanup finished. Total cancelled: {total_cancelled}")

if __name__ == "__main__":
    asyncio.run(clean_orders())
