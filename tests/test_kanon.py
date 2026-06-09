"""k-anonymity tests: uniqueness, small-cell suppression, and SQL/pandas parity."""

from __future__ import annotations

import pandas as pd

from pipeline.io import duck
from pipeline.transform import kanon


def _fixture():
    # Classes on (a, b): (1,10) size 2, (2,20) size 2, (3,30) size 1 (the lone cell).
    return pd.DataFrame({"a": [1, 1, 2, 2, 3], "b": [10, 10, 20, 20, 30]})


def test_uniqueness_is_share_of_size_one_classes():
    assert kanon.uniqueness(_fixture(), ["a", "b"]) == 0.2  # 1 of 5 rows is unique


def test_suppress_drops_exactly_the_one_below_k():
    df = _fixture()
    kept, audit = kanon.suppress_below_k(df, ["a", "b"], k=2)
    assert audit["rows_in"] == 5
    assert audit["rows_out"] == 4
    assert audit["cells_suppressed"] == 1
    assert audit["k_achieved"] == 2
    # The dropped row is the lone (3, 30) cell.
    assert not ((kept["a"] == 3) & (kept["b"] == 30)).any()


def test_suppress_below_k_can_empty_the_frame():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [1, 2, 3]})  # all singletons
    kept, audit = kanon.suppress_below_k(df, ["a", "b"], k=2)
    assert audit["rows_out"] == 0
    assert audit["k_achieved"] is None
    assert len(kept) == 0


def test_sql_builders_match_pandas():
    df = _fixture()
    con = duck.connect()
    try:
        con.register("t", df)
        sql_uniq = con.execute(kanon.uniqueness_sql("t", ["a", "b"])).fetchone()[0]
        sql_supp = con.execute(kanon.suppression_sql("t", ["a", "b"], 2)).fetchone()[0]
        sql_kach = con.execute(kanon.k_achieved_sql("t", ["a", "b"], 2)).fetchone()[0]
    finally:
        con.close()
    assert sql_uniq == kanon.uniqueness(df, ["a", "b"])  # 0.2
    # suppression fraction == cells_suppressed / rows_in from the pandas audit
    _, audit = kanon.suppress_below_k(df, ["a", "b"], 2)
    assert sql_supp == audit["cells_suppressed"] / audit["rows_in"]
    assert sql_kach == audit["k_achieved"]
