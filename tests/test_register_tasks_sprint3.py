import subprocess
from pathlib import Path

REPO = Path(__file__).parent.parent

EXPECTED_NEW = [
    "DiscoverIntel_BuildTopicStats",
    "DiscoverIntel_TOS",
    "DiscoverIntel_Digest",
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


def test_register_and_unregister_mention_new_tasks():
    reg = (REPO / "scripts/register-tasks.ps1").read_text(encoding="utf-8")
    unreg = (REPO / "scripts/unregister-tasks.ps1").read_text(encoding="utf-8")
    for name in EXPECTED_NEW:
        assert name in reg, f"register-tasks missing: {name}"
        assert name in unreg, f"unregister-tasks missing: {name}"


def test_register_still_parses():
    for rel in ("scripts/register-tasks.ps1", "scripts/unregister-tasks.ps1"):
        err = _parse(REPO / rel)
        assert not err, f"{rel} parse error:\n{err}"
