
import asyncio
import aiohttp
import json

API_BASE_URL = "https://craft.blocky.com.br/api/v1"

async def fetch_candles(market="diam_iron", timeframe="4H", count=100):
    # Map timeframe string to nanoseconds
    tf_map = {
        "1m": 60000000000,
        "5m": 300000000000,
        "15m": 900000000000,
        "1H": 3600000000000,
        "4H": 14400000000000,
        "1D": 86400000000000,
        "1W": 604800000000000
    }
    
    tf_ns = tf_map.get(timeframe, 14400000000000)
    market_symbol = market.replace('-', '_')
    url = f"{API_BASE_URL}/markets/{market_symbol}/ohlcv?timeframe={tf_ns}"
    
    print(f"Fetching: {url}")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            print(f"Status: {response.status}")
            data = await response.json(content_type=None)
            
            if not data:
                print("Empty data")
                return
                
            opens = data.get("open", [])
            print(f"Total opens: {len(opens)}")
            if len(opens) > 0:
                print(f"First 5 opens: {opens[:5]}")
                print(f"Last 5 opens: {opens[-5:]}")
            
            timestamps = data.get("timestamp", [])
            num_candles = len(timestamps)
            
            start_idx = max(0, num_candles - count)
            print(f"Processing range: {start_idx} to {num_candles}")
            
            candles = []
            for i in range(start_idx, num_candles):
                try:
                    op = float(opens[i]) if i < len(opens) else 0
                    candles.append(op)
                except Exception as e:
                    print(f"Error parsing index {i}: {e}")
            
            print(f"Processed candles count: {len(candles)}")
            if candles:
                print(f"First processed open: {candles[0]}")
                print(f"Last processed open: {candles[-1]}")

if __name__ == "__main__":
    asyncio.run(fetch_candles())
