# Phase 5 findings — Attestation ledger

**Status:** complete. `pytest` (82 passed) and `ruff` green; a full pipeline run produces an
8-entry hash chain and `ridecloak verify-ledger` confirms it intact.

## What was built
- **`pipeline/attest/ledger.py`** — append-only JSONL at `outputs/ledger/ledger.jsonl`.
  - Entry = flat dict: envelope (`seq`, `timestamp_utc`, `run_id`, `command`, `operator`,
    `prev_entry_hash`, `entry_hash`) + the command's record. For an export the record is the full
    Phase 4 audit; for other commands it is provenance hashes + a `metrics` summary.
  - `entry_hash = sha256(canonical_json(entry − entry_hash))`, chained via `prev_entry_hash`
    (genesis `"0"*64`). `append`, `read_entries`, `verify` (recompute every hash, check the
    linkage, return the **exact break seq**).
- **`pipeline/attest/report.py`** — the methodology report generator, relocated here from
  `export/`. It reads only audit fields, so it renders identically from the in-memory audit or
  the persisted ledger entry. The export runner now **appends the entry, then renders the report
  from the entry** — making byte-identical regeneration structural.
- **Settings:** `operator = "ridecloak-pipeline"` (env `RIDECLOAK_OPERATOR`).
- **Wiring:** `ledger.append` added to every command (fetch, synth, validate, classify, risk,
  export, approve); new **`ridecloak verify-ledger`** (exit non-zero on a broken chain).

## Demonstrated chain (one full pipeline run)
```
seq=0 fetch     prev=000000000000
seq=1 synth     prev=<fetch hash>
seq=2 validate  prev=<synth hash>
seq=3 classify  prev=<validate hash>
seq=4 risk      prev=<classify hash>
seq=5 export    (tlc)  prev=<risk hash>
seq=6 export    (mds)  prev=<tlc hash>
seq=7 export    (le, refused)  prev=<mds hash>
```
`verify-ledger` → "Ledger intact — 8 entries verified". One unbroken provenance chain from ingest
to release, including the fail-closed LE refusal.

## Acceptance criteria — all met
1. Every pipeline command appends an entry ✅ (8-entry chain above).
2. Verify passes on an intact ledger ✅.
3. Mutating a historical entry makes verify report the **exact break seq** ✅ (test tampers seq 1
   and verify returns `break_seq=1`, reason "entry was mutated").
4. The methodology report regenerates **byte-identical** from the same ledger entry ✅ (test).
   82 tests pass, ruff clean.

## Decisions / notes (D-0010)
- Every command chained; operator is the generic `ridecloak-pipeline`; the entry embeds the full
  export audit (superset of the SPEC §7 fields) so the report regenerates and the whole entry is
  hash-protected.
- **The ledger is the one deliberately non-idempotent artifact** (append-only). The committed
  `ledger.jsonl` is a snapshot of one canonical run; the reproduce script truncates it first.
- Refactor: the methodology renderer moved `export/report.py` → `attest/report.py`; the runner
  and the MDS-month path import it from there. No behavior change.

## Open questions for later phases
- Phase 6: the triage agent hashes every prompt/response into this ledger; the guardrail layer
  has no code path to `runner.py` (a grep test will enforce it).
- Phase 7: dashboard extracts read ledger fields (command, policy_name, rows_in/out,
  cells_suppressed, k_achieved, timestamps) — all present per entry.
