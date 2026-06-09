"""Transform-primitive tests: generalization, pseudonymization, suppression, salts."""

from __future__ import annotations

import pandas as pd

from pipeline.io import salts
from pipeline.transform import generalize, pseudonymize, suppress


def test_round_time_floors_to_bucket():
    s = pd.Series(
        pd.to_datetime(["2026-04-01 00:07:30", "2026-04-01 00:15:00", "2026-04-01 00:29:59"])
    )
    out = generalize.round_time(s, 15)
    assert list(out.astype(str)) == [
        "2026-04-01 00:00:00",
        "2026-04-01 00:15:00",
        "2026-04-01 00:15:00",
    ]


def test_rollup_zone_maps_via_lookup():
    s = pd.Series([1, 2, 3])
    out = generalize.rollup_zone(s, {1: "Manhattan", 2: "Queens", 3: "Manhattan"})
    assert list(out) == ["Manhattan", "Queens", "Manhattan"]


def test_same_salt_same_pseudonym_different_salt_disjoint():
    s = pd.Series(["rider-a", "rider-b", "rider-a"])
    salt1 = b"\x01" * 16
    salt2 = b"\x02" * 16
    p1 = pseudonymize.pseudonymize(s, salt1)
    p1_again = pseudonymize.pseudonymize(s, salt1)
    p2 = pseudonymize.pseudonymize(s, salt2)
    # Deterministic and stable within a salt: equal values -> equal pseudonyms.
    assert list(p1) == list(p1_again)
    assert p1.iloc[0] == p1.iloc[2]
    # Different salt -> disjoint pseudonyms for the same input.
    assert set(p1).isdisjoint(set(p2))


def test_pseudonymize_passes_nulls_through():
    s = pd.Series(["x", None])
    out = pseudonymize.pseudonymize(s, b"salt")
    assert pd.isna(out.iloc[1])
    assert pd.notna(out.iloc[0])


def test_salt_fingerprint_is_deterministic_and_not_the_salt():
    salt = salts.generate_salt()
    fp = pseudonymize.salt_fingerprint(salt)
    assert len(salt) == salts.SALT_BYTES
    assert fp == pseudonymize.salt_fingerprint(salt)
    assert salt.hex() != fp  # fingerprint is a hash, not the salt value


def test_salt_write_read_roundtrip(tmp_path):
    salt = salts.generate_salt()
    path = salts.write_salt(salt, tmp_path / "salts")
    assert path.name.endswith(".salt")
    assert salts.read_salt(path) == salt


def test_drop_columns_reports_dropped():
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
    out, audit = suppress.drop_columns(df, ["b", "missing"])
    assert list(out.columns) == ["a", "c"]
    assert audit["dropped_columns"] == ["b"]


def test_redact_spans_masks_exact_offsets():
    text = "Call John Doe at 212.555.1234 now"
    # spans for "John Doe" (5..13) and the phone (17..29)
    out = suppress.redact_spans(text, [(5, 13), (17, 29)], mask="X")
    assert out == "Call X at X now"


def test_redact_series_counts_rows_and_spans():
    texts = pd.Series(["John at 212.555.1234", "no pii here", None])
    detections = [
        [{"start": 0, "end": 4}, {"start": 8, "end": 20}],
        [],
        [],
    ]
    out, audit = suppress.redact_series(texts, detections, mask="*")
    assert audit["rows_redacted"] == 1
    assert audit["spans_masked"] == 2
    assert out.iloc[1] == "no pii here"
