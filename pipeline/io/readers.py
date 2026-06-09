"""Read helpers for small artifacts (JSON manifests, parquet slices, CSV lookups).

Large monthly Parquet is read through DuckDB (see duck.py), never here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def read_json(path: Path) -> dict[str, Any]:
    """Load a JSON file into a dict."""
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def read_parquet(path: Path) -> pd.DataFrame:
    """Read a parquet file already known to be small (dev slice, labels)."""
    return pd.read_parquet(path)


def read_csv(path: Path) -> pd.DataFrame:
    """Read a small CSV (e.g. the taxi zone lookup)."""
    return pd.read_csv(path)
