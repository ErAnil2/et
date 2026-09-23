"""httpx client factory + token bucket rate limiter + retry wrapper."""
from __future__ import annotations

import threading
import time

import httpx

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 discover-intel/0.1"
)


class TokenBucket:
    """Thread-safe token bucket. Blocks on acquire() until a token is available."""

    def __init__(self, rate_per_sec: float, capacity: int) -> None:
        self.rate = float(rate_per_sec)
        self.capacity = float(capacity)
        self._tokens = float(capacity)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self.capacity, self._tokens + (now - self._last) * self.rate
                )
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                deficit = 1.0 - self._tokens
                wait = deficit / self.rate
            time.sleep(wait)


def build_client(timeout: float = 10.0) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        http2=True,
        headers={"User-Agent": DEFAULT_UA, "Accept": "*/*"},
    )


def fetch_with_retry(
    client: httpx.Client,
    url: str,
    bucket: TokenBucket | None,
    backoff: tuple[float, float] = (2.0, 4.0),
) -> httpx.Response:
    """One retry on 5xx or connection error. Never retry 4xx (per PRD)."""
    if bucket is not None:
        bucket.acquire()
    try:
        r = client.get(url)
    except (httpx.TransportError, httpx.TimeoutException):
        time.sleep(backoff[0])
        if bucket is not None:
            bucket.acquire()
        return client.get(url)

    if 500 <= r.status_code < 600:
        time.sleep(backoff[0])
        if bucket is not None:
            bucket.acquire()
        return client.get(url)
    return r
