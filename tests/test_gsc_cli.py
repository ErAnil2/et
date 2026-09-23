import subprocess
import sys

from googleapiclient.errors import HttpError

from discover_intel.ingest.gsc_discover import handle_http_error, main_from_env


class _FakeResp:
    def __init__(self, status: int) -> None:
        self.status = status
        self.reason = "reason"


def test_403_remediation_message(capsys):
    err = HttpError(_FakeResp(403), b"forbidden")
    rc = handle_http_error(err)
    out = capsys.readouterr().err
    assert rc == 2
    assert "403" in out and "Users and permissions" in out


def test_404_remediation_message(capsys):
    err = HttpError(_FakeResp(404), b"not found")
    rc = handle_http_error(err)
    out = capsys.readouterr().err
    assert rc == 2
    assert "404" in out and "GSC_PROPERTY" in out


def test_main_requires_env(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("GSC_SA_JSON", raising=False)
    monkeypatch.delenv("GSC_PROPERTY", raising=False)
    rc = main_from_env(argv=["--db", str(tmp_path / "wh.db"), "--dry-run"])
    out = capsys.readouterr().err
    assert rc == 2
    assert "GSC_SA_JSON" in out and "GSC_PROPERTY" in out


def test_dry_run_prints_planned_query(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("GSC_SA_JSON", str(tmp_path / "fake.json"))
    (tmp_path / "fake.json").write_text("{}")
    monkeypatch.setenv("GSC_PROPERTY", "sc-domain:example.com")
    subprocess.run([sys.executable, "-m", "discover_intel", "init-db",
                    "--db", str(tmp_path / "wh.db")], check=True)
    rc = main_from_env(argv=["--db", str(tmp_path / "wh.db"),
                             "--start", "2026-09-20", "--end", "2026-09-22",
                             "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "gsc dry-run" in out.lower()
    assert "sc-domain:example.com" in out
    assert "2026-09-20" in out and "2026-09-22" in out
