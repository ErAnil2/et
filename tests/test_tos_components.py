import math

from discover_intel.scoring.tos_components import (
    format_match, headroom, lane_fit, momentum, timing,
)


def test_momentum_zero_when_no_prior_and_zero_new():
    assert momentum(new_items_6h=0, prior_48h_mean_per_6h=0.0) == 0.0


def test_momentum_positive_when_new_items_present():
    val = momentum(new_items_6h=8, prior_48h_mean_per_6h=1.0)
    assert val > 0.0


def test_headroom_lookup_uses_curve():
    curve = {"0": 0.4, "1": 0.4, "2": 0.8, "3": 1.0, "4": 1.0, "5": 1.0,
             "6": 1.0, "7": 0.6, "8": 0.6, "9": 0.6, "10": 0.6, "default": 0.2}
    assert headroom(0, curve) == 0.4
    assert headroom(3, curve) == 1.0
    assert headroom(4, curve) == 1.0
    assert headroom(9, curve) == 0.6
    assert headroom(50, curve) == 0.2


def test_timing_zero_when_avg_time_none():
    assert timing(avg_time_on_feed_min=None, hours_since_first_seen=0.0,
                  decay_hours=18.0) == 0.0


def test_timing_applies_decay():
    fresh = timing(avg_time_on_feed_min=60.0, hours_since_first_seen=0.0,
                   decay_hours=18.0)
    old = timing(avg_time_on_feed_min=60.0, hours_since_first_seen=36.0,
                 decay_hours=18.0)
    assert fresh > old
    mid = timing(avg_time_on_feed_min=60.0, hours_since_first_seen=18.0,
                 decay_hours=18.0)
    assert math.isclose(mid, 60.0 * math.exp(-1), rel_tol=1e-6)


def test_format_match_producible_returns_one():
    config = {
        "producible": ["news", "analysis", "atmosphere", "service"],
        "unknown_value": 0.5,
        "penalty_formats": ["trivia", "quote"],
        "penalty_value": 0.0,
    }
    assert format_match(winning_format="news", config=config) == 1.0
    assert format_match(winning_format="analysis", config=config) == 1.0


def test_format_match_unknown_returns_default():
    config = {
        "producible": ["news"], "unknown_value": 0.5,
        "penalty_formats": ["trivia"], "penalty_value": 0.0,
    }
    assert format_match(winning_format=None, config=config) == 0.5


def test_format_match_penalty_returns_zero():
    config = {
        "producible": ["news"], "unknown_value": 0.5,
        "penalty_formats": ["trivia", "quote"], "penalty_value": 0.0,
    }
    assert format_match(winning_format="trivia", config=config) == 0.0


def test_lane_fit_in_lane():
    config = {"in_lane_value": 1.0, "out_of_lane_value": 0.3}
    assert lane_fit(entity_lane_flags=[1, 0], config=config) == 1.0


def test_lane_fit_out_of_lane():
    config = {"in_lane_value": 1.0, "out_of_lane_value": 0.3}
    assert lane_fit(entity_lane_flags=[0, 0], config=config) == 0.3


def test_lane_fit_empty_lanes_out_of_lane():
    config = {"in_lane_value": 1.0, "out_of_lane_value": 0.3}
    assert lane_fit(entity_lane_flags=[], config=config) == 0.3
