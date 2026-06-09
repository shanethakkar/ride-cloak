"""k-anonymity: equivalence classes, small-cell suppression, uniqueness.

Pandas functions for the dev path and matching DuckDB SQL builders for the
full-month path, so equivalence classes can be computed at scale without loading
the raw parquet into pandas. A quasi-identifier (QI) is a tuple of columns; an
equivalence class is the set of rows sharing a QI value.
"""

from __future__ import annotations

import pandas as pd


def class_sizes(df: pd.DataFrame, qi: list[str]) -> pd.Series:
    """Equivalence-class size for each row, grouped on the QI tuple."""
    work = df.assign(_one=1)
    return work.groupby(qi, dropna=False)["_one"].transform("size")


def uniqueness(df: pd.DataFrame, qi: list[str]) -> float:
    """Share of rows that are unique on the QI tuple (in a class of size 1)."""
    if len(df) == 0:
        return 0.0
    return float((class_sizes(df, qi) == 1).mean())


def suppress_below_k(df: pd.DataFrame, qi: list[str], k: int) -> tuple[pd.DataFrame, dict]:
    """Drop rows in equivalence classes smaller than k (record suppression).

    Returns the surviving frame and an audit record with the ledger fields
    rows_in / rows_out / cells_suppressed / k_achieved.
    """
    sizes = class_sizes(df, qi)
    keep = sizes >= k
    kept = df[keep]
    rows_in, rows_out = len(df), int(keep.sum())
    k_achieved = int(class_sizes(kept, qi).min()) if rows_out else None
    audit = {
        "qi": qi,
        "k": k,
        "rows_in": rows_in,
        "rows_out": rows_out,
        "cells_suppressed": rows_in - rows_out,
        "k_achieved": k_achieved,
    }
    return kept, audit


# --- Scale path: DuckDB SQL builders (pure strings) --------------------------


def _grouped(view: str, qi_exprs: list[str]) -> str:
    by = ", ".join(str(i + 1) for i in range(len(qi_exprs)))
    cols = ", ".join(qi_exprs)
    return f"SELECT {cols}, count(*) AS sz FROM {view} GROUP BY {by}"


def uniqueness_sql(view: str, qi_exprs: list[str]) -> str:
    """Single-value query: share of rows in size-1 classes over a QI expression list."""
    return (
        f"WITH c AS ({_grouped(view, qi_exprs)}) "
        "SELECT sum(CASE WHEN sz = 1 THEN sz ELSE 0 END)::double / sum(sz) AS uniq FROM c"
    )


def suppression_sql(view: str, qi_exprs: list[str], k: int) -> str:
    """Single-value query: share of rows in classes smaller than k."""
    return (
        f"WITH c AS ({_grouped(view, qi_exprs)}) "
        f"SELECT sum(CASE WHEN sz < {int(k)} THEN sz ELSE 0 END)::double / sum(sz) AS supp FROM c"
    )


def k_achieved_sql(view: str, qi_exprs: list[str], k: int) -> str:
    """Single-value query: the minimum surviving class size after k-suppression."""
    return f"WITH c AS ({_grouped(view, qi_exprs)}) SELECT min(sz) FROM c WHERE sz >= {int(k)}"
