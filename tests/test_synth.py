"""Synthetic generator tests: determinism, span alignment, decoy purity.

These run on a small in-memory fixture (no external data file) so they are fast
and CI-safe. The full-slice reproducibility check lives in test_devslice.py.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest

from pipeline.synth import generator


def _fixture_rows(n: int = 4000) -> pd.DataFrame:
    """Build distinct real-shaped trip rows (only the columns the generator reads)."""
    rng = np.random.default_rng(7)
    base = pd.Timestamp("2026-04-01 00:00:00")
    pickup = base + pd.to_timedelta(np.arange(n), unit="s")
    return pd.DataFrame(
        {
            "request_datetime": pickup - pd.Timedelta(seconds=60),
            "pickup_datetime": pickup,
            "dropoff_datetime": pickup + pd.to_timedelta(rng.integers(120, 3600, n), unit="s"),
            "PULocationID": rng.integers(1, 263, n),
            "DOLocationID": rng.integers(1, 263, n),
            "trip_miles": np.round(rng.uniform(0.2, 25.0, n), 3),
            "base_passenger_fare": np.round(rng.uniform(5.0, 90.0, n), 2),
            "driver_pay": np.round(rng.uniform(4.0, 80.0, n), 2),
            "tips": np.round(rng.uniform(0.0, 20.0, n), 2),
            "trip_time": rng.integers(120, 3600, n),
        }
    )


def test_generate_is_deterministic():
    df = _fixture_rows()
    a_df, a_labels, a_stats = generator.generate(df, seed=4242)
    b_df, b_labels, b_stats = generator.generate(df, seed=4242)

    pd.testing.assert_frame_equal(a_df, b_df)
    pd.testing.assert_frame_equal(a_labels, b_labels)
    assert a_stats == b_stats


def test_different_seed_changes_identities():
    df = _fixture_rows()
    a_df, _, _ = generator.generate(df, seed=4242)
    b_df, _, _ = generator.generate(df, seed=99)
    # trip_id is attribute-derived, so it is stable; identities must differ.
    assert (a_df["trip_id"] == b_df["trip_id"]).all()
    assert (a_df["rider_id"] != b_df["rider_id"]).any()


def test_trip_id_unique_and_synth_columns_present():
    df = _fixture_rows()
    out, _, _ = generator.generate(df, seed=4242)
    assert out["trip_id"].is_unique
    for col in generator.SYNTH_COLUMNS:
        assert col in out.columns


def test_label_spans_realign_to_injected_values():
    """Every label must re-extract byte-for-byte from its note (hash match)."""
    df = _fixture_rows()
    out, labels, _ = generator.generate(df, seed=4242)
    notes = out.set_index("trip_id")["support_note"]

    assert len(labels) > 0
    for row in labels.itertuples(index=False):
        note = notes.loc[row.trip_id]
        extracted = note[row.start : row.end]
        assert hashlib.sha256(extracted.encode("utf-8")).hexdigest() == row.value_hash


def test_decoy_notes_have_zero_labeled_spans():
    """Noted trips partition cleanly into PII notes (>=1 span) and decoys (0 spans)."""
    df = _fixture_rows()
    out, labels, stats = generator.generate(df, seed=4242)

    noted = out[out["support_note"].notna()]
    pii_trips = set(labels["trip_id"])
    decoy_trips = set(noted["trip_id"]) - pii_trips

    # Decoys never contribute a label.
    assert pii_trips.isdisjoint(decoy_trips)
    # Accounting closes: notes == PII-note trips + decoy notes.
    assert stats["notes"] == labels["trip_id"].nunique() + stats["decoy_notes"]
    assert len(decoy_trips) == stats["decoy_notes"]


def test_note_rate_in_expected_band():
    df = _fixture_rows(20000)
    _, _, stats = generator.generate(df, seed=4242)
    rate = stats["notes"] / stats["rows"]
    assert 0.015 <= rate <= 0.025  # ~2% target


@pytest.mark.parametrize("seed", [1, 4242, 100000])
def test_spans_within_note_bounds(seed):
    df = _fixture_rows()
    out, labels, _ = generator.generate(df, seed=seed)
    notes = out.set_index("trip_id")["support_note"]
    for row in labels.itertuples(index=False):
        note = notes.loc[row.trip_id]
        assert 0 <= row.start < row.end <= len(note)
