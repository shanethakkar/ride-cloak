"""Export-runner tests: gate + approval guards, the three profiles, and a toy
fourth policy proving new regulator = new YAML, zero code.

Uses a SimpleNamespace 'settings' pointing at tmp_path so all I/O is isolated.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

from pipeline.export import runner
from pipeline.io import approvals
from policies.schema import Policy
from tests.test_validate import clean_df

# Borough lookup covering every zone id the fixture can draw.
LOOKUP = {i: f"Boro{i % 5}" for i in range(1, 266)}
NO_DETECTIONS = lambda texts: [[] for _ in texts]  # noqa: E731


def _fixture_df(n: int = 300) -> pd.DataFrame:
    """A gate-passing frame with the synthetic identity columns attached."""
    df = clean_df(n)
    rng = np.random.default_rng(3)
    df["trip_id"] = [f"trip-{i:05d}" for i in range(n)]
    df["driver_name"] = "Jane Doe"
    df["rider_id"] = [f"rider-{i % 50}" for i in range(n)]
    df["rider_phone"] = "212-555-0000"
    df["rider_email"] = "r@example.com"
    df["device_id"] = "dev-1"
    df["payment_token"] = "tok-1"
    df["driver_license_num"] = "1234567"
    df["vehicle_plate"] = "ABC-1234"
    df["vehicle_vin"] = "1HGCM82633A004352"
    notes = np.where(rng.random(n) < 0.3, "Rider John at 212.555.1234", None)
    df["support_note"] = pd.array(notes, dtype="string")
    return df


def _settings(tmp_path) -> SimpleNamespace:
    return SimpleNamespace(
        gate_threshold=90,
        project_root=tmp_path,
        exports_dir=tmp_path / "exports",
        reports_dir=tmp_path / "reports",
        approvals_dir=tmp_path / "approvals",
        salts_dir=tmp_path / "salts",
    )


def _policy(name, **row):
    return Policy.model_validate(
        {
            "name": name,
            "version": 1,
            "description": "test",
            "output_kind": "row_level",
            "row_level": row,
        }
    )


def test_row_level_export_pseudonymizes_and_writes(tmp_path):
    s = _settings(tmp_path)
    policy = _policy(
        "p_tlc", pseudonymize_columns=["trip_id", "driver_name"], time_bucket_minutes=15
    )
    result = runner.run_export(
        _fixture_df(), policy, "h" * 64, s, LOOKUP, "dev", "ih", note_detector=NO_DETECTIONS
    )
    assert result["refused"] is False
    assert result["salt_fingerprint"] != "n/a"
    out = pd.read_parquet(s.exports_dir / "p_tlc_dev.parquet")
    assert (out["driver_name"] != "Jane Doe").all()  # pseudonymized
    assert (out["pickup_datetime"].dt.minute % 15 == 0).all()  # 15-min floor


def test_redaction_masks_detected_spans(tmp_path):
    s = _settings(tmp_path)
    policy = _policy("p_redact", redact_note=True)

    def detector(texts):
        # Mask "John" (chars 6-10) wherever a note exists.
        return [[{"start": 6, "end": 10}] if isinstance(t, str) else [] for t in texts]

    runner.run_export(
        _fixture_df(), policy, "h" * 64, s, LOOKUP, "dev", "ih", note_detector=detector
    )
    out = pd.read_parquet(s.exports_dir / "p_redact_dev.parquet")
    noted = out["support_note"].dropna()
    assert (~noted.str.contains("John")).all()
    assert noted.str.contains("REDACTED").all()


def test_aggregate_export_suppresses_small_cells(tmp_path):
    s = _settings(tmp_path)
    policy = Policy.model_validate(
        {
            "name": "p_mds",
            "version": 1,
            "description": "t",
            "output_kind": "aggregate",
            "aggregate": {"dimensions": ["PUBorough", "DOBorough", "pickup_bucket"], "k": 5},
        }
    )
    result = runner.run_export(_fixture_df(2000), policy, "h" * 64, s, LOOKUP, "dev", "ih")
    out = pd.read_csv(s.exports_dir / "p_mds_dev.csv")
    assert (out["trip_count"] >= 5).all()  # every released cell meets k
    assert result["cells_suppressed"] >= 0


def test_le_without_approval_fails_closed(tmp_path):
    s = _settings(tmp_path)
    policy = _policy("p_le", pseudonymize_columns=["trip_id"])
    policy.requires_approval = True
    result = runner.run_export(
        _fixture_df(), policy, "h" * 64, s, LOOKUP, "dev", "ih", approval_id=None
    )
    assert result["refused"] is True
    assert "approval" in result["reason"]
    assert not (s.exports_dir / "p_le_dev.parquet").exists()  # no file written
    assert (s.reports_dir / "export_p_le_dev.md").exists()  # but a refusal is logged


def test_le_with_approval_succeeds(tmp_path):
    s = _settings(tmp_path)
    approvals.write_approval("req-1", s.approvals_dir, operator="tester")
    policy = _policy(
        "p_le", pseudonymize_columns=["trip_id"], select_columns=["trip_id", "PULocationID"]
    )
    policy.requires_approval = True
    result = runner.run_export(
        _fixture_df(), policy, "h" * 64, s, LOOKUP, "dev", "ih", approval_id="req-1"
    )
    assert result["refused"] is False
    assert (s.exports_dir / "p_le_dev.parquet").exists()


def test_toy_fourth_policy_exports_with_zero_code(tmp_path):
    """A brand-new regulator profile is just a new Policy -> it must export as-is."""
    s = _settings(tmp_path)
    policy = _policy(
        "toy_regulator",
        pseudonymize_columns=["rider_id"],
        drop_columns=["support_note"],
        select_columns=["rider_id", "PULocationID", "DOLocationID", "base_passenger_fare"],
    )
    result = runner.run_export(_fixture_df(), policy, "h" * 64, s, LOOKUP, "dev", "ih")
    assert result["refused"] is False
    out = pd.read_parquet(s.exports_dir / "toy_regulator_dev.parquet")
    assert list(out.columns) == ["rider_id", "PULocationID", "DOLocationID", "base_passenger_fare"]
