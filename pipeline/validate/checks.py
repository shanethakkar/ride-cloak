"""Tier-2 quality checks: completeness, validity, consistency, uniqueness.

Pure functions over a DataFrame. ``quality_counts`` returns the per-rule counts
and dimension fail-row totals that ``health`` turns into a 0-100 score. Rule
names are shared with the month-scale SQL path (see ``quality_counts_sql``) so a
dev run and a full-month run report the same rules.
"""

from __future__ import annotations

import pandas as pd

from pipeline.validate.contract import (
    FLAG_COLUMNS,
    MONEY_COLUMNS,
    NON_NULL_COLUMNS,
    REAL_COLUMNS,
    ZONE_MAX,
    ZONE_MIN,
)

TRIP_TIME_TOLERANCE_S = 60  # |trip_time - wall-clock duration| allowed before it counts


def _validity_rules(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Per-rule boolean masks for the validity dimension (True = row fails rule)."""
    rules: dict[str, pd.Series] = {}
    for col in MONEY_COLUMNS:
        rules[f"{col}_negative"] = df[col] < 0
    rules["trip_miles_negative"] = df["trip_miles"] < 0
    for flag in FLAG_COLUMNS:
        rules[f"{flag}_not_YN"] = ~df[flag].isin(["Y", "N"])
    return rules


def _consistency_rules(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Per-rule boolean masks for the consistency dimension."""
    duration_s = (df["dropoff_datetime"] - df["pickup_datetime"]).dt.total_seconds()
    return {
        "dropoff_before_pickup": df["dropoff_datetime"] < df["pickup_datetime"],
        "trip_time_mismatch": (df["trip_time"] - duration_s).abs() > TRIP_TIME_TOLERANCE_S,
    }


def _dimension(rules: dict[str, pd.Series], n: int) -> dict:
    """Collapse per-rule masks into rule counts plus rows-failing-any total."""
    counts = {name: int(mask.sum()) for name, mask in rules.items()}
    if rules:
        any_fail = pd.concat(rules.values(), axis=1).any(axis=1)
        fail_rows = int(any_fail.sum())
    else:
        fail_rows = 0
    return {"fail_rows": fail_rows, "rules": counts}


def quality_counts(df: pd.DataFrame, real_columns: list[str] | None = None) -> dict:
    """Compute all Tier-2 counts from an in-memory DataFrame (the dev path).

    Returns a dict with ``n``, completeness cell counts + per-column nulls, and
    the validity/consistency/uniqueness sub-dicts.
    """
    cols = real_columns or REAL_COLUMNS
    n = len(df)

    null_per_col = {c: int(df[c].isna().sum()) for c in cols}
    null_cells = sum(null_per_col.values())

    validity = _dimension(_validity_rules(df), n)
    consistency = _dimension(_consistency_rules(df), n)
    duplicate_rows = int(df.duplicated(subset=cols).sum())

    return {
        "n": n,
        "completeness": {
            "null_cells": null_cells,
            "total_cells": n * len(cols),
            "null_per_col": null_per_col,
        },
        "validity": validity,
        "consistency": consistency,
        "uniqueness": {"duplicate_rows": duplicate_rows},
    }


def month_aggregate_sql(view: str = "t") -> str:
    """One single-pass aggregation producing Tier-1 structural + Tier-2 quality counts.

    Used by the month path so full-month validation never loads the parquet into
    pandas. ``view`` is a DuckDB relation already filtered to HV0003.
    """
    money_neg_any = " OR ".join(f'"{c}" < 0' for c in MONEY_COLUMNS)
    flag_bad_any = " OR ".join(f"\"{f}\" NOT IN ('Y','N')" for f in FLAG_COLUMNS)
    null_terms = " + ".join(f'(count(*) - count("{c}"))' for c in REAL_COLUMNS)
    required_null_terms = " + ".join(f'(count(*) - count("{c}"))' for c in NON_NULL_COLUMNS)

    validity_any = f"({money_neg_any}) OR (trip_miles < 0) OR ({flag_bad_any})"
    consistency_any = (
        "(dropoff_datetime < pickup_datetime) OR "
        "(abs(trip_time - date_diff('second', pickup_datetime, dropoff_datetime)) "
        f"> {TRIP_TIME_TOLERANCE_S})"
    )
    zone_oob = (
        f"PULocationID NOT BETWEEN {ZONE_MIN} AND {ZONE_MAX} OR "
        f"DOLocationID NOT BETWEEN {ZONE_MIN} AND {ZONE_MAX}"
    )
    return f"""
        SELECT
            count(*) AS n,
            ({null_terms}) AS null_cells,
            ({required_null_terms}) AS required_nulls,
            sum(CASE WHEN {zone_oob} THEN 1 ELSE 0 END) AS zone_out_of_range,
            sum(CASE WHEN trip_time < 0 THEN 1 ELSE 0 END) AS trip_time_negative,
            sum(CASE WHEN hvfhs_license_num <> 'HV0003' THEN 1 ELSE 0 END) AS license_bad,
            sum(CASE WHEN {validity_any} THEN 1 ELSE 0 END) AS validity_fail_rows,
            sum(CASE WHEN {consistency_any} THEN 1 ELSE 0 END) AS consistency_fail_rows,
            (count(*) - count(DISTINCT ({", ".join(REAL_COLUMNS)}))) AS duplicate_rows
        FROM {view}
    """


def parse_month_aggregate(row: dict) -> tuple[dict, dict]:
    """Split a month aggregation row into a Tier-1 ``tier1`` dict and ``counts``."""
    structural = [
        ("required columns", "not_null", int(row["required_nulls"])),
        (
            "PULocationID/DOLocationID",
            f"in_range({ZONE_MIN},{ZONE_MAX})",
            int(row["zone_out_of_range"]),
        ),
        ("trip_time", "ge(0)", int(row["trip_time_negative"])),
        ("hvfhs_license_num", "isin(['HV0003'])", int(row["license_bad"])),
    ]
    failures = [
        {"column": col, "check": chk, "count": cnt} for col, chk, cnt in structural if cnt > 0
    ]
    tier1 = {"passed": len(failures) == 0, "failures": failures}

    n = int(row["n"])
    counts = {
        "n": n,
        "completeness": {
            "null_cells": int(row["null_cells"]),
            "total_cells": n * len(REAL_COLUMNS),
            "null_per_col": {},  # per-column nulls omitted on the scale path
        },
        "validity": {"fail_rows": int(row["validity_fail_rows"]), "rules": {}},
        "consistency": {"fail_rows": int(row["consistency_fail_rows"]), "rules": {}},
        "uniqueness": {"duplicate_rows": int(row["duplicate_rows"])},
    }
    return tier1, counts
