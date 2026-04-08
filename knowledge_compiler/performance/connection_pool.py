#!/usr/bin/env python3
"""
P5-03: Connection Pool - Notion API connection pooling with async support

Provides:
- HTTP connection pooling for Notion API
- Rate limiting (Notion: 3 req/s)
- Retry mechanism with exponential backoff
- Async/await support for concurrent requests
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Callable, Awaitable
from collections import deque
from functools import wraps

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None

logger = logging.getLogger(__name__)


# Notion API rate limit: 3 requests per second
NOTION_RATE_LIMIT = 3.0
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_CONNECTIONS = 100
DEFAULT_MAX_RETRIES = 3


@dataclass
class RequestResult:
    """Result of an API request"""
    success: bool
    status_code: int | None = None
    data: dict | None = None
    error: str | None = None
    elapsed_ms: float = 0
    retry_count: int = 0


class RateLimiter:
    """
    Token bucket rate limiter for Notion API

    Enforces 3 req/s limit with burst allowance
    """

    def __init__(self, rate: float = NOTION_RATE_LIMIT, burst: int = 5):
        """
        Initialize rate limiter

        Args:
            rate: Requests per second
            burst: Maximum burst size
        """
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        """Lazily create asyncio.Lock to avoid requiring event loop at init time"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def acquire(self, tokens: int = 1) -> None:
        """
        Acquire tokens (async)

        Args:
            tokens: Number of tokens to acquire
        """
        async with self._get_lock():
            now = time.time()
            elapsed = now - self.last_update
            # Refill tokens based on elapsed time
            self.tokens = min(
                self.burst,
                self.tokens + elapsed * self.rate
            )
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return

            # Wait for enough tokens
            wait_time = (tokens - self.tokens) / self.rate
            self.tokens = 0
            self.last_update = now + wait_time

        await asyncio.sleep(wait_time)

    def acquire_sync(self, tokens: int = 1) -> None:
        """
        Acquire tokens (synchronous)

        Args:
            tokens: Number of tokens to acquire
        """
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(
            self.burst,
            self.tokens + elapsed * self.rate
        )
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return

        # Wait for enough tokens
        wait_time = (tokens - self.tokens) / self.rate
        time.sleep(wait_time)
        self.tokens = 0
        self.last_update = time.time() + wait_time / self.rate


class NotionConnectionPool:
    """
    Connection pool for Notion API requests

    Features:
    - Connection pooling (HTTPAdapter for sync, aiohttp for async)
    - Rate limiting (3 req/s)
    - Retry with exponential backoff
    - Timeout handling
    """

    def __init__(
        self,
        api_key: str | None = None,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        """
        Initialize connection pool

        Args:
            api_key: Notion API key (defaults to NOTION_API_KEY env var)
            max_connections: Maximum concurrent connections
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        import os

        self.api_key = api_key or os.environ.get("NOTION_API_KEY")
        if not self.api_key:
            raise ValueError("NOTION_API_KEY not found")

        self.max_connections = max_connections
        self.timeout = timeout
        self.max_retries = max_retries

        # Rate limiter
        self.rate_limiter = RateLimiter(rate=NOTION_RATE_LIMIT)

        # Session (requests)
        self._session: Any = None
        self._aiohttp_session: Any = None

        # Statistics
        self._total_requests = 0
        self._total_retries = 0
        self._total_errors = 0
        self._last_reset = time.time()

    def _get_session(self) -> Any:
        """Get or create requests session with pooling"""
        if not HAS_REQUESTS:
            raise RuntimeError("requests package not installed")

        if self._session is None:
            self._session = requests.Session()

            # Configure retry strategy
            retry_strategy = Retry(
                total=self.max_retries,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST", "PATCH", "DELETE"],
            )

            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=self.max_connections,
                pool_maxsize=self.max_connections,
            )

            self._session.mount("https://", adapter)
            self._session.mount("http://", adapter)

        return self._session

    async def _get_aiohttp_session(self) -> Any:
        """Get or create aiohttp session"""
        if not HAS_AIOHTTP:
            raise RuntimeError("aiohttp package not installed")

        if self._aiohttp_session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=self.max_connections,
            )

            self._aiohttp_session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json",
                },
            )

        return self._aiohttp_session

    def _request(
        self,
        method: str,
        url: str,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> RequestResult:
        """
        Make synchronous request

        Args:
            method: HTTP method
            url: Request URL
            json: Request body
            headers: Additional headers

        Returns:
            RequestResult
        """
        start = time.time()

        # Apply rate limiting
        self.rate_limiter.acquire_sync()

        # Prepare headers
        req_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        if headers:
            req_headers.update(headers)

        try:
            session = self._get_session()
            response = session.request(
                method=method,
                url=url,
                json=json,
                headers=req_headers,
                timeout=self.timeout,
            )

            elapsed_ms = (time.time() - start) * 1000
            self._total_requests += 1

            if response.status_code >= 400:
                self._total_errors += 1
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", "Unknown error")
                except Exception:
                    error_msg = response.text or f"HTTP {response.status_code}"

                return RequestResult(
                    success=False,
                    status_code=response.status_code,
                    error=error_msg,
                    elapsed_ms=elapsed_ms,
                )

            return RequestResult(
                success=True,
                status_code=response.status_code,
                data=response.json() if response.text else None,
                elapsed_ms=elapsed_ms,
            )

        except requests.exceptions.Timeout as e:
            self._total_errors += 1
            return RequestResult(
                success=False,
                error=f"Timeout: {e}",
                elapsed_ms=(time.time() - start) * 1000,
            )

        except Exception as e:
            self._total_errors += 1
            return RequestResult(
                success=False,
                error=f"Request failed: {e}",
                elapsed_ms=(time.time() - start) * 1000,
            )

    async def _request_async(
        self,
        method: str,
        url: str,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> RequestResult:
        """
        Make async request

        Args:
            method: HTTP method
            url: Request URL
            json: Request body
            headers: Additional headers

        Returns:
            RequestResult
        """
        start = time.time()

        # Apply rate limiting
        await self.rate_limiter.acquire()

        # Prepare headers
        req_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        if headers:
            req_headers.update(headers)

        retry_count = 0

        while retry_count <= self.max_retries:
            try:
                session = await self._get_aiohttp_session()

                async with session.request(
                    method=method,
                    url=url,
                    json=json,
                    headers=req_headers,
                ) as response:
                    elapsed_ms = (time.time() - start) * 1000
                    self._total_requests += 1

                    if response.status >= 400:
                        # Check if we should retry
                        if response.status in [429, 500, 502, 503, 504] and retry_count < self.max_retries:
                            retry_count += 1
                            self._total_retries += 1
                            # Exponential backoff
                            await asyncio.sleep(0.5 * (2 ** retry_count))
                            continue

                        self._total_errors += 1
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get("message", "Unknown error")
                        except Exception:
                            error_msg = await response.text()

                        return RequestResult(
                            success=False,
                            status_code=response.status,
                            error=error_msg,
                            elapsed_ms=elapsed_ms,
                            retry_count=retry_count,
                        )

                    data = None
                    if response.content_length:
                        data = await response.json()

                    return RequestResult(
                        success=True,
                        status_code=response.status,
                        data=data,
                        elapsed_ms=elapsed_ms,
                        retry_count=retry_count,
                    )

            except asyncio.TimeoutError as e:
                if retry_count < self.max_retries:
                    retry_count += 1
                    self._total_retries += 1
                    await asyncio.sleep(0.5 * (2 ** retry_count))
                    continue

                self._total_errors += 1
                return RequestResult(
                    success=False,
                    error=f"Timeout: {e}",
                    elapsed_ms=(time.time() - start) * 1000,
                    retry_count=retry_count,
                )

            except Exception as e:
                if retry_count < self.max_retries:
                    retry_count += 1
                    self._total_retries += 1
                    await asyncio.sleep(0.5 * (2 ** retry_count))
                    continue

                self._total_errors += 1
                return RequestResult(
                    success=False,
                    error=f"Request failed: {e}",
                    elapsed_ms=(time.time() - start) * 1000,
                    retry_count=retry_count,
                )

        return RequestResult(
            success=False,
            error="Max retries exceeded",
            elapsed_ms=(time.time() - start) * 1000,
            retry_count=retry_count,
        )

    def get(self, url: str, headers: dict | None = None) -> RequestResult:
        """GET request (sync)"""
        return self._request("GET", url, headers=headers)

    async def get_async(self, url: str, headers: dict | None = None) -> RequestResult:
        """GET request (async)"""
        return await self._request_async("GET", url, headers=headers)

    def post(
        self, url: str, json: dict, headers: dict | None = None
    ) -> RequestResult:
        """POST request (sync)"""
        return self._request("POST", url, json=json, headers=headers)

    async def post_async(
        self, url: str, json: dict, headers: dict | None = None
    ) -> RequestResult:
        """POST request (async)"""
        return await self._request_async("POST", url, json=json, headers=headers)

    def patch(
        self, url: str, json: dict, headers: dict | None = None
    ) -> RequestResult:
        """PATCH request (sync)"""
        return self._request("PATCH", url, json=json, headers=headers)

    async def patch_async(
        self, url: str, json: dict, headers: dict | None = None
    ) -> RequestResult:
        """PATCH request (async)"""
        return await self._request_async("PATCH", url, json=json, headers=headers)

    def get_statistics(self) -> dict:
        """Get connection pool statistics"""
        return {
            "total_requests": self._total_requests,
            "total_retries": self._total_retries,
            "total_errors": self._total_errors,
            "error_rate": (
                self._total_errors / self._total_requests if self._total_requests > 0 else 0
            ),
            "uptime_seconds": time.time() - self._last_reset,
        }

    def reset_statistics(self) -> None:
        """Reset statistics"""
        self._total_requests = 0
        self._total_retries = 0
        self._total_errors = 0
        self._last_reset = time.time()

    async def close(self) -> None:
        """Close all sessions"""
        if self._aiohttp_session:
            await self._aiohttp_session.close()
            self._aiohttp_session = None

        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, *args):
        """Context manager exit"""
        if self._session:
            self._session.close()


async def create_notion_pool(
    api_key: str | None = None,
    max_connections: int = DEFAULT_MAX_CONNECTIONS,
    timeout: int = DEFAULT_TIMEOUT,
) -> NotionConnectionPool:
    """
    Factory function to create Notion connection pool

    Args:
        api_key: Notion API key
        max_connections: Maximum concurrent connections
        timeout: Request timeout

    Returns:
        Configured NotionConnectionPool
    """
    return NotionConnectionPool(
        api_key=api_key,
        max_connections=max_connections,
        timeout=timeout,
    )


# Export main classes
__all__ = [
    "NotionConnectionPool",
    "create_notion_pool",
    "RateLimiter",
    "RequestResult",
]
