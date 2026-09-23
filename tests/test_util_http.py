import time

import httpx
import pytest

from discover_intel.util import http as httputil


def test_token_bucket_rate_limits():
    b = httputil.TokenBucket(rate_per_sec=5, capacity=5)
    start = time.monotonic()
    for _ in range(10):
        b.acquire()
    elapsed = time.monotonic() - start
    # 10 tokens at 5/s from a bucket of 5 → the last 5 wait ~1s total
    assert elapsed >= 0.8


def test_fetch_with_retry_200(httpx_mock):
    httpx_mock.add_response(url="https://example.com/feed", status_code=200,
                            content=b"<rss/>")
    client = httputil.build_client()
    r = httputil.fetch_with_retry(client, "https://example.com/feed", bucket=None)
    assert r.status_code == 200
    assert r.content == b"<rss/>"


def test_fetch_with_retry_never_retries_404(httpx_mock):
    httpx_mock.add_response(url="https://example.com/feed", status_code=404)
    client = httputil.build_client()
    r = httputil.fetch_with_retry(client, "https://example.com/feed", bucket=None)
    assert r.status_code == 404
    # Only one call was made — pytest-httpx fails at teardown if unexpected extras arrived.


def test_fetch_with_retry_retries_500_once(httpx_mock):
    httpx_mock.add_response(url="https://example.com/feed", status_code=500)
    httpx_mock.add_response(url="https://example.com/feed", status_code=200,
                            content=b"ok")
    client = httputil.build_client()
    r = httputil.fetch_with_retry(client, "https://example.com/feed", bucket=None,
                                  backoff=(0.0, 0.0))
    assert r.status_code == 200


def test_fetch_with_retry_gives_up_after_one_retry(httpx_mock):
    httpx_mock.add_response(url="https://example.com/feed", status_code=502)
    httpx_mock.add_response(url="https://example.com/feed", status_code=502)
    client = httputil.build_client()
    r = httputil.fetch_with_retry(client, "https://example.com/feed", bucket=None,
                                  backoff=(0.0, 0.0))
    assert r.status_code == 502
