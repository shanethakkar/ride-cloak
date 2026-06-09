"""Pydantic schema for declarative sharing policies.

A policy is a YAML file describing how one regulator profile transforms the data.
The schema is the contract: the compiler (pipeline.export.profiles) turns a valid
policy into an ordered transform plan, so a new regulator is a new YAML file with
zero code changes. Policies are validated on load; a malformed policy fails fast.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, model_validator


class OutputKind(StrEnum):
    ROW_LEVEL = "row_level"
    AGGREGATE = "aggregate"


class KAnonSpec(BaseModel):
    qi: list[str]
    k: int


class RowLevelSpec(BaseModel):
    pseudonymize_columns: list[str] = []
    time_bucket_minutes: int | None = None
    rollup_zone: bool = False
    redact_note: bool = False
    drop_columns: list[str] = []
    select_columns: list[str] | None = None  # None keeps all surviving columns
    kanon: KAnonSpec | None = None


class AggregateSpec(BaseModel):
    dimensions: list[str]  # e.g. [PUBorough, DOBorough, pickup_bucket]
    time_bucket_minutes: int = 60
    k: int = 5


class Policy(BaseModel):
    name: str
    version: int
    description: str
    output_kind: OutputKind
    requires_approval: bool = False
    row_level: RowLevelSpec | None = None
    aggregate: AggregateSpec | None = None

    @model_validator(mode="after")
    def _block_matches_kind(self) -> Policy:
        if self.output_kind == OutputKind.ROW_LEVEL and self.row_level is None:
            raise ValueError("row_level policy requires a 'row_level' block")
        if self.output_kind == OutputKind.AGGREGATE and self.aggregate is None:
            raise ValueError("aggregate policy requires an 'aggregate' block")
        return self


def policy_hash(raw: dict) -> str:
    """SHA-256 of the canonicalized policy content (for the ledger)."""
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_policy(path: Path) -> tuple[Policy, str]:
    """Load and validate a policy file; return the model and its content hash."""
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return Policy.model_validate(raw), policy_hash(raw)
