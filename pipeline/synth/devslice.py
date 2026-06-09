"""Dev-slice builder: deterministic 250K-row Uber sample with the synthetic layer.

I/O orchestration (not pure): selects a reproducible sample from the cached
monthly Parquet via DuckDB, hands the rows to the pure synth generator, and
writes the dev slice and ground-truth labels. The sample is deterministic
because rows are ordered by a hash of their attributes and the top N taken under
a single thread, so the same month + seed reproduce a byte-identical slice.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from config.settings import Settings
from pipeline.io import duck, writers
from pipeline.synth import generator

# Columns whose hash defines the deterministic sample ordering. Spans enough
# attributes that distinct rows get distinct order keys (no boundary ties).
_ORDER_COLS = [
    "request_datetime",
    "pickup_datetime",
    "dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "trip_miles",
    "base_passenger_fare",
    "driver_pay",
    "tips",
    "trip_time",
]


def _order_expr() -> str:
    casts = ", ".join(f"CAST({c} AS VARCHAR)" for c in _ORDER_COLS)
    return f"md5(concat_ws('|', {casts}))"


def _sha256_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            sha.update(chunk)
    return sha.hexdigest()


def select_uber_sample(settings: Settings, month: str):
    """Return a deterministic ``dev_slice_rows`` sample of HV0003 trips for ``month``."""
    raw_path = settings.raw_parquet_path(month)
    if not raw_path.exists():
        raise FileNotFoundError(
            f"No cached month at {raw_path}. Run `ridecloak fetch --month {month}` first."
        )
    sql = (
        "SELECT * FROM read_parquet(?) "
        "WHERE hvfhs_license_num = ? "
        f"ORDER BY {_order_expr()} "
        "LIMIT ?"
    )
    # threads=1 makes the top-N ordering reproducible run to run.
    return duck.query_df(
        sql,
        params=[str(raw_path), settings.uber_license_num, settings.dev_slice_rows],
        threads=1,
    )


def build_dev_slice(
    settings: Settings,
    month: str | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Build and write the dev slice + labels; return a summary with the slice hash."""
    month = month or settings.dev_source_month
    seed = seed if seed is not None else settings.synth_seed

    sample = select_uber_sample(settings, month)
    enriched, labels, stats = generator.generate(sample, seed)

    slice_path = settings.dev_slice_path
    labels_path = settings.labels_path
    writers.write_parquet(enriched, slice_path)
    writers.write_parquet(labels, labels_path)

    return {
        **stats,
        "month": month,
        "seed": seed,
        "slice_path": str(slice_path),
        "labels_path": str(labels_path),
        "slice_sha256": _sha256_file(slice_path),
    }
