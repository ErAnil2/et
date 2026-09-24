from pathlib import Path

README = Path(__file__).parent.parent / "README.md"


def test_readme_mentions_sprint3_deps():
    text = README.read_text(encoding="utf-8")
    assert "streamlit" in text.lower()
    assert "plotly" in text.lower()


def test_readme_mentions_sprint3_commands():
    text = README.read_text(encoding="utf-8")
    for cmd in ("build-topic-stats", "tos", "drs", "digest", "dashboard"):
        assert cmd in text, f"missing command: {cmd}"


def test_readme_mentions_scoring_yaml():
    text = README.read_text(encoding="utf-8")
    assert "config/scoring.yaml" in text or "scoring.yaml" in text


def test_readme_mentions_digest_output_path():
    text = README.read_text(encoding="utf-8")
    assert "data/digests" in text or "data\\digests" in text
