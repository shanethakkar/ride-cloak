"""Dashboard extract + figure tests (offline, synthetic ledger)."""

from __future__ import annotations

import pandas as pd

from pipeline.dashboard import extract, figures


def _entries():
    base = "2026-06-09T00:00:00+00:00"
    return [
        {
            "seq": 0,
            "timestamp_utc": base,
            "command": "fetch",
            "operator": "op",
            "entry_hash": "a" * 64,
            "metrics": {"month": "2026-01"},
        },
        {
            "seq": 1,
            "timestamp_utc": base,
            "command": "validate",
            "operator": "op",
            "entry_hash": "b" * 64,
            "metrics": {"health_score": 99.5, "refused": False, "source": "month:2026-01"},
        },
        {
            "seq": 2,
            "timestamp_utc": base,
            "command": "risk",
            "operator": "op",
            "entry_hash": "c" * 64,
            "source": "month:2026-01",
            "metrics": {
                "k": 5,
                "ladder": [
                    {"qi": "zone x minute", "uniqueness": 0.9},
                    {"qi": "borough x 15min", "uniqueness": 0.05},
                ],
            },
        },
        {
            "seq": 3,
            "timestamp_utc": base,
            "command": "export",
            "operator": "op",
            "entry_hash": "d" * 64,
            "source": "month:2026-01",
            "policy_name": "mds_aggregate",
            "output_kind": "aggregate",
            "rows_in": 1000,
            "rows_out": 950,
            "cells_suppressed": 50,
            "k_achieved": 5,
            "gate": {"health_score": None},
            "refused": False,
        },
        {
            "seq": 4,
            "timestamp_utc": "2026-06-09T10:00:00+00:00",
            "command": "triage",
            "operator": "op",
            "entry_hash": "e" * 64,
            "metrics": {
                "request_id": "treq-2",
                "verdict": "allow",
                "profile": "le",
                "pii_redacted_in_draft": 0,
            },
        },
        {
            "seq": 5,
            "timestamp_utc": "2026-06-09T11:00:00+00:00",
            "command": "approve",
            "operator": "op",
            "entry_hash": "f" * 64,
            "metrics": {"request_id": "treq-2"},
        },
        {
            "seq": 6,
            "timestamp_utc": "2026-06-09T12:00:00+00:00",
            "command": "export",
            "operator": "op",
            "entry_hash": "0" * 64,
            "approval_id": "treq-2",
            "source": "dev",
            "policy_name": "law_enforcement_extract",
            "output_kind": "row_level",
            "rows_in": 100,
            "rows_out": 100,
            "cells_suppressed": 0,
            "k_achieved": None,
            "gate": {"health_score": 99.9},
            "refused": False,
        },
    ]


def test_month_and_scope_mapping():
    assert extract.month_of("month:2026-03", "2026-04") == "2026-03"
    assert extract.month_of("dev", "2026-04") == "2026-04"
    assert extract.scope_of("dev") == "dev"
    assert extract.scope_of("month:2026-03") == "month"


def test_exports_table_computes_suppression_rate():
    df = extract.exports(_entries(), "2026-04")
    assert len(df) == 2
    mds = df[df["policy_name"] == "mds_aggregate"].iloc[0]
    assert mds["month"] == "2026-01" and mds["scope"] == "month"
    assert mds["suppression_rate"] == 50 / 1000


def test_uniqueness_table_expands_ladder_with_scope():
    df = extract.uniqueness(_entries(), "2026-04")
    assert list(df["qi"]) == ["zone x minute", "borough x 15min"]
    assert set(df["scope"]) == {"month"}
    assert df[df["qi"] == "borough x 15min"]["uniqueness"].iloc[0] == 0.05


def test_requests_turnaround_join():
    df = extract.requests(_entries())
    row = df[df["request_id"] == "treq-2"].iloc[0]
    assert row["final_status"] == "exported"
    assert row["turnaround_hours"] == 2.0  # triage 10:00 -> export 12:00


def test_detection_table_includes_overall():
    report = {
        "detection": {
            "per_entity": {
                "PERSON": {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 5, "fp": 0, "fn": 0}
            },
            "overall": {"precision": 0.99, "recall": 0.99, "f1": 0.99, "tp": 5, "fp": 0, "fn": 0},
        }
    }
    df = extract.detection(report)
    assert set(df["entity"]) == {"PERSON", "overall"}


def test_uniqueness_figure_renders(tmp_path):
    df = pd.DataFrame(
        {
            "month": ["2026-04"] * 4,
            "scope": ["month"] * 4,
            "qi": ["zone x minute", "zone x 15min", "zone x 60min", "borough x 15min"],
            "uniqueness": [0.9, 0.46, 0.21, 0.001],
        }
    )
    out = figures.fig_uniqueness_ladder(df, "2026-04", tmp_path / "u.png")
    assert out.exists() and out.stat().st_size > 0


def test_detection_figure_renders(tmp_path):
    df = pd.DataFrame(
        {
            "entity": ["PERSON", "EMAIL_ADDRESS", "overall"],
            "precision": [0.99, 1.0, 0.99],
            "recall": [0.99, 1.0, 0.99],
        }
    )
    out = figures.fig_detection(df, tmp_path / "d.png")
    assert out.exists() and out.stat().st_size > 0
