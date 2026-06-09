"""Approval records for human-gated exports.

An approval is a small JSON file under ``outputs/approvals/`` written by the
human-only ``ridecloak approve`` command (SPEC section 13). The export runner
checks for one before running an approval-gated profile and fails closed if it is
absent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pipeline.io.readers import read_json
from pipeline.io.writers import write_json


def approval_path(request_id: str, approvals_dir: Path) -> Path:
    return approvals_dir / f"{request_id}.json"


def write_approval(request_id: str, approvals_dir: Path, operator: str, note: str = "") -> Path:
    """Record an approval. Caller is a human via the CLI (SPEC section 13)."""
    record = {
        "request_id": request_id,
        "operator": operator,
        "note": note,
        "approved_utc": datetime.now(UTC).isoformat(),
    }
    return write_json(approval_path(request_id, approvals_dir), record)


def approval_exists(request_id: str | None, approvals_dir: Path) -> bool:
    return bool(request_id) and approval_path(request_id, approvals_dir).exists()


def read_approval(request_id: str, approvals_dir: Path) -> dict:
    return read_json(approval_path(request_id, approvals_dir))
