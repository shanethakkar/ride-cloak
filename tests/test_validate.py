"""Validation tests: Tier-1 contract, each Tier-2 rule, and the corruption gate.

All run on small hand-crafted frames (CI-safe). A dev-slice integration test at
the end confirms clean real data passes its own gate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pipeline.validate import checks, contract, health

GATE = 90


def clean_df(n: int = 500) -> pd.DataFrame:
    """A fully valid HVFHV frame: passes Tier-1 and scores 100 on every dimension."""
    rng = np.random.default_rng(11)
    base = pd.Timestamp("2026-04-01 00:00:00")
    pickup = base + pd.to_timedelta(np.arange(n), unit="s")
    trip_time = rng.integers(120, 3600, n)
    dropoff = pickup + pd.to_timedelta(trip_time, unit="s")
    yn = lambda: rng.choice(["Y", "N"], n)  # noqa: E731
    df = pd.DataFrame(
        {
            "hvfhs_license_num": "HV0003",
            "dispatching_base_num": "B03404",
            "originating_base_num": "B03404",
            "request_datetime": pickup - pd.Timedelta(seconds=60),
            "on_scene_datetime": pickup - pd.Timedelta(seconds=30),
            "pickup_datetime": pickup,
            "dropoff_datetime": dropoff,
            "PULocationID": rng.integers(1, 266, n),
            "DOLocationID": rng.integers(1, 266, n),
            "trip_miles": np.round(rng.uniform(0.2, 25.0, n), 3),
            "trip_time": trip_time,
            "base_passenger_fare": np.round(rng.uniform(5, 90, n), 2),
            "tolls": 0.0,
            "bcf": np.round(rng.uniform(0, 2, n), 2),
            "sales_tax": np.round(rng.uniform(0, 5, n), 2),
            "congestion_surcharge": 0.0,
            "airport_fee": 0.0,
            "tips": np.round(rng.uniform(0, 10, n), 2),
            "driver_pay": np.round(rng.uniform(4, 80, n), 2),
            "shared_request_flag": yn(),
            "shared_match_flag": yn(),
            "access_a_ride_flag": yn(),
            "wav_request_flag": yn(),
            "wav_match_flag": yn(),
            "cbd_congestion_fee": 0.0,
        }
    )
    return df


def corrupt_slice(df: pd.DataFrame, frac: float = 0.2, seed: int = 5) -> pd.DataFrame:
    """Inject Tier-2 quality damage across all four dimensions (Tier-1 stays valid).

    Negative fares (validity), dropoff<pickup (consistency), nulled optional cells
    (completeness), and duplicated rows (uniqueness). Zones, required columns,
    dtypes and license are left intact so the structural contract still passes and
    a numeric score is produced.
    """
    rng = np.random.default_rng(seed)
    out = df.reset_index(drop=True).copy()
    n = len(out)
    k = max(1, int(frac * n))
    idx = rng.choice(n, size=k, replace=False)

    out.loc[idx, "base_passenger_fare"] = -out.loc[idx, "base_passenger_fare"].abs() - 1
    out.loc[idx, "dropoff_datetime"] = out.loc[idx, "pickup_datetime"] - pd.Timedelta(minutes=1)
    out.loc[idx, "tips"] = np.nan  # tips is nullable -> completeness ding, not Tier-1

    dupes = out.iloc[idx].copy()
    return pd.concat([out, dupes], ignore_index=True)


# --- Tier-1 contract ---------------------------------------------------------


def test_contract_passes_on_clean():
    assert contract.validate_contract(clean_df())["passed"] is True


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.drop(columns=["tips"]),  # missing required-present column
        lambda d: d.assign(PULocationID=d["PULocationID"].mask(d.index < 5, 999)),  # zone domain
        lambda d: d.assign(hvfhs_license_num="HV0004"),  # wrong license
        lambda d: d.assign(
            pickup_datetime=d["pickup_datetime"].mask(d.index < 3, pd.NaT)
        ),  # null req
    ],
)
def test_contract_fails_on_structural_damage(mutate):
    bad = mutate(clean_df())
    assert contract.validate_contract(bad)["passed"] is False


# --- Tier-2 rules: each fires on a crafted bad row ---------------------------


def test_negative_money_fires_validity():
    df = clean_df(10)
    df.loc[0, "driver_pay"] = -1.0
    counts = checks.quality_counts(df)
    assert counts["validity"]["rules"]["driver_pay_negative"] == 1
    assert counts["validity"]["fail_rows"] == 1


def test_bad_flag_fires_validity():
    df = clean_df(10)
    df.loc[0, "wav_match_flag"] = "X"
    counts = checks.quality_counts(df)
    assert counts["validity"]["rules"]["wav_match_flag_not_YN"] == 1


def test_dropoff_before_pickup_fires_consistency():
    df = clean_df(10)
    df.loc[0, "dropoff_datetime"] = df.loc[0, "pickup_datetime"] - pd.Timedelta(minutes=2)
    counts = checks.quality_counts(df)
    assert counts["consistency"]["rules"]["dropoff_before_pickup"] == 1


def test_trip_time_mismatch_fires_consistency():
    df = clean_df(10)
    df.loc[0, "trip_time"] = int(df.loc[0, "trip_time"]) + 600  # 10 min off
    counts = checks.quality_counts(df)
    assert counts["consistency"]["rules"]["trip_time_mismatch"] == 1


def test_duplicate_rows_fire_uniqueness():
    df = clean_df(10)
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    counts = checks.quality_counts(df)
    assert counts["uniqueness"]["duplicate_rows"] == 1


def test_null_cell_fires_completeness():
    df = clean_df(10)
    df.loc[0, "tips"] = np.nan
    counts = checks.quality_counts(df)
    assert counts["completeness"]["null_cells"] == 1


# --- Health score + gate -----------------------------------------------------


def test_clean_scores_100_and_passes():
    report = health.build_report(clean_df(), GATE, source="fixture")
    assert report["tier1_passed"] is True
    assert report["health_score"] == 100.0
    assert report["refused"] is False


def test_corrupted_slice_scores_lower_and_is_refused():
    clean = health.build_report(clean_df(), GATE, source="clean")
    corrupt = health.build_report(corrupt_slice(clean_df()), GATE, source="corrupt")
    assert corrupt["tier1_passed"] is True  # damage is Tier-2, not structural
    assert corrupt["health_score"] < clean["health_score"]
    assert corrupt["health_score"] < GATE
    assert corrupt["refused"] is True
    for dim in ("completeness", "validity", "consistency", "uniqueness"):
        assert corrupt["dimensions"][dim] < 100.0


def test_structural_failure_short_circuits_to_refused():
    bad = clean_df().assign(hvfhs_license_num="HV0004")
    report = health.build_report(bad, GATE, source="bad")
    assert report["tier1_passed"] is False
    assert report["refused"] is True
    assert report["health_score"] is None


# --- Month/scale path parsing ------------------------------------------------


def test_parse_month_aggregate_shapes_tier1_and_counts():
    row = {
        "n": 1000,
        "null_cells": 0,
        "required_nulls": 0,
        "zone_out_of_range": 0,
        "trip_time_negative": 0,
        "license_bad": 0,
        "validity_fail_rows": 4,
        "consistency_fail_rows": 1,
        "duplicate_rows": 0,
    }
    tier1, counts = checks.parse_month_aggregate(row)
    assert tier1["passed"] is True
    assert counts["validity"]["fail_rows"] == 4
    report = health.build_report_from_counts(counts, GATE, tier1, "month:test")
    assert report["refused"] is False
    assert report["health_score"] > 99


def test_parse_month_aggregate_flags_structural():
    row = {
        "n": 1000,
        "null_cells": 0,
        "required_nulls": 0,
        "zone_out_of_range": 7,
        "trip_time_negative": 0,
        "license_bad": 0,
        "validity_fail_rows": 0,
        "consistency_fail_rows": 0,
        "duplicate_rows": 0,
    }
    tier1, _ = checks.parse_month_aggregate(row)
    assert tier1["passed"] is False
    assert tier1["failures"][0]["count"] == 7


# --- Dev-slice integration (skipped if the slice is absent) ------------------


def test_validate_dev_slice_passes_gate():
    from config.settings import get_settings
    from pipeline.io import readers

    settings = get_settings()
    if not settings.dev_slice_path.exists():
        pytest.skip("dev slice not built; run `ridecloak synth --input dev`")
    df = readers.read_parquet(settings.dev_slice_path)
    report = health.build_report(df, settings.gate_threshold, source="dev")
    assert report["tier1_passed"] is True
    assert report["refused"] is False
    assert report["health_score"] >= settings.gate_threshold
