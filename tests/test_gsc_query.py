from unittest.mock import MagicMock

from discover_intel.ingest.gsc_discover import query_and_upsert


def _canned_response():
    return {
        "rows": [
            {"keys": ["2026-09-20", "usa", "MOBILE",
                      "https://economictimes.indiatimes.com/x"],
             "clicks": 12, "impressions": 300, "ctr": 0.04, "position": 3.2},
            {"keys": ["2026-09-20", "usa", "DESKTOP",
                      "https://economictimes.indiatimes.com/y"],
             "clicks": 3, "impressions": 100, "ctr": 0.03, "position": 5.0},
        ],
        "responseAggregationType": "byPage",
    }


def test_query_and_upsert_writes_rows(conn):
    fake_execute = MagicMock(return_value=_canned_response())
    fake_query = MagicMock(execute=fake_execute)
    fake_service = MagicMock()
    fake_service.searchanalytics.return_value.query.return_value = fake_query

    n = query_and_upsert(
        conn, service=fake_service,
        property_url="sc-domain:economictimes.indiatimes.com",
        start="2026-09-20", end="2026-09-20",
    )
    assert n == 2

    # verify body params
    kwargs = fake_service.searchanalytics.return_value.query.call_args.kwargs
    body = kwargs["body"]
    assert body["type"] == "discover"
    assert body["dimensions"] == ["date", "country", "device", "page"]
    filters = body["dimensionFilterGroups"][0]["filters"]
    assert any(f["dimension"] == "country" and f["expression"] == "usa"
               for f in filters)

    (imp, clk) = conn.execute(
        "SELECT impressions, clicks FROM gsc_discover WHERE device='MOBILE'"
    ).fetchone()
    assert imp == 300 and clk == 12


def test_query_and_upsert_upserts_on_second_run(conn):
    def resp(clicks_bump=0):
        return {"rows": [
            {"keys": ["2026-09-20", "usa", "MOBILE",
                      "https://economictimes.indiatimes.com/x"],
             "clicks": 12 + clicks_bump, "impressions": 300,
             "ctr": 0.04, "position": 3.2},
        ]}

    fake_service = MagicMock()
    fake_service.searchanalytics.return_value.query.return_value.execute.side_effect = [
        resp(), resp(clicks_bump=5),
    ]
    query_and_upsert(conn, service=fake_service,
                     property_url="sc-domain:x", start="2026-09-20", end="2026-09-20")
    query_and_upsert(conn, service=fake_service,
                     property_url="sc-domain:x", start="2026-09-20", end="2026-09-20")
    (n, clk) = conn.execute(
        "SELECT count(*), max(clicks) FROM gsc_discover"
    ).fetchone()
    assert n == 1
    assert clk == 17  # restatement overwrote the row
