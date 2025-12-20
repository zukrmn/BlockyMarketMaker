import asyncio
import json
import logging
import websockets
from typing import Dict, Callable, Optional, Any, List

logger = logging.getLogger(__name__)

class BlockyWebSocket:
    def __init__(self, endpoint: str = "wss://blocky.com.br/api/v1/ws/"):
        self.endpoint = endpoint
        self.ws = None
        self.callbacks: Dict[str, Callable] = {}
        self.subscriptions: List[str] = []
        self.running = False
        self._msg_id_counter = 0
        
        # Reconnection settings
        self._reconnect_delay = 1.0  # Initial delay in seconds
        self._max_reconnect_delay = 60.0  # Max delay
        self._reconnect_attempts = 0

    def _get_msg_id(self) -> int:
        self._msg_id_counter += 1
        return self._msg_id_counter

    async def connect(self):
        """Connects to the WebSocket server."""
        self.ws = await websockets.connect(self.endpoint)
        self.running = True
        self._reconnect_delay = 1.0  # Reset on successful connection
        self._reconnect_attempts = 0
        logger.info(f"WebSocket connected to {self.endpoint}")

    async def _reconnect(self):
        """Attempts to reconnect with exponential backoff."""
        while self.running:
            self._reconnect_attempts += 1
            delay = min(self._reconnect_delay * (2 ** (self._reconnect_attempts - 1)), self._max_reconnect_delay)
            
            logger.warning(f"WebSocket disconnected. Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts})...")
            await asyncio.sleep(delay)
            
            try:
                self.ws = await websockets.connect(self.endpoint)
                logger.info(f"WebSocket reconnected successfully after {self._reconnect_attempts} attempts.")
                
                # Re-subscribe to all channels
                for channel in self.subscriptions:
                    msg = {
                        "action": "subscribe",
                        "message_id": self._get_msg_id(),
                        "channel": channel
                    }
                    await self.ws.send(json.dumps(msg))
                    logger.debug(f"Re-subscribed to {channel}")
                
                self._reconnect_delay = 1.0  # Reset on success
                self._reconnect_attempts = 0
                return True
                
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
                continue
        
        return False

    async def subscribe_transactions(self, market: str, callback: Callable):
        channel = f"{market}:transactions"
        self.callbacks[channel] = callback
        await self._subscribe(channel)

    async def subscribe_orderbook(self, market: str, callback: Callable):
        channel = f"{market}:orderbook"
        self.callbacks[channel] = callback
        await self._subscribe(channel)

    async def _subscribe(self, channel: str):
        if not self.ws:
            raise RuntimeError("WebSocket is not connected. Call connect() first.")
        
        msg = {
            "action": "subscribe",
            "message_id": self._get_msg_id(),
            "channel": channel
        }
        await self.ws.send(json.dumps(msg))
        if channel not in self.subscriptions:
            self.subscriptions.append(channel)

    async def run_forever(self):
        """Main loop that handles messages and automatic reconnection."""
        if not self.ws:
            raise RuntimeError("WebSocket is not connected.")
        
        while self.running:
            try:
                async for message in self.ws:
                    data = json.loads(message)
                    
                    # Check if it's a channel message
                    channel = data.get("channel")
                    if channel and channel in self.callbacks:
                        # Using asyncio.create_task to run callback without blocking the loop
                        if asyncio.iscoroutinefunction(self.callbacks[channel]):
                            asyncio.create_task(self.callbacks[channel](data))
                        else:
                            self.callbacks[channel](data)
                            
            except websockets.exceptions.ConnectionClosedError as e:
                logger.warning(f"WebSocket connection closed with error: {e}")
                if self.running:
                    success = await self._reconnect()
                    if not success:
                        break
                        
            except websockets.exceptions.ConnectionClosedOK:
                logger.info("WebSocket connection closed normally.")
                break
                
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                if self.running:
                    success = await self._reconnect()
                    if not success:
                        break

    async def close(self):
        """Gracefully closes the WebSocket connection."""
        self.running = False
        if self.ws:
            await self.ws.close()
            logger.info("WebSocket closed.")
