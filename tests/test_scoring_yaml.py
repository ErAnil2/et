from pathlib import Path

import yaml

CFG = Path(__file__).parent.parent / "config" / "scoring.yaml"


def _load() -> dict:
    return yaml.safe_load(CFG.read_text(encoding="utf-8"))


def test_top_level_sections():
    d = _load()
    assert "tos" in d and "drs" in d


def test_tos_weights_sum_to_one():
    w = _load()["tos"]["weights"]
    total = w["momentum"] + w["headroom"] + w["timing"] + w["format_match"] + w["lane_fit"]
    assert abs(total - 1.0) < 1e-9


def test_drs_weights_sum_to_one():
    w = _load()["drs"]["weights"]
    total = (w["headline"] + w["image"] + w["eeat"] + w["originality"]
             + w["timeliness"] + w["technical"])
    assert abs(total - 1.0) < 1e-9


def test_headroom_curve_values_in_range():
    curve = _load()["tos"]["headroom_curve"]
    for k, v in curve.items():
        assert 0.0 <= float(v) <= 1.0, f"headroom_curve[{k}]={v} out of [0,1]"


def test_tos_thresholds():
    t = _load()["tos"]["thresholds"]
    assert 0 < t["watchlist"] < t["publish"] <= 100


def test_drs_gate():
    assert 0 < _load()["drs"]["gate"] <= 100


def test_producible_formats_and_penalty_formats():
    fm = _load()["tos"]["format_match"]
    assert "news" in fm["producible"]
    assert "trivia" in fm["penalty_formats"]


def test_ymyl_lanes_defined():
    lanes = _load()["drs"]["eeat"]["ymyl_lanes"]
    assert isinstance(lanes, list) and len(lanes) >= 1
