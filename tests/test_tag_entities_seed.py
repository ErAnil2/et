from pathlib import Path

from discover_intel.analysis.tag_entities import (
    load_format_rules, load_lane_patterns, seed_taxonomy,
)

CONFIG_DIR = Path(__file__).parent.parent / "config"


def _load_labels(path: Path) -> dict[str, str]:
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {slug: entry["label"] for slug, entry in data.items()}


def test_seed_taxonomy_inserts_23_lanes_plus_6_formats(conn):
    lanes = load_lane_patterns(CONFIG_DIR / "lane_keywords.yaml")
    formats = load_format_rules(CONFIG_DIR / "format_rules.yaml")

    seed_taxonomy(conn, lanes, formats,
                  lane_labels=_load_labels(CONFIG_DIR / "lane_keywords.yaml"))

    (n_lanes,) = conn.execute(
        "SELECT count(*) FROM taxonomy WHERE kind='lane'"
    ).fetchone()
    (n_formats,) = conn.execute(
        "SELECT count(*) FROM taxonomy WHERE kind='format'"
    ).fetchone()
    assert n_lanes == 23
    assert n_formats == 6


def test_seed_taxonomy_is_idempotent(conn):
    lanes = load_lane_patterns(CONFIG_DIR / "lane_keywords.yaml")
    formats = load_format_rules(CONFIG_DIR / "format_rules.yaml")
    labels = _load_labels(CONFIG_DIR / "lane_keywords.yaml")

    seed_taxonomy(conn, lanes, formats, lane_labels=labels)
    seed_taxonomy(conn, lanes, formats, lane_labels=labels)
    (n,) = conn.execute("SELECT count(*) FROM taxonomy").fetchone()
    assert n == 23 + 6


def test_seed_all_lanes_have_in_et_lane_1(conn):
    lanes = load_lane_patterns(CONFIG_DIR / "lane_keywords.yaml")
    formats = load_format_rules(CONFIG_DIR / "format_rules.yaml")
    labels = _load_labels(CONFIG_DIR / "lane_keywords.yaml")
    seed_taxonomy(conn, lanes, formats, lane_labels=labels)
    all_flagged = conn.execute(
        "SELECT in_et_lane FROM taxonomy WHERE kind='lane'"
    ).fetchall()
    assert all(row[0] == 1 for row in all_flagged)
