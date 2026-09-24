import subprocess
import sys
from pathlib import Path

from discover_intel.scoring.drs import load_drs_config, score_draft

CFG_PATH = Path(__file__).parent.parent / "config" / "scoring.yaml"


def test_score_draft_clean_headline(spacy_nlp):
    cfg = load_drs_config(CFG_PATH,
                          clickbait_path=Path("config/clickbait_patterns.txt"))
    draft = {
        "title": "Fed cuts rates by 25 bps as Powell signals slower path",
        "image_width": 1600,
        "author": "Jane Doe",
        "published_at": "2026-09-24T15:00:00Z",
    }
    result = score_draft(draft, config=cfg, conn=None, nlp=spacy_nlp)
    assert result["drs"] >= 60.0
    assert "findings_json" in result


def test_score_draft_clickbait_headline(spacy_nlp):
    cfg = load_drs_config(CFG_PATH,
                          clickbait_path=Path("config/clickbait_patterns.txt"))
    draft = {
        "title": "You won't believe what happened next at the Fed today wow",
        "image_width": 1600,
        "author": "Jane Doe",
        "published_at": "2026-09-24T15:00:00Z",
    }
    result = score_draft(draft, config=cfg, conn=None, nlp=spacy_nlp)
    assert result["headline"] == 0.0
    assert result["drs"] < 70.0


def test_score_draft_short_headline_fails(spacy_nlp):
    cfg = load_drs_config(CFG_PATH,
                          clickbait_path=Path("config/clickbait_patterns.txt"))
    draft = {
        "title": "Fed cut", "image_width": 1600, "author": "Jane Doe",
        "published_at": "2026-09-24T15:00:00Z",
    }
    result = score_draft(draft, config=cfg, conn=None, nlp=spacy_nlp)
    assert result["headline"] == 0.0


def test_cli_drs_clean(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "drs",
         "--title", "Fed cuts rates by 25 bps as Powell signals slower path",
         "--image-width", "1600",
         "--author", "Jane Doe",
         "--published-at", "2026-09-24T15:00:00Z",
         "--db", str(db_path)],
        capture_output=True, text=True, check=True,
    )
    assert "DRS:" in r.stdout


def test_cli_drs_clickbait_below_gate(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "drs",
         "--title", "You won't believe what happened next at Fed meet today wow",
         "--image-width", "1600",
         "--author", "Jane Doe",
         "--published-at", "2026-09-24T15:00:00Z",
         "--db", str(db_path)],
        capture_output=True, text=True, check=True,
    )
    line = next(ln for ln in r.stdout.splitlines() if ln.startswith("DRS:"))
    val = float(line.split()[1])
    assert val < 70.0
