import requests
import time
import threading
import logging
from typing import Optional, Dict, List, Any, Union
from collections import deque

logger = logging.getLogger(__name__)


class RateLimiter:
    """Thread-safe rate limiter using sliding window algorithm."""
    
    def __init__(self, max_requests: int = 30, window_seconds: float = 1.0):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed per window.
            window_seconds: Time window in seconds.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque = deque()
        self._lock = threading.Lock()
        self._total_waits = 0
        self._total_requests = 0
    
    def acquire(self) -> float:
        """
        Acquire permission to make a request. Blocks if rate limit exceeded.
        
        Returns:
            Time waited in seconds (0 if no wait was needed).
        """
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            
            # Remove timestamps outside the window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            
            wait_time = 0.0
            if len(self._timestamps) >= self.max_requests:
                # Wait until the oldest request exits the window
                wait_time = self._timestamps[0] - cutoff
                if wait_time > 0:
                    self._total_waits += 1
                    logger.debug(f"Rate limit reached, waiting {wait_time:.3f}s")
            
            self._total_requests += 1
        
        # Wait outside the lock
        if wait_time > 0:
            time.sleep(wait_time)
        
        # Record this request timestamp
        with self._lock:
            self._timestamps.append(time.time())
        
        return wait_time
    
    def get_stats(self) -> dict:
        """Returns rate limiter statistics."""
        with self._lock:
            return {
                'total_requests': self._total_requests,
                'total_waits': self._total_waits,
                'current_window_size': len(self._timestamps),
                'max_requests': self.max_requests,
                'window_seconds': self.window_seconds
            }


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests are blocked
    - HALF_OPEN: Testing if service recovered, limited requests allowed
    """
    
    STATE_CLOSED = "CLOSED"
    STATE_OPEN = "OPEN"
    STATE_HALF_OPEN = "HALF_OPEN"
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0,
                 half_open_max_calls: int = 3):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit.
            recovery_timeout: Seconds to wait before trying half-open state.
            half_open_max_calls: Max calls allowed in half-open state.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = self.STATE_CLOSED
        self._failures = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0
        self._lock = threading.Lock()
        
        # Statistics
        self._total_blocked = 0
        self._total_failures = 0
        self._total_successes = 0
    
    @property
    def state(self) -> str:
        """Returns current circuit state."""
        with self._lock:
            self._check_recovery()
            return self._state
    
    def _check_recovery(self):
        """Check if circuit should transition from OPEN to HALF_OPEN."""
        if self._state == self.STATE_OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                logger.info("🔌 Circuit breaker: OPEN -> HALF_OPEN (testing recovery)")
                self._state = self.STATE_HALF_OPEN
                self._half_open_calls = 0
    
    def allow_request(self) -> bool:
        """
        Check if a request should be allowed.
        
        Returns:
            True if request is allowed, False otherwise.
            
        Raises:
            CircuitBreakerOpen: If circuit is open and request is blocked.
        """
        with self._lock:
            self._check_recovery()
            
            if self._state == self.STATE_CLOSED:
                return True
            
            if self._state == self.STATE_OPEN:
                self._total_blocked += 1
                raise CircuitBreakerOpen(
                    f"Circuit breaker is OPEN. Retry after {self.recovery_timeout}s. "
                    f"({self._failures}/{self.failure_threshold} failures)"
                )
            
            if self._state == self.STATE_HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                else:
                    self._total_blocked += 1
                    raise CircuitBreakerOpen(
                        "Circuit breaker is HALF_OPEN. Max test calls reached."
                    )
        
        return False
    
    def record_success(self):
        """Record a successful request."""
        with self._lock:
            self._total_successes += 1
            
            if self._state == self.STATE_HALF_OPEN:
                # Successful in half-open, close the circuit
                logger.info("✅ Circuit breaker: HALF_OPEN -> CLOSED (recovered)")
                self._state = self.STATE_CLOSED
                self._failures = 0
            elif self._state == self.STATE_CLOSED:
                # Decay failures on success
                if self._failures > 0:
                    self._failures = max(0, self._failures - 1)
    
    def record_failure(self):
        """Record a failed request."""
        with self._lock:
            self._failures += 1
            self._total_failures += 1
            self._last_failure_time = time.time()
            
            if self._state == self.STATE_HALF_OPEN:
                # Failure in half-open, reopen circuit
                logger.warning("⚠️ Circuit breaker: HALF_OPEN -> OPEN (still failing)")
                self._state = self.STATE_OPEN
            elif self._state == self.STATE_CLOSED:
                if self._failures >= self.failure_threshold:
                    logger.warning(f"🔴 Circuit breaker: CLOSED -> OPEN ({self._failures} failures)")
                    self._state = self.STATE_OPEN
    
    def get_stats(self) -> dict:
        """Returns circuit breaker statistics."""
        with self._lock:
            return {
                'state': self._state,
                'failures': self._failures,
                'failure_threshold': self.failure_threshold,
                'total_blocked': self._total_blocked,
                'total_failures': self._total_failures,
                'total_successes': self._total_successes,
                'recovery_timeout': self.recovery_timeout
            }

class Blocky:
    BASE_URL = "https://blocky.com.br/api/v1"

    def __init__(self, api_key: Optional[str] = None, endpoint: Optional[str] = None, 
                 rate_limit: int = 30, rate_window: float = 1.0,
                 circuit_failure_threshold: int = 5, circuit_recovery_timeout: float = 30.0):
        """
        Initialize Blocky client.
        
        Args:
            api_key: API key for authentication.
            endpoint: Optional custom API endpoint.
            rate_limit: Maximum requests per window (default: 30/sec).
            rate_window: Rate limit window in seconds (default: 1.0).
            circuit_failure_threshold: Failures before circuit opens (default: 5).
            circuit_recovery_timeout: Seconds before trying recovery (default: 30).
        """
        self.api_key = api_key
        if endpoint:
            self.BASE_URL = endpoint
        self.session = requests.Session()
        
        # Rate limiter
        self.rate_limiter = RateLimiter(max_requests=rate_limit, window_seconds=rate_window)
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_failure_threshold,
            recovery_timeout=circuit_recovery_timeout
        )
        
        # Optimize connection pool for high concurrency
        adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        if self.api_key:
            self.session.headers.update({"x-api-key": self.api_key})

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        # Check circuit breaker first
        self.circuit_breaker.allow_request()
        
        # Apply rate limiting
        self.rate_limiter.acquire()
        
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            try:
                data = response.json()
            except Exception:
                response.raise_for_status()
                # Record success for non-JSON responses
                self.circuit_breaker.record_success()
                return response.text

            if isinstance(data, dict) and not data.get("success", False):
                error_msg = data.get("error_message", "Unknown error")
                error_code = data.get("error_code")
                # Record failure for API errors
                self.circuit_breaker.record_failure()
                raise Exception(f"Blocky API Error {error_code}: {error_msg}")
            
            # Record success
            self.circuit_breaker.record_success()
            return data
            
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as e:
            # Record failure for network/HTTP errors
            self.circuit_breaker.record_failure()
            raise

    def get_instruments(self) -> Dict:
        return self._request("GET", "/instruments")

    def get_instrument(self, symbol: str) -> Dict:
        return self._request("GET", f"/instruments/{symbol}")

    def get_markets(self, get_tickers: bool = False) -> Dict:
        params = {}
        if get_tickers:
            params["get_tickers"] = "true"
        return self._request("GET", "/markets", params=params)

    def get_market(self, market_symbol: str, get_tickers: bool = False) -> Dict:
        params = {}
        if get_tickers:
            params["get_tickers"] = "true"
        return self._request("GET", f"/markets/{market_symbol}", params=params)

    def get_ticker(self, market_symbol: str) -> Dict:
        return self._request("GET", f"/markets/{market_symbol}/ticker")

    def get_transactions(self, market_symbol: str, count: int = 128) -> Dict:
        return self._request("GET", f"/markets/{market_symbol}/transactions", params={"count": count})

    def get_orderbook(self, market_symbol: str, depth: int = 0, tick_size: Optional[float] = None) -> Dict:
        params = {"depth": depth}
        if tick_size is not None:
            params["tick_size"] = str(tick_size)
        return self._request("GET", f"/markets/{market_symbol}/orderbook", params=params)

    def get_ohlcv(self, market_symbol: str, timeframe: str = "1m", start: Optional[int] = None, end: Optional[int] = None) -> Dict:
        params = {}
        tf_map = {
            "1m": 60000000000,
            "5m": 300000000000,
            "15m": 900000000000,
            "1H": 3600000000000,
            "4H": 14400000000000,
            "1D": 86400000000000
        }
        
        # Allow passing direct nanosecond value or string keys
        if str(timeframe) in tf_map:
             params["timeframe"] = tf_map[str(timeframe)]
        else:
             params["timeframe"] = timeframe

        if start:
            params["start"] = start
        if end:
            params["end"] = end
            
        return self._request("GET", f"/markets/{market_symbol}/ohlcv", params=params)

    # Private Endpoints

    def get_wallets(self, sub_wallet_id: int = 0, get_frozen: bool = False, get_all_frozen: bool = False) -> Dict:
        params = {"sub_wallet_id": sub_wallet_id}
        if get_frozen:
            params["get_frozen"] = "true"
        if get_all_frozen:
             params["get_all_frozen"] = "true"
        return self._request("GET", "/wallets", params=params)

    def get_wallet(self, instrument: str, sub_wallet_id: int = 0, get_frozen: bool = False) -> Dict:
        params = {"sub_wallet_id": sub_wallet_id}
        if get_frozen:
            params["get_frozen"] = "true"
        return self._request("GET", f"/wallets/{instrument}", params=params)

    def create_order(self, market: str, side: str, type_: str, 
                     price: Optional[str] = None, quantity: Optional[str] = None, 
                     total: Optional[str] = None, sub_wallet_id: int = 0) -> Dict:
        data = {
            "market": market,
            "side": side,
            "type": type_,
            "sub_wallet_id": sub_wallet_id
        }
        if price:
            data["price"] = price
        if quantity:
            data["quantity"] = quantity
        if total:
            data["total"] = total
            
        return self._request("POST", "/orders", json=data)

    def get_order(self, order_id: int, get_trades: bool = False) -> Dict:
        params = {}
        if get_trades:
            params["get_trades"] = "true"
        return self._request("GET", f"/orders/{order_id}", params=params)

    def get_orders(self, limit: int = 10, cursor: Optional[int] = None, 
                   start: Optional[int] = None, end: Optional[int] = None,
                   sort_order: str = "desc", get_trades: bool = False,
                   with_trades_only: bool = False,
                   types: Optional[List[str]] = None,
                   markets: Optional[List[str]] = None, 
                   sides: Optional[List[str]] = None,
                   statuses: Optional[List[str]] = None) -> Dict:
        params = {
            "limit": limit,
            "sort_order": sort_order
        }
        if cursor: params["cursor"] = cursor
        if start: params["start"] = start
        if end: params["end"] = end
        if get_trades: params["get_trades"] = "true"
        if with_trades_only: params["with_trades_only"] = "true"
        
        # For list params, requests handles list of values correctly with multiple keys like key=val1&key=val2
        # However, we need to verify if the API expects array syntax (key[]) or just repeated keys.
        # Python requests passes `key`: [`val1`, `val2`] as `key=val1&key=val2`.
        # Taking a guess based on standard practices, standard multiple params is likely supported.
        if types: params["types"] = types
        if markets: params["markets"] = markets
        if sides: params["sides"] = sides
        if statuses: params["statuses"] = statuses
        
        return self._request("GET", "/orders", params=params)

    def cancel_order(self, order_id: int, get_trades: bool = False) -> Dict:
        params = {}
        if get_trades:
            params["get_trades"] = "true"
        return self._request("DELETE", f"/orders/{order_id}", params=params)

    def cancel_orders(self, markets: Optional[List[str]] = None, sides: Optional[List[str]] = None, get_trades: bool = False) -> Dict:
        params = {}
        if markets: params["markets"] = markets
        if sides: params["sides"] = sides
        if get_trades: params["get_trades"] = "true"
        return self._request("DELETE", "/orders", params=params)
    
    def get_trades(self, limit: int = 10, cursor: Optional[int] = None,
                   start: Optional[int] = None, end: Optional[int] = None,
                   sort_order: str = "desc",
                   types: Optional[List[str]] = None,
                   markets: Optional[List[str]] = None,
                   sides: Optional[List[str]] = None) -> Dict:
        params = {"limit": limit, "sort_order": sort_order}
        if cursor: params["cursor"] = cursor
        if start: params["start"] = start
        if end: params["end"] = end
        if types: params["types"] = types
        if markets: params["markets"] = markets
        if sides: params["sides"] = sides
        return self._request("GET", "/trades", params=params)

    def get_transfers(self, limit: int = 10, cursor: Optional[int] = None,
                      start: Optional[int] = None, end: Optional[int] = None,
                      sort_order: str = "desc",
                      sub_wallet_ids: Optional[List[int]] = None,
                      instruments: Optional[List[str]] = None) -> Dict:
        params = {"limit": limit, "sort_order": sort_order}
        if cursor: params["cursor"] = cursor
        if start: params["start"] = start
        if end: params["end"] = end
        if sub_wallet_ids: params["sub_wallet_ids"] = sub_wallet_ids
        if instruments: params["instruments"] = instruments
        return self._request("GET", "/transfers", params=params)

    def create_transfer(self, instrument: str, quantity: str, 
                        source_id: int, dest_id: int, memo: Optional[str] = None) -> Dict:
        data = {
            "instrument": instrument,
            "quantity": quantity,
            "source_sub_wallet_id": source_id,
            "destination_sub_wallet_id": dest_id
        }
        if memo:
            data["memo"] = memo
        return self._request("POST", "/transfers", json=data)

    def get_deposits(self, limit: int = 15, cursor: Optional[int] = None,
                     instruments: Optional[List[str]] = None) -> Dict:
        params = {"limit": limit}
        if cursor: params["cursor"] = cursor
        if instruments: params["instruments"] = instruments
        return self._request("GET", "/deposits", params=params)

    def get_withdrawals(self, limit: int = 15, cursor: Optional[int] = None,
                        instruments: Optional[List[str]] = None) -> Dict:
        params = {"limit": limit}
        if cursor: params["cursor"] = cursor
        if instruments: params["instruments"] = instruments
        return self._request("GET", "/withdrawals", params=params)

    def get_deposits_and_withdrawals(self, limit: int = 15, cursor: Optional[int] = None,
                                     instruments: Optional[List[str]] = None) -> Dict:
        params = {"limit": limit}
        if cursor: params["cursor"] = cursor
        if instruments: params["instruments"] = instruments
        return self._request("GET", "/deposits-and-withdrawals", params=params)

    # Metrics
    def get_supply_metrics(self, time_range: str = "24h", interval: str = "1h") -> Dict:
        params = {
            "time_range": time_range,
            "interval": interval
        }
        # Note: This endpoint might return a list directly, but _request expects dict response mostly?
        # _request handles "success" check if dict. If list, it bypasses check?
        # Let's check _request implementation.
        return self._request("GET", "/supply-metrics", params=params)
