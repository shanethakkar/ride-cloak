# Phase 4 findings — Export profiles

**Status:** complete. `pytest` (77 passed) and `ruff` green; all three profiles run end to end
on dev, MDS also on the full month, and the LE profile fails closed without an approval.

## What was built
- **`policies/schema.py`** — pydantic `Policy` (row_level | aggregate blocks; `requires_approval`;
  a validator that rejects a kind/block mismatch) + `policy_hash`. Three policy YAMLs:
  `tlc_trip_submission`, `mds_aggregate`, `law_enforcement_extract`.
- **`pipeline/export/profiles.py`** — compiler turning a policy into an ordered transform plan
  (row-level order: redact → pseudonymize → generalize → rollup → drop → kanon → select).
- **`pipeline/export/runner.py`** — executes the plan; **two fail-closed gates** (validation
  certification, then approval for gated profiles); generates a per-export salt (stored under
  `secrets/salts/`, fingerprint in the audit); writes the export (parquet row-level, CSV
  aggregate) + a methodology report; returns an audit dict pre-loaded with the Phase 5 ledger
  fields (rows_in/out, cells_suppressed, k_achieved, salt_fingerprint, policy_hash, input/output
  hashes, columns shared/withheld).
- **`pipeline/export/report.py`** — renders the methodology report (what shared, withheld, why,
  under which policy version) deterministically from the audit, so Phase 5 can regenerate it.
- **`pipeline/io/approvals.py`** + **`ridecloak approve`** (human-only, SPEC §13) and
  **`ridecloak export --profile <tlc|mds|le> --input <dev|month> [--approval]`**.

## Results (one command each)
- **TLC (dev):** 250,000 rows; 10 direct identifiers pseudonymized (salted SHA-256, fingerprint
  `f10ddfdccf2bba71`), pickup/dropoff floored to 15 min, support-note PII redacted to
  `[REDACTED]` (Phase 2 detector feeds the redaction), zone-level location + full fares kept.
- **MDS (dev):** 250,000 rows → 238,153 represented; 5,988 borough×borough×60-min cells; k=5.
- **MDS (month, 15.4M rows via DuckDB in ~2s):** 15,370,445 of 15,378,858 rows represented
  (**99.95% retained**); only 4,217 cells suppressed — the borough-level aggregate is both
  privacy-suppressed and useful, exactly the Phase 3 thesis.
- **LE (no approval):** **REFUSED — fail-closed**, no export written, refusal logged to a
  methodology report.

## Acceptance criteria — all met
1. Each profile produces an export file + methodology report from one command ✅ (LE happy path
   exercised in tests with a fixture-written approval; committed LE artifact is the refusal).
2. A toy fourth policy exports with **zero code changes** ✅ (test builds a new `Policy` and runs it).
3. LE without approval **fails closed with a logged refusal** ✅. 77 tests pass, ruff clean.

## Decisions / notes (D-0009)
- TLC 15-min row-level pseudonymized, no k; MDS borough×60-min k=5; LE minimal + approval.
- **Row-level exports (TLC, LE) are dev-scoped** — the synthetic identity layer only exists on
  the dev slice. MDS aggregate needs no PII and runs on the full month via SQL.
- **SPEC §13 honored:** Claude never runs `ridecloak approve`. The committed LE showcase is the
  fail-closed refusal; the with-approval happy path lives in tests. Shane runs `approve` for a
  real LE export.
- The runner's audit dict is deliberately shaped to be the Phase 5 ledger entry payload.

## Open questions for later phases
- Phase 5: append each export's audit to the hash-chained ledger; the methodology report then
  regenerates byte-identically from the ledger entry (the renderer is already a pure function of
  the audit, so this is a clean handoff).
