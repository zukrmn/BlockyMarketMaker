import asyncio
import os
import logging
from blocky import Blocky

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

API_KEY = os.environ.get("BLOCKY_API_KEY")
if not API_KEY:
    raise RuntimeError("BLOCKY_API_KEY environment variable is not set.")
API_ENDPOINT = os.environ.get("BLOCKY_API_ENDPOINT", "https://craft.blocky.com.br/api/v1")

async def audit():
    client = Blocky(api_key=API_KEY, endpoint=API_ENDPOINT)
    
    logger.info("Fetching Open Orders...")
    
    # Manual Pagination Loop to be sure
    all_orders = []
    cursor = None
    has_more = True
    
    while has_more:
        try:
            response = client.get_orders(statuses=["open"], limit=50, cursor=cursor)
            if response.get("success"):
                orders = response.get("orders", [])
                if not orders:
                    break
                    
                all_orders.extend(orders)
                
                # Cursor logic
                next_cursor = response.get("next_cursor") or response.get("cursor")
                if next_cursor:
                    cursor = next_cursor
                elif len(orders) >= 50:
                    cursor = orders[-1].get("id") or orders[-1].get("order_id")
                    if not cursor: has_more = False
                else:
                    has_more = False
            else:
                logger.error(f"Error: {response}")
                break
        except Exception as e:
            logger.error(f"Exception: {e}")
            break
            
    logger.info(f"Total Open Orders Found: {len(all_orders)}")
    for o in all_orders:
        logger.info(f"Order: {o['market']} {o['side']} {o['price']} x {o['quantity']} (ID: {o.get('id')})")

if __name__ == "__main__":
    asyncio.run(audit())
