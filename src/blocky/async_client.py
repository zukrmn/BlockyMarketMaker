"""
Async HTTP client for the Blocky API using aiohttp.
Provides the same interface as the sync client but without blocking.
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = 0
    HALF_OPEN = 1
    OPEN = 2


class AsyncRateLimiter:
    """Async-safe sliding window rate limiter."""
    
    def __init__(self, max_requests: int = 30, window_seconds: float = 1.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.timestamps: List[float] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        async with self._lock:
            now = time.time()
            
            # Remove old timestamps
            cutoff = now - self.window_seconds
            self.timestamps = [t for t in self.timestamps if t > cutoff]
            
            # Wait if at limit
            if len(self.timestamps) >= self.max_requests:
                sleep_time = self.timestamps[0] - cutoff
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            
            self.timestamps.append(time.time())


class AsyncCircuitBreaker:
    """Async circuit breaker pattern for fault tolerance."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.half_open_calls = 0
                    logger.info("Circuit breaker: HALF_OPEN")
                else:
                    raise CircuitBreakerOpen("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except RateLimitException:
            # Don't count rate limits as system failures
            raise
        except Exception as e:
            await self._on_failure()
            raise
    
    async def _on_success(self) -> None:
        async with self._lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.half_open_calls += 1
                if self.half_open_calls >= self.half_open_max_calls:
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    logger.info("Circuit breaker: CLOSED (recovered)")
            else:
                self.failure_count = 0
    
    async def _on_failure(self) -> None:
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.warning("Circuit breaker: OPEN")


class RateLimitException(Exception):
    """Raised on 429 Too Many Requests."""
    pass


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""
    pass




class AsyncBlocky:
    """
    Async client for the Blocky API.
    
    Provides async versions of all API methods using aiohttp.
    """
    
    def __init__(
        self,
        api_key: str,
        endpoint: str = "https://craft.blocky.com.br/api/v1",
        rate_limit: int = 30,
        circuit_breaker_threshold: int = 5
    ):
        self.api_key = api_key
        self.BASE_URL = endpoint
        
        self.rate_limiter = AsyncRateLimiter(max_requests=rate_limit)
        self.circuit_breaker = AsyncCircuitBreaker(failure_threshold=circuit_breaker_threshold)
        
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {"X-API-KEY": self.api_key}
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session
    
    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        ignore_status_codes: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Make an async HTTP request with rate limiting and circuit breaker."""
        await self.rate_limiter.acquire()
        
        async def make_request():
            session = await self._get_session()
            url = f"{self.BASE_URL}/{endpoint}"
            
            async with session.request(method, url, params=params, json=json) as response:
                try:
                    data = await response.json(content_type=None)
                except:
                   # Fallback if empty or invalid json
                   data = {}
                
                if response.status == 429:
                    raise RateLimitException("Rate limit exceeded")

                if ignore_status_codes and response.status in ignore_status_codes:
                     return data
                
                if response.status >= 400:
                    error_msg = data.get("message", str(data))
                    raise Exception(f"API Error {response.status}: {error_msg}")
                
                return data
        
        return await self.circuit_breaker.call(make_request)
    
    # Market endpoints
    async def get_markets(self, get_tickers: bool = False) -> Dict[str, Any]:
        """Get all available markets."""
        params = {"tickers": "true"} if get_tickers else None
        return await self._request("GET", "markets", params=params)
    
    async def get_ticker(self, market: str) -> Dict[str, Any]:
        """Get ticker for a specific market."""
        return await self._request("GET", f"markets/{market}/ticker")
    
    async def get_orderbook(self, market: str) -> Dict[str, Any]:
        """Get orderbook for a market."""
        return await self._request("GET", f"markets/{market}/orderbook")
    
    async def get_ohlcv(
        self,
        market: str,
        timeframe: str = "1H",
        limit: int = 24
    ) -> Dict[str, Any]:
        """Get OHLCV candles."""
        params = {"timeframe": timeframe, "limit": limit}
        return await self._request("GET", f"markets/{market}/ohlcv", params=params)
    
    # Wallet endpoints
    async def get_wallets(self) -> Dict[str, Any]:
        """Get all wallets."""
        return await self._request("GET", "wallets")
    
    async def get_wallet(self, currency: str) -> Dict[str, Any]:
        """Get specific wallet."""
        return await self._request("GET", f"wallets/{currency}")
    
    # Order endpoints
    async def get_orders(
        self,
        statuses: Optional[List[str]] = None,
        markets: Optional[List[str]] = None,
        limit: int = 50,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get orders with filters."""
        params = {"limit": limit}
        if statuses:
            params["status"] = ",".join(statuses)
        if markets:
            params["market"] = ",".join(markets)
        if cursor:
            params["cursor"] = cursor
        return await self._request("GET", "orders", params=params)
    
    async def create_order(
        self,
        market: str,
        side: str,
        type_: str,
        price: str,
        quantity: str
    ) -> Dict[str, Any]:
        """Create a new order."""
        payload = {
            "market": market,
            "side": side,
            "type": type_,
            "price": price,
            "quantity": quantity
        }
        return await self._request("POST", "orders", json=payload)
    
    async def cancel_order(self, order_id: int) -> Dict[str, Any]:
        """Cancel a specific order."""
        return await self._request("DELETE", f"orders/{order_id}", ignore_status_codes=[404])
    
    async def cancel_orders(self, market: Optional[str] = None) -> Dict[str, Any]:
        """Cancel all orders, optionally for a specific market."""
        endpoint = f"orders?market={market}" if market else "orders"
        return await self._request("DELETE", endpoint, ignore_status_codes=[404])
    
    # Trade endpoints
    async def get_trades(
        self,
        limit: int = 50,
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """Get recent trades."""
        params = {"limit": limit, "sort": sort_order}
        return await self._request("GET", "trades", params=params)
    
    # Supply metrics
    async def get_supply_metrics(self) -> Dict[str, Any]:
        """Get item supply metrics (Bypasses Circuit Breaker)."""
        # Manual request to avoid tripping CB on 404s (non-critical)
        await self.rate_limiter.acquire()
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/metrics/supply"
            async with session.get(url) as response:
                if response.status == 404:
                    return {} # Return empty if not found
                    
                data = await response.json(content_type=None) # Safe decode
                if response.status >= 400:
                    # Log but don't raise to breaker
                    logger.warning(f"Metrics API error {response.status}: {data}")
                    return {}
                return data
        except Exception as e:
            logger.warning(f"Failed to fetch metrics: {e}")
            return {}
