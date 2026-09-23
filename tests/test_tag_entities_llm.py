from pathlib import Path
from unittest.mock import patch

from discover_intel.analysis.tag_entities import llm_classify, orchestrate

CONFIG_DIR = Path(__file__).parent.parent / "config"


def hash_of(s: str) -> str:
    import hashlib
    return hashlib.sha1(s.encode()).hexdigest()


def test_llm_classify_uses_cache(tmp_path, monkeypatch):
    """A cached title bypasses the SDK call entirely."""
    cache_dir = tmp_path / "llm_cache"
    cache_dir.mkdir()
    monkeypatch.setattr(
        "discover_intel.analysis.tag_entities._LLM_CACHE_DIR",
        cache_dir,
    )
    title = "some obscure title"
    (cache_dir / f"{hash_of(title)}.json").write_text(
        '{"lanes": ["tech_ai"], "format": "news", "entities": [], "confidence": 0.9}'
    )

    result = llm_classify(title, lane_slugs=["tech_ai"], format_slugs=["news"])
    assert result["lanes"] == ["tech_ai"]


def test_llm_classify_calls_sdk_when_uncached(tmp_path, monkeypatch):
    cache_dir = tmp_path / "llm_cache"
    cache_dir.mkdir()
    monkeypatch.setattr(
        "discover_intel.analysis.tag_entities._LLM_CACHE_DIR",
        cache_dir,
    )
    with patch("discover_intel.analysis.tag_entities._call_claude_sdk") as fake:
        fake.return_value = {"lanes": ["finance_markets"], "format": "news",
                             "entities": [{"text": "Fed", "type": "ORG"}],
                             "confidence": 0.85}
        result = llm_classify("Fed hints at cut", lane_slugs=["finance_markets"],
                              format_slugs=["news"])
    assert result["lanes"] == ["finance_markets"]
    assert (cache_dir / f"{hash_of('Fed hints at cut')}.json").exists()


def test_orchestrate_with_llm_missing_sdk_returns_zero_llm_calls(spacy_nlp, conn,
                                                                  monkeypatch):
    """If claude-code-sdk is unavailable, use_llm=True still runs the rule pass
    but skips LLM."""
    from discover_intel.db import upsert
    upsert(conn, "sources", {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example", "url": "https://example.com/feed",
        "host": "example.com", "tier": None, "category": None,
        "enabled": 1, "notes": None,
    }, key="source_id")
    conn.execute(
        "INSERT INTO items (item_id, source_id, url, host, title, "
        "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
        "('itm-x', 'web:example.com', 'https://a', 'example.com', "
        "'obscure story that hits no lane pattern zqxjw', "
        "'2026-09-23T12:00:00Z', '2026-09-23T12:00:00Z', 1, 'hx')"
    )
    conn.commit()

    monkeypatch.setattr(
        "discover_intel.analysis.tag_entities._SDK_AVAILABLE", False,
    )
    stats = orchestrate(conn, source="items", limit=10, config_dir=CONFIG_DIR,
                        nlp=spacy_nlp, use_llm=True)
    assert stats["llm_calls"] == 0
