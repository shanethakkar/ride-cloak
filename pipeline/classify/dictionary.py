"""Load and validate the field classification dictionary.

The dictionary (``config/classification.yaml``) assigns every column a privacy
tier; downstream transforms key off these tiers. Pydantic validates the file on
load so a malformed or partial dictionary fails fast. ``parse`` is pure; ``load``
adds the file read.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel


class Tier(StrEnum):
    DIRECT = "direct"
    QUASI = "quasi"
    SENSITIVE = "sensitive"
    SAFE = "safe"


class ColumnClass(BaseModel):
    tier: Tier
    rationale: str
    entity_type: str | None = None


class ClassificationDict(BaseModel):
    version: int
    columns: dict[str, ColumnClass]

    def tier_of(self, column: str) -> Tier:
        return self.columns[column].tier

    def columns_in_tier(self, tier: Tier) -> list[str]:
        return [name for name, c in self.columns.items() if c.tier == tier]

    def unclassified(self, present_columns: list[str]) -> list[str]:
        """Columns present in the data but missing from the dictionary."""
        return [c for c in present_columns if c not in self.columns]


def parse(data: dict) -> ClassificationDict:
    """Validate a raw mapping into a ClassificationDict (pure)."""
    return ClassificationDict.model_validate(data)


def load(path: Path) -> ClassificationDict:
    """Read and validate the classification YAML."""
    with path.open("r", encoding="utf-8") as fh:
        return parse(yaml.safe_load(fh))
