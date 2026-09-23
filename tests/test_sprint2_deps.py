"""Verify Sprint 2 runtime deps are importable after install."""

def test_spacy_importable():
    import spacy  # noqa: F401


def test_rapidfuzz_importable():
    from rapidfuzz import fuzz  # noqa: F401
    assert fuzz.token_set_ratio("a b c", "b c a") == 100


def test_google_analytics_data_importable():
    from google.analytics.data_v1beta import BetaAnalyticsDataClient  # noqa: F401
    assert BetaAnalyticsDataClient is not None
