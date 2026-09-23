"""Google News URL decoder.

Google News RSS returns URLs shaped like:
  https://news.google.com/rss/articles/CBMi<base64-blob>?oc=5

The base64 blob (URL-safe or standard) contains a small protobuf-shape
payload with the original publisher URL as a plain string. We extract
the first `https?://...` substring and hand it back. If decode fails
or produces no URL, return None — the resolver will fall back to HEAD.
"""
from __future__ import annotations

import base64
import re
from urllib.parse import urlparse

_GNEWS_HOST = "news.google.com"
_ARTICLE_PREFIX = "/rss/articles/"
_URL_IN_BLOB = re.compile(rb"https?://[^\s<>\"'\x00-\x1f]+")


def decode_gnews_url(url: str) -> str | None:
    """Return the publisher URL embedded in a Google News article URL, or None."""
    parsed = urlparse(url)
    if parsed.netloc != _GNEWS_HOST or not parsed.path.startswith(_ARTICLE_PREFIX):
        return None

    article_id = parsed.path[len(_ARTICLE_PREFIX):].split("/", 1)[0]
    if not article_id:
        return None

    for decoder in (_urlsafe_b64, _standard_b64):
        blob = decoder(article_id)
        if blob is None:
            continue
        match = _URL_IN_BLOB.search(blob)
        if match:
            return match.group(0).decode("utf-8", errors="replace").rstrip(".,;:!?")
    return None


def _urlsafe_b64(s: str) -> bytes | None:
    padded = s + "=" * (-len(s) % 4)
    try:
        return base64.urlsafe_b64decode(padded)
    except (ValueError, base64.binascii.Error):
        return None


def _standard_b64(s: str) -> bytes | None:
    padded = s + "=" * (-len(s) % 4)
    try:
        return base64.b64decode(padded, validate=False)
    except (ValueError, base64.binascii.Error):
        return None
