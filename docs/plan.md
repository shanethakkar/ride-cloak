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
- **Last completed:** **Phase 4** (2026-06-09) — export profiles: declarative YAML policies +
  pydantic schema + compiler + runner with two fail-closed gates (validation, approval). Three
  profiles run end to end: TLC (250K rows, 10 IDs pseudonymized, 15-min, notes redacted), MDS
  (borough×60-min k=5; full month retains 99.95% of rows in ~2s), LE (fails closed without
  approval). Toy 4th policy exports with zero code. `pytest` (77 passed), ruff green.
  See [findings/phase-4.md](findings/phase-4.md).
- **Phases completed:** 0, 1, 2, 3, 4.
- **Next step:** Begin **Phase 5** — attestation ledger: append-only hash-chained JSONL with the
  SPEC §7 entry schema; every pipeline command appends an entry; `ridecloak verify-ledger` walks
  the chain; methodology report regenerates byte-identically from a ledger entry. The Phase 4
  runner audit dict is already shaped as the ledger payload.
- **Open escalations:** [decisions.md](decisions.md) D-0003 (k → Phase 3, buckets → Phase 4,
  extra months → Shane). Month locked: 2026-04 (D-0004).
- **Naming note:** CLI is `ridecloak` ([decisions.md](decisions.md) D-0001). SPEC examples that
  say `safeharbor` translate to `ridecloak`.
- **Setup note:** Presidio needs the spaCy model — `uv run python -m spacy download
  en_core_web_lg` (not a pinned dependency).

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

### ☑ Phase 2 — Classification & PII detection  (done 2026-06-09)

**Result: overall precision 0.997, recall 0.998 (targets 0.90/0.95 met). 51 tests pass.**
Findings: [findings/phase-2.md](findings/phase-2.md). Design below (decisions D-0007).

Deps to add: `presidio-analyzer`, `spacy`; download `en_core_web_lg` (~560MB,
`uv run python -m spacy download en_core_web_lg`). (`presidio-anonymizer` waits for Phase 3.)

Step A — **extend the synthetic layer** (revises Phase 0 per D-0007): move the license/plate/VIN
value generators into `pipeline/synth/identifiers.py` (shared by generator + templates, no
import cycle); add support-note templates embedding `TLC_LICENSE`, `NY_PLATE`, `VEHICLE_VIN`
with context words ("TLC license", "plate", "VIN") so context-aware recognizers can hit them
precisely. Re-run `ridecloak synth --input dev` (dev-slice hash changes; determinism holds).
Phase 0/1 tests remain green (validation ignores synth columns; synth tests are structural).

Modules under `pipeline/classify/`:
- **`dictionary.py`** — pydantic models (Tier enum: direct/quasi/sensitive/safe; `ColumnClass`;
  `ClassificationDict`) that load + validate **`config/classification.yaml`** (versioned). Tiers
  for every dev-slice column (25 real + synth + trip_id):
  - direct: trip_id, driver_license_num, driver_name, vehicle_plate, vehicle_vin, rider_id,
    rider_phone, rider_email, payment_token, device_id
  - quasi: request/on_scene/pickup/dropoff_datetime, PULocationID, DOLocationID, trip_miles,
    trip_time
  - sensitive: support_note, access_a_ride_flag, wav_request_flag, wav_match_flag (D-0007)
  - safe: hvfhs_license_num, dispatching/originating_base_num, all money fields,
    shared_request_flag, shared_match_flag
- **`recognizers.py`** — context-aware `PatternRecognizer`s: `TLC_LICENSE` (6–7 digit + context),
  `NY_PLATE` (`[A-Z]{3}-?\d{4}`), `VEHICLE_VIN` (17 alnum excl. I/O/Q + context). Context words
  are the precision lever against decoy numerics (trip ids, fares).
- **`pii_scan.py`** — build `AnalyzerEngine` (spaCy lg) + register custom recognizers; scan a
  series of `support_note` texts → detections (entity_type, start, end, score); score threshold
  is a tunable param. Scans free text only; structured columns are dictionary-classified.
- **`evaluate.py`** — greedy one-to-one matcher: a detection is a TP if it **overlaps** a label
  of **compatible type** (D-0007); compute per-entity + overall precision/recall/F1. Includes
  decoy notes so false positives are penalized.

CLI **`ridecloak classify --input dev`**: assert every column is classified (else fail);
scan notes; evaluate vs `labels.parquet`; write `outputs/reports/classification_dev.{json,md}`
+ Rich per-entity table; report PASS/FAIL vs the 0.95/0.90 targets.

Tuning loop (documented in findings): baseline lg + defaults → measure per-entity P/R → close
gaps (numeric license precision via context; address-without-suffix LOCATION recall; dotted
phone formats) by tuning recognizers/context/thresholds → re-measure until targets met.

Tests (`test_recognizers.py`, `test_classify.py`): custom recognizers fire on context strings
and ignore decoy numerics; `evaluate` returns correct P/R/F1 on synthetic detections (overlap,
type-mismatch, partial-overlap cases); **every dev-slice column appears in classification.yaml**
(SPEC acceptance); skippable integration test runs full classify and asserts recall ≥ 0.95,
precision ≥ 0.90.

**Accept when:** `ridecloak classify --input dev` writes a per-entity precision/recall report;
recall ≥ 0.95 and precision ≥ 0.90 on labeled spans (tuning documented in findings); a test
enforces no unclassified columns.
**Decided:** extend synth & measure custom recognizers; `en_core_web_lg`; disability flags
sensitive; overlap+type match (all D-0007).

### ☑ Phase 3 — Transform engine  (done 2026-06-09)

**Result: full-month uniqueness 90.1%→0.06% (zone→borough); zone-level k=5 suppresses 85%,
borough×15min 0.26%. 64 tests pass.** Findings: [findings/phase-3.md](findings/phase-3.md).
Design below (decisions D-0008). Default k=5; generalization is the main lever.

Modules under `pipeline/transform/` (pure core: DataFrame in → DataFrame + audit-dict out):
- **`suppress.py`** — drop columns (whole-field suppression) and **redact spans**: mask the
  Presidio-detected PII spans in `support_note` in place (consumes Phase 2 `pii_scan`
  detections), keeping non-PII text. Returns redacted text + count of spans masked.
- **`pseudonymize.py`** — salted SHA-256 over a column/value. `generate_salt()` (per export run),
  `salt_fingerprint()` = SHA-256 of the salt; `pseudonymize(series, salt)` → hex digest
  (truncation length a param, default 16 hex). Same salt → same pseudonyms; different → disjoint.
  Salt I/O (write to `secrets/salts/`) lives in the I/O layer, not here.
- **`generalize.py`** — `round_time(series, minutes)` (floor to N-min bucket) and
  `rollup_zone(series, lookup)` (zone → borough via the taxi-zone lookup). Both pure.
- **`kanon.py`** — `equivalence_sizes(df, qi)` (pandas groupby, dev), `suppress_below_k(df, qi, k)`
  (drop rows in classes < k; audit: rows_in, rows_out, cells_suppressed, k_achieved),
  `uniqueness(df, qi)` (share of rows in size-1 classes). Plus `kanon_sql(view, qi, k)` /
  `uniqueness_sql(view, qi)` — pure SQL builders so the **full-month run computes
  equivalence classes in DuckDB without loading parquet into pandas** (mirrors the Phase 1
  dual-path pattern).

CLI **`ridecloak risk --input <dev|month> [--qi ...] [--bucket-min 15]`**: default QI =
`PULocationID × DOLocationID × pickup-bucket` (D-0008). Reports the **uniqueness ladder** —
minute → 15-min → 60-min → borough×borough — plus k-suppression cost at k, before/after. Dev
path uses pandas; month path uses the DuckDB SQL builders (scale-safe). Writes
`outputs/reports/risk_<input>.{json,md}` + Rich summary. The honest core result: zone-level data
is ~97% unique and k-anon suppresses ~100% there; borough rollup makes it viable.

Profiled reference numbers (dev slice, for the report/tests): minute 99.8% / 15-min 97.1% /
60-min 90.4% / borough×borough×15-min 5.4% unique; borough k=5 suppression ~23% (15-min) /
~4.7% (60-min).

Tests (`test_transform.py`, `test_kanon.py`): each transform pure with hand-crafted fixtures —
**a fixture where exactly one known cell falls below k**; same-salt-same-pseudonym /
different-salt-disjoint; round_time floors correctly; zone→borough maps via lookup; redaction
masks the right offsets; uniqueness computed correctly before/after; SQL builders parse and
match the pandas path on a small fixture.

**Accept when:** all transforms are pure with unit tests (incl. the exactly-one-below-k
fixture); same salt = same pseudonyms, different salt = disjoint; `ridecloak risk --input dev`
prints before/after uniqueness at minute-level vs bucketed; full-month run completes without
loading raw parquet into pandas.
**Decided (D-0008):** k=5 default; raw-zone default QI with full ladder; redact support_note
spans; record-drop suppression; salted-SHA-256 + per-export salt fingerprint.

### ☑ Phase 4 — Export profiles  (done 2026-06-09)

**Result: 3 profiles + toy 4th export from YAML (zero code); LE fails closed; MDS month retains
99.95% in ~2s. 77 tests pass.** Findings: [findings/phase-4.md](findings/phase-4.md).
Design below (decisions D-0009). Declarative YAML policies compose Phase 3.

`policies/` (3 YAML + schema):
- **`schema.py`** — pydantic `Policy`: `name`, `version`, `description`, `output_kind`
  (`row_level` | `aggregate`), `requires_approval`, and a block per kind:
  - row_level: `pseudonymize_columns`, `time_bucket_minutes`, `rollup_zone` (bool),
    `redact_note` (bool), `drop_columns`, `select_columns` (whitelist | null), `kanon`
    (`{qi, k}` | null).
  - aggregate: `dimensions` (e.g. `[PUBorough, DOBorough, pickup_bucket]`),
    `time_bucket_minutes`, `k`. Validates on load; a malformed policy fails fast.
- **`tlc_trip_submission.yaml`** — row-level; pseudonymize the 10 direct-id columns; 15-min
  pickup rounding; `redact_note`; keep zone; full fares; no kanon.
- **`mds_aggregate.yaml`** — aggregate; borough×borough×60-min counts; k=5.
- **`law_enforcement_extract.yaml`** — row-level; minimal `select_columns`; pseudonymized trip
  key + zone/time; `requires_approval: true`.

`pipeline/export/`:
- **`profiles.py`** — compiler: `Policy` → ordered transform plan. Row-level order: redact_note →
  pseudonymize → generalize time → rollup zone → drop → kanon suppress → select. Aggregate:
  build dims (time bucket + borough rollup) → group-count → small-cell-suppress (k).
- **`runner.py`** — execute the plan on the input; **fail closed** if the Phase 1 validation gate
  is REFUSED or (LE) the approval is absent; generate a per-export salt (store via
  `io/salts.py`, fingerprint into the audit); write the export to `outputs/exports/` (parquet
  row-level, CSV aggregate); emit a **methodology report** + an audit dict carrying the Phase 5
  ledger fields (rows_in/out, cells_suppressed, k_achieved, salt_fingerprint, transforms,
  policy_name/version/hash, input_hash, output_hash).
- **`report.py`** — render the methodology report (what was shared, withheld, why, under which
  policy version) from the audit; the same function regenerates from a ledger entry in Phase 5.

`pipeline/io/approvals.py` + **`ridecloak approve --request-id <id>`** (human-only, SPEC §13)
writes an approval record under `outputs/approvals/`. **`ridecloak export --profile <tlc|mds|le>
--input <dev|month> [--approval <id>]`** runs the profile. Row-level profiles are dev-scoped (the
synth identity layer only exists there); MDS aggregate also supports `--input month` via SQL.

Tests (`test_policies.py`, `test_export`): policy schema loads/validates all three; compiler
produces the expected ordered plan; each profile exports a file + report on dev; **a toy 4th
policy YAML exports with zero code changes**; **LE without approval fails closed** with a logged
refusal; LE **with** a fixture-written approval produces a file (happy path); pseudonymized
columns are unrecoverable + salt fingerprint recorded; MDS cells below k are suppressed.

**Accept when:** all three exports produce files + methodology reports from one command each;
adding a toy fourth policy needs zero code changes (test); LE without approval fails closed with
a logged refusal. (Claude does not run `approve`; committed LE artifact is the refusal.)
**Decided (D-0009):** TLC 15-min row-level no-k; MDS borough×60-min k=5; LE minimal+approval;
declarative policy language.

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
