from unittest.mock import MagicMock

from discover_intel.ingest.toi_ga import run_report


def _canned_response():
    """Simulate BetaAnalyticsDataClient.run_report()'s return object."""
    r = MagicMock()

    row1 = MagicMock()
    row1.dimension_values = [
        MagicMock(value=v) for v in
        ["20260920", "/news/story-a", "Story A Title", "google", "discover", "MOBILE"]
    ]
    row1.metric_values = [MagicMock(value=v) for v in ["1250", "980", "0.784", "1400"]]

    row2 = MagicMock()
    row2.dimension_values = [
        MagicMock(value=v) for v in
        ["20260920", "/news/story-b", "Story B Title", "google", "discover", "DESKTOP"]
    ]
    row2.metric_values = [MagicMock(value=v) for v in ["300", "240", "0.8", "310"]]

    r.rows = [row1, row2]
    return r


def test_run_report_calls_client_with_correct_params():
    client = MagicMock()
    client.run_report.return_value = _canned_response()

    rows = run_report(client, property_id="230487101",
                      start="2026-09-20", end="2026-09-22")

    assert len(rows) == 2
    assert rows[0]["pagePath"] == "/news/story-a"
    assert rows[0]["sessions"] == 1250
    assert rows[0]["deviceCategory"] == "MOBILE"

    call = client.run_report.call_args
    request = call.kwargs.get("request") or call.args[0]
    assert request.property == "properties/230487101"
    dim_names = [d.name for d in request.dimensions]
    assert "date" in dim_names
    assert "pagePath" in dim_names
    assert "sessionSource" in dim_names
    metric_names = [m.name for m in request.metrics]
    assert "sessions" in metric_names
