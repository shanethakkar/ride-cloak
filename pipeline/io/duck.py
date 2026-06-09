"""DuckDB helpers: connect, query Parquet in place, introspect schema.

DuckDB is the scale tool. Monthly HVFHV files hold ~17-20M rows; we query the
Parquet directly here and pull only filtered or aggregated results into pandas.
Never read a full monthly file into pandas (CLAUDE.md scale guardrail).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


def connect(threads: int | None = None) -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB connection.

    Args:
        threads: pin the thread count for deterministic ops (e.g. sampling).
            None leaves DuckDB's default.

    Returns:
        A new in-memory connection.
    """
    con = duckdb.connect(database=":memory:")
    if threads is not None:
        con.execute(f"SET threads TO {int(threads)}")
    return con


def introspect_schema(parquet_path: Path) -> list[dict[str, str]]:
    """Return the Parquet schema as ordered ``{name, type}`` records.

    Uses ``DESCRIBE`` so the recorded schema is the file's actual schema, not an
    assumed one (TLC revises the HVFHV format; the contract derives from this).
    """
    con = connect()
    try:
        rel = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(parquet_path)]).fetchall()
    finally:
        con.close()
    # DESCRIBE columns: column_name, column_type, null, key, default, extra
    return [{"name": row[0], "type": row[1]} for row in rel]


def row_count(parquet_path: Path, where: str | None = None) -> int:
    """Count rows in a Parquet file, optionally under a SQL WHERE predicate."""
    con = connect()
    try:
        sql = "SELECT count(*) FROM read_parquet(?)"
        if where:
            sql += f" WHERE {where}"
        return int(con.execute(sql, [str(parquet_path)]).fetchone()[0])
    finally:
        con.close()


def query_df(sql: str, params: list | None = None, threads: int | None = None) -> pd.DataFrame:
    """Run a query and return a pandas DataFrame. Caller guarantees the result is
    filtered/aggregated small enough for pandas."""
    con = connect(threads=threads)
    try:
        return con.execute(sql, params or []).df()
    finally:
        con.close()
