"""Write helpers. All writes are idempotent: re-running overwrites cleanly.

File-producing operations create parent directories as needed and replace any
existing file at the target path, never appending or duplicating.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Write a dict as pretty JSON, creating parent dirs. Overwrites."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True, default=str)
        fh.write("\n")
    return path


def write_parquet(df: pd.DataFrame, path: Path) -> Path:
    """Write a DataFrame to parquet, creating parent dirs. Overwrites."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def write_text(path: Path, text: str) -> Path:
    """Write a text artifact (e.g. a markdown report), creating parent dirs. Overwrites."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(text)
    return path
