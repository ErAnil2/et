from pathlib import Path

from discover_intel.analysis.gnews_decoder import decode_gnews_url

FIXTURES = Path(__file__).parent / "fixtures"


def _load_urls() -> list[str]:
    return [
        line.strip()
        for line in (FIXTURES / "gnews_encoded_urls.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def test_decoder_extracts_https_from_base64():
    urls = _load_urls()
    result = decode_gnews_url(urls[0])
    assert result is not None
    assert result.startswith("https://")
    assert "example.com" in result


def test_decoder_handles_second_shape():
    urls = _load_urls()
    result = decode_gnews_url(urls[1])
    assert result is not None
    assert "nj.com" in result


def test_decoder_returns_none_on_garbage():
    urls = _load_urls()
    result = decode_gnews_url(urls[2])
    assert result is None


def test_decoder_returns_none_on_non_gnews_url():
    result = decode_gnews_url("https://example.com/regular/url")
    assert result is None
