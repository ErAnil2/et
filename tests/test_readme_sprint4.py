from pathlib import Path

README = Path(__file__).parent.parent / "README.md"


def test_readme_mentions_sprint4_command():
    text = README.read_text(encoding="utf-8")
    assert "scorecard" in text


def test_readme_mentions_scorecards_output_path():
    text = README.read_text(encoding="utf-8")
    assert "data/scorecards" in text or "data\\scorecards" in text
