from pathlib import Path

from discover_intel.ingest.toi_ga import (
    handle_ga_error, main_from_env, persist_rows,
)


def test_persist_rows_writes_discover_articles(conn):
    rows = [
        {"date": "20260920", "pagePath": "/news/a", "pageTitle": "Story A",
         "sessionSource": "google", "sessionMedium": "discover",
         "deviceCategory": "MOBILE", "sessions": 1250, "engagedSessions": 980,
         "engagementRate": 0.784, "screenPageViews": 1400},
        {"date": "20260920", "pagePath": "/news/b", "pageTitle": "Story B",
         "sessionSource": "google", "sessionMedium": "discover",
         "deviceCategory": "DESKTOP", "sessions": 300, "engagedSessions": 240,
         "engagementRate": 0.8, "screenPageViews": 310},
    ]
    stats = persist_rows(conn, rows, market="US")
    assert stats["new"] == 2

    (n,) = conn.execute(
        "SELECT count(*) FROM discover_articles WHERE tool='toi_ga'"
    ).fetchone()
    assert n == 2

    (host, url, vis) = conn.execute(
        "SELECT host, url, visibility FROM discover_articles "
        "WHERE tool='toi_ga' ORDER BY visibility DESC LIMIT 1"
    ).fetchone()
    assert host == "timesofindia.indiatimes.com"
    assert url.startswith("https://timesofindia.indiatimes.com/news/")
    assert vis == 1250


def test_persist_rows_upserts_on_restatement(conn):
    row = {"date": "20260920", "pagePath": "/news/a", "pageTitle": "Story A",
           "sessionSource": "google", "sessionMedium": "discover",
           "deviceCategory": "MOBILE", "sessions": 100, "engagedSessions": 80,
           "engagementRate": 0.8, "screenPageViews": 120}
    persist_rows(conn, [row], market="US")

    row["sessions"] = 175
    persist_rows(conn, [row], market="US")
    (n,) = conn.execute(
        "SELECT count(*) FROM discover_articles WHERE tool='toi_ga'"
    ).fetchone()
    assert n == 1
    (vis,) = conn.execute(
        "SELECT visibility FROM discover_articles WHERE tool='toi_ga'"
    ).fetchone()
    assert vis == 175


def test_handle_ga_error_403_message():
    from google.api_core import exceptions as gexc
    err = gexc.PermissionDenied("permission denied")
    exit_code = handle_ga_error(err)
    assert exit_code == 2


def test_main_from_env_missing_vars(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("TOI_GA_SA_JSON", raising=False)
    monkeypatch.delenv("TOI_GA_PROPERTY_ID", raising=False)
    db_path = tmp_path / "wh.db"
    db_path.touch()
    exit_code = main_from_env(db_path=str(db_path), start=None, end=None,
                              dry_run=False)
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "TOI_GA_SA_JSON" in captured.err or "TOI_GA_SA_JSON" in captured.out


def test_dry_run_prints_planned_request(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("TOI_GA_SA_JSON", str(tmp_path / "sa.json"))
    monkeypatch.setenv("TOI_GA_PROPERTY_ID", "230487101")
    db_path = tmp_path / "wh.db"
    db_path.touch()
    exit_code = main_from_env(db_path=str(db_path),
                              start="2026-09-20", end="2026-09-22",
                              dry_run=True)
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "toi-ga dry-run:" in out
    assert "230487101" in out
    assert "2026-09-20" in out
