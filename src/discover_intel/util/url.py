"""URL helpers: host extraction and tracking-param stripping."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_EXACT = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid", "yclid"})


def extract_host(url: str) -> str:
    p = urlparse(url if "://" in url else f"//{url}", scheme="")
    return (p.hostname or "").lower()


def strip_tracking(url: str) -> str:
    p = urlparse(url)
    keep = [
        (k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True)
        if not any(k.startswith(pre) for pre in _TRACKING_PREFIXES)
        and k not in _TRACKING_EXACT
    ]
    new_q = urlencode(keep)
    return urlunparse(p._replace(query=new_q, fragment=""))
