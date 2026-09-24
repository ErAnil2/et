"""Parse-check the Sprint 4 scorecard wrapper + Task Scheduler entry."""
import subprocess
from pathlib import Path

REPO = Path(__file__).parent.parent


def _parse(path: Path) -> str:
    ps_cmd = (
        f"$errs = $null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile("
        f"'{path.as_posix()}', [ref]$null, [ref]$errs) | Out-Null; "
        f"if ($errs.Count -gt 0) {{ $errs | Out-String }} else {{ 'OK' }}"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
        capture_output=True, text=True, timeout=30,
    )
    out = result.stdout.strip()
    return "" if out == "OK" else (out or result.stderr)


def test_run_scorecard_ps1_parses():
    err = _parse(REPO / "scripts/run-scorecard.ps1")
    assert not err, f"parse error:\n{err}"


def test_register_unregister_mention_scorecard():
    reg = (REPO / "scripts/register-tasks.ps1").read_text(encoding="utf-8")
    unreg = (REPO / "scripts/unregister-tasks.ps1").read_text(encoding="utf-8")
    assert "DiscoverIntel_Scorecard" in reg
    assert "DiscoverIntel_Scorecard" in unreg


def test_register_and_unregister_still_parse():
    for rel in ("scripts/register-tasks.ps1", "scripts/unregister-tasks.ps1"):
        err = _parse(REPO / rel)
        assert not err, f"{rel} parse error:\n{err}"
