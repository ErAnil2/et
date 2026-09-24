"""Pure functions for the 5 TOS components. Each returns a raw value.

Rank-percentile normalisation happens in tos.py at the batch level so
components can be tested independently here without a full warehouse.
"""
from __future__ import annotations

import math


def momentum(new_items_6h: int, prior_48h_mean_per_6h: float) -> float:
    """Ratio: new_items in last 6h vs mean per 6h over prior 48h.

    Returns raw ratio (non-normalised). The caller batches ratios across
    all entities in the same run and rank-percentiles them.
    """
    denom = max(1.0, prior_48h_mean_per_6h)
    return float(new_items_6h) / denom


def headroom(competitor_hosts_24h: int, curve: dict) -> float:
    """Bell-curve lookup on competitor_hosts_24h."""
    key = str(int(competitor_hosts_24h))
    if key in curve:
        return float(curve[key])
    return float(curve.get("default", 0.2))


def timing(avg_time_on_feed_min: float | None, hours_since_first_seen: float,
           decay_hours: float) -> float:
    """avg_time_on_feed_min * exp(-hours_since_first_seen / decay_hours).

    Returns raw value; caller percentile-normalises across entities.
    NULL time-on-feed -> 0.0 (no signal).
    """
    if avg_time_on_feed_min is None or avg_time_on_feed_min <= 0:
        return 0.0
    return float(avg_time_on_feed_min) * math.exp(-hours_since_first_seen / decay_hours)


def format_match(winning_format: str | None, config: dict) -> float:
    """1.0 if in producible list; 0.0 for penalty formats; unknown_value else."""
    if winning_format is None or winning_format == "":
        return float(config.get("unknown_value", 0.5))
    if winning_format in config.get("penalty_formats", []):
        return float(config.get("penalty_value", 0.0))
    if winning_format in config.get("producible", []):
        return 1.0
    return float(config.get("unknown_value", 0.5))


def lane_fit(entity_lane_flags: list[int], config: dict) -> float:
    """1.0 if any lane flag is 1 (in_et_lane); else out_of_lane_value."""
    if entity_lane_flags and any(flag == 1 for flag in entity_lane_flags):
        return float(config.get("in_lane_value", 1.0))
    return float(config.get("out_of_lane_value", 0.3))
