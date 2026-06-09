# Plan & Roadmap

**Role of this file.** The living execution roadmap. SPEC §7 is the immutable original phase
plan; this file tracks *current status* against it, the next concrete step, and any deviations.
When the plan and the SPEC disagree because reality intervened, this file records the deviation
and the reason (and a matching `decisions.md` entry).

**How and when to update.** At the end of every working session, update the Current State block
and tick any acceptance criteria met. When a phase completes, mark it done, link its
`docs/findings/phase-N.md`, and advance Current State to the next phase. Keep checkboxes honest
— only tick what is actually verified (`pytest` + `ruff` green, CLI run on dev slice).

---

## Current State
- **Last completed:** **Phase 1** (2026-06-09) — two-tier validation gate (Pandera Tier-1 +
  equal-weighted 0–100 health score), dev + scale-safe month paths. Clean 2026-04 scores 99.99
  (dev and full 15.4M-row month, the latter in 5.5s via DuckDB single-pass, no pandas);
  corrupted fixture scores 78.83 and is refused. `pytest` (30 passed) and `ruff` green.
  See [findings/phase-1.md](findings/phase-1.md).
- **Phases completed:** 0, 1.
- **Next step:** Begin **Phase 2** — `classification.yaml` tiering every column; Presidio over
  `support_note` + custom recognizers (TLC license, NY plate, VIN); precision/recall/F1 vs the
  `labels.parquet` ground truth (target recall ≥ 0.95, precision ≥ 0.90).
- **Open escalations:** [decisions.md](decisions.md) D-0003 (k → Phase 3, buckets → Phase 4,
  extra months → Shane). Month locked: 2026-04 (D-0004). spaCy model choice → Phase 2.
- **Naming note:** CLI is `ridecloak` ([decisions.md](decisions.md) D-0001). SPEC examples that
  say `safeharbor` translate to `ridecloak`.

---

## Workflow per phase (SPEC §7)
implement → `pytest` + `ruff check` green → run the phase CLI command on the dev slice →
write `docs/findings/phase-N.md` (~300–800 words) → commit `Phase N: <summary>`.
A phase is **done** only when all of the above pass and its acceptance criteria are met.

---

## Phase roadmap

Legend: ☐ not started · ◐ in progress · ☑ done

### ☑ Phase 0 — Scaffold, ingest, synthetic layer  (done 2026-06-09)
Built: repo skeleton, uv env, `ridecloak fetch --month YYYY-MM`, manifest cache, schema
introspection, Uber filter, synthetic generator + labels, dev slice.
**Accepted:** 2026-04 cached with manifest + SHA-256; 25-column schema recorded (no drift);
`dev_slice.parquet` = 250K rows, reproducible (same seed = same hash, verified); labels
re-extract byte-for-byte by offset; decoy notes have zero spans. All criteria met; 13 tests
pass. Findings: [findings/phase-0.md](findings/phase-0.md).
**Decided:** first month = 2026-04 (D-0004); `labels.parquet` not committed (D-0005).

### ☑ Phase 1 — Validation gate  (done 2026-06-09)

**Design (decisions D-0006). Two-tier gate, equal-weighted score.**

Step 0 — calibration (do first): read-only **full-month** (~21M row) profile in DuckDB of
null rates, value ranges, and negative/zero money shares, to set the contract's nullable flags
and per-column null-rate thresholds (the 250K sample showed 0 nulls — too optimistic). Record
the profile in `docs/findings/phase-1.md`.

Modules under `pipeline/validate/` (pure core: DataFrame in → DataFrame/audit-dict out):
- **`contract.py` — Tier 1 (hard).** Pandera `DataFrameSchema` for the 25 real HVFHV columns,
  built from `data/raw/manifests/schema_2026-04.json` + the profile: dtypes; domains
  (`PULocationID`/`DOLocationID` ∈ lookup 1–265, `trip_time ≥ 0`, datetimes parse, license/flag
  value sets); nullability per the profile. Any violation ⇒ validation fails outright.
- **`checks.py` — Tier 2 (soft), statistical/cross-field.** Each returns an audit record
  (rule, rows_failed, fail_rate): `dropoff ≥ pickup`; `abs(trip_time − (dropoff−pickup)) ≤ 60s`;
  money non-negative **per field** (negatives ding validity, not hard-fail — real data has 89);
  zero-distance-with-positive-fare sanity; duplicate full-row detection; per-column null-rate vs
  threshold.
- **`health.py` — 0–100 score.** Four dimensions, **25 pts each (equal)**:
  completeness (null-rate adherence), validity (per-row value rules), consistency (cross-field
  rules), uniqueness (1 − duplicate-row share). Each dimension subscore = `100·(1 − fail_rate)`
  (or threshold-adherence for completeness); composite = mean. Configurable `gate_threshold`
  (default 90, already in settings) → `refused` boolean.

Operates on the **25 real columns only**; synth PII columns are Phase 2's concern. Ledger entry
deferred to Phase 5 — for now `validate` writes a JSON artifact + human-readable report to
`outputs/reports/validation_<input>.json|.md` (idempotent, fixed name per input) and prints a
Rich per-dimension summary with PASS/REFUSE.

Testing: per-check unit tests on tiny hand-crafted fixtures (clean passes, each bad fixture
fires its rule); a `corrupt_slice()` helper injects nulls/negatives/`dropoff<pickup`/
out-of-range zones/duplicates, and a test asserts the score drops measurably below threshold and
the gate refuses.

**Accept when:** `ridecloak validate --input dev` emits JSON + human-readable report and PASSES
clean 2026-04 (score ≥ 90); each check fires on a crafted bad fixture and passes on a clean one;
the corrupted slice scores measurably lower and is refused; full-month profile recorded in
findings.

**Status: ☑ done (2026-06-09).** Clean dev + full month score 99.99 (PASS); corrupted fixture
78.83 (REFUSED); month path validates 15.4M rows in 5.5s with no pandas load; 30 tests pass.
Findings: [findings/phase-1.md](findings/phase-1.md).

### ☐ Phase 2 — Classification & PII detection  (est. 2–3 days)
Build: `classification.yaml` tiering every column direct/quasi/sensitive/safe; Presidio over
`support_note`; custom recognizers (TLC license, NY plate, VIN); evaluation harness computing
precision/recall/F1 per entity vs ground truth.
**Accept when:** `ridecloak classify --input dev` writes a detection report with per-entity
precision/recall; **recall ≥ 0.95 and precision ≥ 0.90** on labeled spans (tune + document in
findings); a test enforces every schema column appears in `classification.yaml`.
**Decides:** spaCy model (`en_core_web_lg` vs `_sm` fallback).

### ☐ Phase 3 — Transform engine  (est. 3 days)
Build: suppression; salted SHA-256 pseudonymization (per-export salt + ledger fingerprint);
temporal rounding (param: minutes); spatial rollup zone→borough (param); k-anonymity over a
configurable QI tuple (default `PULocationID × DOLocationID × pickup bucket`) with
equivalence-class computation in DuckDB SQL and small-cell suppression below k; uniqueness
metric (share of size-1 classes) before and after.
**Accept when:** all transforms are pure functions with unit tests on hand-crafted fixtures
(incl. a fixture where exactly one known cell falls below k); same salt = same pseudonyms,
different salt = disjoint (test); `ridecloak risk --input dev` prints before/after uniqueness at
minute-level vs bucketed; full-month run completes without loading raw parquet into pandas.
**Decides:** final k (default 5).

### ☐ Phase 4 — Export profiles  (est. 2 days)
Build: three YAML policies — TLC trip submission (row-level, pseudonymized, 15-min rounding,
full fare fields, HVFHV-matched schema); MDS aggregate (zone × time-bucket counts, k-suppressed);
law-enforcement extract (trip-scoped, minimal fields, requires approval record); pydantic policy
schema; compiler policy → ordered transform plan; runner that refuses if the certification gate
failed or (LE) approval is absent.
**Accept when:** all three exports produce files + methodology reports from one command each
(`ridecloak export --profile tlc --input dev`); adding a toy fourth policy file needs zero code
changes (test proves it); LE profile without approval fails closed with a logged refusal.
**Decides:** TLC 15-min / MDS 60-min buckets.

### ☐ Phase 5 — Attestation ledger  (est. 2 days)
Build: append-only JSONL ledger with the SPEC §7 entry schema; `entry_hash =
sha256(canonical_json(entry − entry_hash))` chained via `prev_entry_hash`;
`ridecloak verify-ledger` walks the chain; methodology report generator pulls from the ledger
entry (what shared, withheld, why, which policy version).
**Accept when:** every pipeline command appends an entry; verify passes on an intact ledger; a
test mutating a historical entry makes verify report the exact break point; the methodology
report regenerates byte-identical from the same entry.

### ☐ Phase 6 — AI triage agent with guardrails  (est. 2–3 days, needs `ANTHROPIC_API_KEY`)
Build: `ridecloak triage --request "<text>"`; Claude parses request → `{requester, scope,
fields, window, claimed_legal_basis}`; deterministic guardrail layer maps fields against
`classification.yaml` + policies, flags out-of-policy asks; drafts response plan; queues approval
record; second Presidio pass over drafted content; every prompt/response hashed into the ledger.
**The agent has no code path to `runner.py` — enforced by architecture, not prompts.**
**Accept when:** ≥ 10 canned requests (in-policy, out-of-policy, ambiguous, prompt-injection)
produce correct decisions; out-of-scope + injection fail closed; grep proves the agent module
never imports the export runner; all agent interactions appear in the ledger.
**Optional 6b:** Streamlit approval console — **cut first if behind schedule.**

### ☐ Phase 7 — Dashboard extracts  (est. 1 day agent + 1 day human)
Build (agent): `ridecloak dashboard-extract` emitting tidy CSVs from ledger + reports (requests
by status/profile/month, turnaround, health-score trend, suppression rates, k achieved,
before/after uniqueness, PII detection metrics).
Human (Shane): build + publish the Tableau Public dashboard. **Claude Code does not attempt
Tableau; do not substitute React.**
**Accept when:** CSVs load into Tableau without manual cleaning; every metric traces to a ledger
field.

### ☐ Phase 8 — Ship  (est. 2–3 days, mostly human)
README (recruiter intro, honest-scope statement, reproduce instructions), `reproduce.ps1/.sh`
(fetch → synth → validate → classify → risk → all three exports → verify-ledger), article on
shanethakkar.com (opens on the LADOT lawsuit), matplotlib figures, repo public.
**Accept when:** fresh clone + reproduce script completes end-to-end on one month; README
contains zero unearned claims.

---

## Cut order if time-constrained (SPEC §7)
1. 6b Streamlit console. 2. LE profile → a stub.
**Never cut:** labeled-PII evaluation, before/after re-identification metric, Tableau dashboard.

## Human-only tasks (do not attempt — SPEC §13)
Tableau build/publish; article drafting/publishing; `ridecloak approve` invocations; Anthropic
API key provisioning; final decisions on k / buckets / months; making the repo public.
