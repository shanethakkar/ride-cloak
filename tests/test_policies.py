"""Policy schema + compiler tests (pure, fast)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from config.settings import get_settings
from pipeline.export.profiles import compile_policy
from policies.schema import Policy, load_policy

settings = get_settings()
PROFILES = ["tlc_trip_submission", "mds_aggregate", "law_enforcement_extract"]


@pytest.mark.parametrize("name", PROFILES)
def test_shipped_policies_load_and_validate(name):
    policy, phash = load_policy(settings.policies_dir / f"{name}.yaml")
    assert policy.name == name
    assert len(phash) == 64  # sha256 hex


def test_compile_tlc_plan_order():
    policy, _ = load_policy(settings.policies_dir / "tlc_trip_submission.yaml")
    ops = [s["op"] for s in compile_policy(policy)]
    assert ops == ["redact_note", "pseudonymize", "generalize_time"]


def test_compile_le_plan_order():
    policy, _ = load_policy(settings.policies_dir / "law_enforcement_extract.yaml")
    ops = [s["op"] for s in compile_policy(policy)]
    assert ops == ["pseudonymize", "generalize_time", "select"]
    assert policy.requires_approval is True


def test_compile_mds_is_single_aggregate_step():
    policy, _ = load_policy(settings.policies_dir / "mds_aggregate.yaml")
    plan = compile_policy(policy)
    assert len(plan) == 1 and plan[0]["op"] == "aggregate"
    assert plan[0]["k"] == 5


def test_policy_rejects_kind_block_mismatch():
    with pytest.raises(ValidationError):
        Policy.model_validate(
            {"name": "x", "version": 1, "description": "d", "output_kind": "row_level"}
        )
