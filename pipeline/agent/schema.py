"""Structured types for the triage agent.

``TriageRequest`` is what the LLM extracts from free text (untrusted input).
``TriageDecision`` is what the deterministic guardrail layer produces from it.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class TriageRequest(BaseModel):
    """A regulator data request parsed into structure. The model fills these
    fields; nothing here is trusted to drive a decision."""

    requester: str
    scope: str
    fields: list[str] = []
    window: str | None = None
    claimed_legal_basis: str | None = None


class Verdict(StrEnum):
    ALLOW = "allow"  # maps to a profile; still requires human approval to export
    REFUSE = "refuse"  # out of policy; fails closed
    ESCALATE = "escalate"  # ambiguous / needs human or legal review; fails closed


class TriageDecision(BaseModel):
    verdict: Verdict
    profile: str | None = None
    fields_allowed: list[str] = []
    fields_refused: list[str] = []
    reasons: list[str] = []
