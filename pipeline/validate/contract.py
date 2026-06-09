"""Tier-1 structural contract for the 25 real HVFHV columns (hard pass/fail).

Pandera schema covering column presence, dtypes, and value domains that must hold
for the data to be structurally valid. Nullability and domains were calibrated
from a full-month (~15.4M HV0003 rows) profile of 2026-04
(``data/raw/manifests/profile_2026-04.json``): zero nulls observed, all zone IDs
in 1-265, trip_time >= 0. Legitimate value anomalies (negative fares, temporal
outliers) are NOT enforced here; they are Tier-2 quality dings (see checks.py).
"""

from __future__ import annotations

import pandera.pandas as pa
from pandera.errors import SchemaErrors

# Column groups (order matches the introspected schema).
REAL_COLUMNS = [
    "hvfhs_license_num",
    "dispatching_base_num",
    "originating_base_num",
    "request_datetime",
    "on_scene_datetime",
    "pickup_datetime",
    "dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "trip_miles",
    "trip_time",
    "base_passenger_fare",
    "tolls",
    "bcf",
    "sales_tax",
    "congestion_surcharge",
    "airport_fee",
    "tips",
    "driver_pay",
    "shared_request_flag",
    "shared_match_flag",
    "access_a_ride_flag",
    "wav_request_flag",
    "wav_match_flag",
    "cbd_congestion_fee",
]

MONEY_COLUMNS = [
    "base_passenger_fare",
    "tolls",
    "bcf",
    "sales_tax",
    "congestion_surcharge",
    "airport_fee",
    "tips",
    "driver_pay",
    "cbd_congestion_fee",
]

FLAG_COLUMNS = [
    "shared_request_flag",
    "shared_match_flag",
    "access_a_ride_flag",
    "wav_request_flag",
    "wav_match_flag",
]

ZONE_MIN, ZONE_MAX = 1, 265

# Optional columns: nullable in the contract for cross-month robustness even
# though 2026-04 showed zero nulls. Core operational/key columns stay non-null.
_NULLABLE = {
    "originating_base_num",
    "on_scene_datetime",
    "tolls",
    "bcf",
    "sales_tax",
    "congestion_surcharge",
    "airport_fee",
    "tips",
    "cbd_congestion_fee",
}

NULLABLE_COLUMNS = _NULLABLE
NON_NULL_COLUMNS = [c for c in REAL_COLUMNS if c not in _NULLABLE]

_DATETIME_COLUMNS = [
    "request_datetime",
    "on_scene_datetime",
    "pickup_datetime",
    "dropoff_datetime",
]


def build_contract() -> pa.DataFrameSchema:
    """Return the Tier-1 Pandera schema. ``strict=False`` ignores synth columns."""
    columns: dict[str, pa.Column] = {}

    def nullable(name: str) -> bool:
        return name in _NULLABLE

    columns["hvfhs_license_num"] = pa.Column(
        str, pa.Check.isin(["HV0003"]), nullable=False, coerce=True
    )
    columns["dispatching_base_num"] = pa.Column(str, nullable=False, coerce=True)
    columns["originating_base_num"] = pa.Column(str, nullable=True, coerce=True)

    for col in _DATETIME_COLUMNS:
        columns[col] = pa.Column("datetime64[ns]", nullable=nullable(col), coerce=True)

    for col in ("PULocationID", "DOLocationID"):
        columns[col] = pa.Column(
            int, pa.Check.in_range(ZONE_MIN, ZONE_MAX), nullable=False, coerce=True
        )

    columns["trip_miles"] = pa.Column(float, pa.Check.ge(0), nullable=False, coerce=True)
    columns["trip_time"] = pa.Column(int, pa.Check.ge(0), nullable=False, coerce=True)

    for col in MONEY_COLUMNS:
        # No non-negativity here: refunds make negatives legitimate (Tier-2 ding).
        columns[col] = pa.Column(float, nullable=nullable(col), coerce=True)

    for col in FLAG_COLUMNS:
        # Y/N domain is enforced as a Tier-2 validity check, not a hard fail.
        columns[col] = pa.Column(str, nullable=False, coerce=True)

    return pa.DataFrameSchema(columns, strict=False, name="hvfhv_contract", coerce=True)


def validate_contract(df) -> dict:
    """Run the Tier-1 contract. Returns ``{passed, failures}``.

    ``failures`` summarizes violations as ``{column, check, count}`` records.
    Missing required columns and out-of-domain values are both reported here.
    """
    schema = build_contract()
    try:
        schema.validate(df, lazy=True)
        return {"passed": True, "failures": []}
    except SchemaErrors as exc:
        cases = exc.failure_cases
        grouped = cases.groupby(["column", "check"], dropna=False).size().reset_index(name="count")
        failures = [
            {
                "column": None if _is_nan(row.column) else row.column,
                "check": str(row.check),
                "count": int(row.count),
            }
            for row in grouped.itertuples(index=False)
        ]
        return {"passed": False, "failures": failures}


def _is_nan(value) -> bool:
    return value != value  # noqa: PLR0124 (NaN check without importing math)
