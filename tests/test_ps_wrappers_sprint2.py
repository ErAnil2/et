"""Parse-check the four Sprint 2 PowerShell wrappers via the language parser."""
import subprocess
from pathlib import Path

REPO = Path(__file__).parent.parent
WRAPPERS = [
    "scripts/run-resolve-urls.ps1",
    "scripts/run-match-outcomes.ps1",
    "scripts/run-tag-entities.ps1",
    "scripts/run-toi-ga.ps1",
]


def _parse(path: Path) -> str:
    """Return empty string on success, or the error text on failure."""
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
    if out == "OK":
        return ""
    return out or result.stderr


def test_all_sprint2_wrappers_exist_and_parse():
    for rel in WRAPPERS:
        p = REPO / rel
        assert p.exists(), f"missing: {rel}"
        err = _parse(p)
        assert not err, f"{rel} parse error:\n{err}"
