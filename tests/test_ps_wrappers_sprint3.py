"""Parse-check the Sprint 3 PowerShell wrappers."""
import subprocess
from pathlib import Path

REPO = Path(__file__).parent.parent
WRAPPERS = [
    "scripts/run-build-topic-stats.ps1",
    "scripts/run-tos.ps1",
    "scripts/run-digest.ps1",
]


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


def test_all_sprint3_wrappers_exist_and_parse():
    for rel in WRAPPERS:
        p = REPO / rel
        assert p.exists(), f"missing: {rel}"
        err = _parse(p)
        assert not err, f"{rel} parse error:\n{err}"
