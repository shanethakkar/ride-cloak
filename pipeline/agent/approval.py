"""Pending triage records: the agent's draft-only output.

A triage run writes a *pending* record here -- a recommendation, not an approval.
Releasing data still requires a human to run ``ridecloak approve`` and then
``ridecloak export``. This module writes records; it never exports.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from config.settings import Settings
from pipeline.agent.schema import TriageDecision, TriageRequest
from pipeline.io.writers import write_json


def new_request_id() -> str:
    return f"treq-{uuid.uuid4().hex[:10]}"


def queue_triage(
    settings: Settings,
    request_id: str,
    parsed: TriageRequest,
    decision: TriageDecision,
    draft: str,
) -> Path:
    """Write a pending triage record under ``outputs/triage/`` (gitignored)."""
    record = {
        "request_id": request_id,
        "status": "pending",
        "verdict": decision.verdict.value,
        "profile": decision.profile,
        "fields_allowed": decision.fields_allowed,
        "fields_refused": decision.fields_refused,
        "reasons": decision.reasons,
        "requester": parsed.requester,
        "scope": parsed.scope,
        "draft": draft,
        "created_utc": datetime.now(UTC).isoformat(),
    }
    return write_json(settings.triage_dir / f"{request_id}.json", record)
