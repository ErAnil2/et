import subprocess
import sys


def test_dashboard_module_imports():
    """Just importing must not raise (Streamlit imports must be lazy)."""
    from discover_intel.delivery import dashboard  # noqa: F401


def test_cli_dashboard_help_lists_subcommand():
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "--help"],
        capture_output=True, text=True, check=True,
    )
    assert "dashboard" in r.stdout


def test_streamlit_import_succeeds():
    import streamlit  # noqa: F401
