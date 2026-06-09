"""Ledger tests: chain integrity, tamper detection at the exact break point,
and byte-identical methodology-report regeneration."""

from __future__ import annotations

import json

from pipeline.attest import ledger, report


def _ledger(tmp_path):
    return tmp_path / "ledger.jsonl"


def _append_three(path):
    ledger.append(path, {"input_hash": "a", "metrics": {"x": 1}}, "fetch", "op")
    ledger.append(path, {"input_hash": "b", "metrics": {"x": 2}}, "synth", "op")
    ledger.append(path, {"input_hash": "c", "metrics": {"x": 3}}, "validate", "op")


def test_intact_chain_verifies(tmp_path):
    path = _ledger(tmp_path)
    _append_three(path)
    result = ledger.verify(path)
    assert result["ok"] is True
    assert result["entries"] == 3
    assert result["break_seq"] is None


def test_chain_links_each_entry_to_the_previous(tmp_path):
    path = _ledger(tmp_path)
    _append_three(path)
    entries = ledger.read_entries(path)
    assert entries[0]["prev_entry_hash"] == ledger.GENESIS_HASH
    assert entries[1]["prev_entry_hash"] == entries[0]["entry_hash"]
    assert entries[2]["prev_entry_hash"] == entries[1]["entry_hash"]


def test_mutating_a_historical_entry_breaks_at_that_seq(tmp_path):
    path = _ledger(tmp_path)
    _append_three(path)
    entries = ledger.read_entries(path)
    entries[1]["metrics"]["x"] = 999  # tamper with seq 1, leave its entry_hash
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")

    result = ledger.verify(path)
    assert result["ok"] is False
    assert result["break_seq"] == 1
    assert "mutated" in result["reason"]


def test_entry_hash_excludes_itself_and_is_deterministic(tmp_path):
    path = _ledger(tmp_path)
    entry = ledger.append(path, {"input_hash": "a"}, "fetch", "op")
    recomputed = ledger.compute_entry_hash(entry)
    assert recomputed == entry["entry_hash"]


def _export_record():
    return {
        "policy_name": "tlc",
        "policy_version": 1,
        "policy_hash": "f" * 64,
        "output_kind": "row_level",
        "source": "dev",
        "generated_utc": "2026-04-01T00:00:00+00:00",
        "gate": {"health_score": 99.99, "refused": False},
        "salt_fingerprint": "abc123",
        "output_path": "outputs/exports/tlc_dev.parquet",
        "output_hash": "d" * 64,
        "rows_in": 100,
        "rows_out": 100,
        "cells_suppressed": 0,
        "k_achieved": None,
        "columns_shared": ["a", "b"],
        "columns_withheld": ["c"],
        "transforms": [{"op": "pseudonymize", "columns": ["a"]}],
        "refused": False,
        "reason": None,
    }


def test_methodology_report_regenerates_byte_identical(tmp_path):
    path = _ledger(tmp_path)
    entry = ledger.append(path, _export_record(), "export", "op")
    # The report at write time and the report regenerated from the persisted entry
    # must be byte-identical (the renderer is a pure function of the entry).
    at_write = report.render_markdown(entry)
    persisted = ledger.read_entries(path)[0]
    regenerated = report.render_markdown(persisted)
    assert regenerated == at_write
    assert "tlc" in regenerated and "pseudonymize" in regenerated
