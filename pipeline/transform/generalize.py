"""Generalization transforms: temporal rounding and spatial rollup.

Generalization is the primary re-identification lever (decisions.md D-0008): raw
zone-level trip data is ~97% unique, but rolling zones up to borough collapses
uniqueness to ~5%, which is what makes k-anonymity viable.
"""

from __future__ import annotations

import pandas as pd


def round_time(series: pd.Series, minutes: int) -> pd.Series:
    """Floor each timestamp down to an N-minute bucket (consistent, non-overlapping)."""
    return series.dt.floor(f"{minutes}min")


def rollup_zone(series: pd.Series, lookup: dict[int, str]) -> pd.Series:
    """Map a LocationID series to its borough via the taxi-zone lookup mapping."""
    return series.map(lookup)
