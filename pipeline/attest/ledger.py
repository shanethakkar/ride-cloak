"""Hash-chained, append-only JSONL ledger.

Each entry is a flat dict: an envelope (seq, timestamp_utc, run_id, command,
operator, prev_entry_hash, entry_hash) plus the command's record (provenance
hashes and, for an export, the full audit). The entry hash covers everything
except itself and chains to the previous entry, so any later mutation is
detectable and ``verify`` reports the exact break point.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

GENESIS_HASH = "0" * 64
_ENVELOPE_ONLY = {"entry_hash"}


def _canonical_json(entry: dict) -> str:
    """Deterministic serialization for hashing (sorted keys, no whitespace)."""
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), default=str)


def compute_entry_hash(entry: dict) -> str:
    """SHA-256 over the entry minus its own ``entry_hash`` field."""
    body = {k: v for k, v in entry.items() if k not in _ENVELOPE_ONLY}
    return hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()


def read_entries(ledger_path: Path) -> list[dict]:
    """Return all entries in order, or [] if the ledger does not exist yet."""
    if not ledger_path.exists():
        return []
    with ledger_path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def append(
    ledger_path: Path,
    record: dict,
    command: str,
    operator: str,
    run_id: str | None = None,
) -> dict:
    """Append a new entry chaining to the last one; return the written entry."""
    entries = read_entries(ledger_path)
    prev = entries[-1]["entry_hash"] if entries else GENESIS_HASH
    entry = {
        "seq": len(entries),
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "run_id": run_id or str(uuid.uuid4()),
        "command": command,
        "operator": operator,
        "prev_entry_hash": prev,
        **record,
    }
    entry["entry_hash"] = compute_entry_hash(entry)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(_canonical_json(entry) + "\n")
    return entry


def verify(ledger_path: Path) -> dict:
    """Walk the chain. Return ``{ok, entries, break_seq, reason}``.

    On the first inconsistency, ``ok`` is False and ``break_seq`` is the seq of
    the offending entry.
    """
    entries = read_entries(ledger_path)
    prev = GENESIS_HASH
    for i, entry in enumerate(entries):
        if entry.get("seq") != i:
            return _break(i, f"seq mismatch (expected {i}, got {entry.get('seq')})", len(entries))
        if entry.get("prev_entry_hash") != prev:
            return _break(i, "prev_entry_hash linkage broken", len(entries))
        if compute_entry_hash(entry) != entry.get("entry_hash"):
            return _break(i, "entry_hash mismatch (entry was mutated)", len(entries))
        prev = entry["entry_hash"]
    return {"ok": True, "entries": len(entries), "break_seq": None, "reason": None}


def _break(seq: int, reason: str, total: int) -> dict:
    return {"ok": False, "entries": total, "break_seq": seq, "reason": reason}
