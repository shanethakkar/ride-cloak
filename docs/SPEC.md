# SafeHarbor — Privacy-Safe Regulated Trip-Data Sharing Pipeline
## Build Sheet v2 — Agent-Ready Specification for Claude Code

**Target role:** Uber Data Scientist I, DESS team, Dallas TX
**Owner:** Shane Thakkar
**Status:** Spec complete, not started
**This document is the project's source of truth. Claude Code: read it in full before writing any code. Section 2 contains your operating rules.**

---

# 1. MISSION AND CONTEXT

## Why this project exists
Built to target Uber's DESS team, whose JD centers on: pipelines for external data sharing under legal/regulatory mandates, automated compliance dashboards, refactoring manual reporting into auditable integrations, rigorous data validation, and AI enablement with security guardrails.

Two researched facts anchor the narrative:
1. **Uber sued LADOT in March 2020** over the Mobility Data Specification, arguing mandated trip-level location sharing amounted to rider surveillance. LADOT suspended JUMP's permit over non-compliance; Uber lost the appeal and eventually complied. The unresolved tension: regulators have a legitimate claim to trip data, riders to privacy, and the pipeline in the middle is where that tension gets resolved.
2. **Uber submits trip records to NYC TLC biweekly via SFTP today** under the High-Volume For-Hire Services rules, Local Law 149 of 2018. The public HVFHV dataset is the *output* of exactly this kind of pipeline.

**The system:** ingest raw trip data carrying a synthetic PII layer, validate it against a contract, classify every field, quantify re-identification risk, apply policy-driven privacy transforms, emit regulator-ready exports, and record every transformation in a tamper-evident hash-chained ledger. An AI triage agent maps free-text regulator requests to sharing policies under hard guardrails: draft-only authority, fail-closed scope checks, mandatory human approval.

## Pipeline shape
```
ingest → validate → classify → transform → export → attest
```

## JD coverage map
| JD requirement | SafeHarbor component |
|---|---|
| Pipelines for external data sharing under legal/regulatory mandates | Core pipeline; TLC-style and MDS-style export profiles |
| Automated dashboards for compliance metrics for executives | Tableau Public dashboard fed by ledger extracts (human task, agent preps data) |
| Refactor manual reporting into scalable integrations | Declarative YAML sharing policies; new regulator = new YAML, zero code |
| Rigorous data validation and auditing | Pandera certification gate + hash-chained audit ledger |
| AI enablement with security and guardrails | Claude triage agent, draft-only, human-in-the-loop, fail-closed |
| SQL on large-scale databases | DuckDB analytical SQL over ~20M trips/month |
| GDPR/CCPA familiarity | Classification tiers, pseudonymization, k-anonymity, salt-destruction erasure story |
| Documented, auditable analysis | Auto-generated methodology report per export |

---

# 2. AGENT OPERATING RULES (Claude Code: these are binding)

## Code style
- Python 3.12. Type hints on all public functions. Docstrings stating purpose, inputs, outputs.
- **No emojis anywhere. No AI-sounding comments** ("Let's now...", "Great!", "# Here we simply..."). Write production-grade comments that explain *why*, not *what*.
- `pathlib` for all paths. Resolve project root from file location so scripts run from anywhere.
- **Pure-function core:** everything in `pipeline/validate/`, `pipeline/classify/`, `pipeline/transform/` takes DataFrames (or Arrow tables) in and returns DataFrames plus an audit-record dict out. No file or DB I/O inside math/transform modules. I/O lives only in `pipeline/io/` and the CLI layer.
- All file-producing operations are **idempotent**: re-running overwrites cleanly, never duplicates.
- `ruff` for lint + format. `pytest` for tests. Both must pass before any phase is considered done.

## Scale guardrails
- Monthly HVFHV Parquet files contain roughly 17–20M rows. **Never `pd.read_parquet` a full monthly file into pandas.** Use DuckDB to query Parquet directly and pull only filtered/aggregated results into pandas.
- During development, work against a sampled dev slice (see Section 5.4). Full-month runs only at phase verification.

## Secrets and config
- `pydantic-settings` + `.env` for config. `.env` is gitignored; commit `.env.example` with placeholder keys.
- `ANTHROPIC_API_KEY` required only for Phase 6. Never hardcode. Never log it.
- Salts for pseudonymization are generated per export run, stored only in `secrets/salts/` (gitignored), referenced in the ledger by salt fingerprint (SHA-256 of the salt), never by value.

## Git discipline
- One commit per completed phase minimum, message format: `Phase N: <summary>` (EdgarRisk convention).
- `.gitignore`: `data/raw/`, `data/dev/`, `secrets/`, `.env`, `outputs/exports/` (large generated files). Commit manifests, configs, policies, reports, and ledger.
- Synthetic-data generator and its seed ARE committed; generated synthetic data is reproducible, so it is not.

## Decisions you MUST escalate to Shane (do not decide alone)
1. Final k threshold for k-anonymity (build it as a policy parameter; default k=5 for dev)
2. Time-bucket sizes per export profile (defaults: 15 min TLC profile, 60 min MDS profile)
3. Which months of data beyond the first dev month
4. Any dependency outside the approved stack in Section 4
5. Anything requiring a paid service
6. Renaming the project (current working name: SafeHarbor)

## Definition of done, per phase
A phase is done only when: acceptance criteria in Section 7 pass, `pytest` passes, `ruff check` passes, the phase's CLI command runs end-to-end on the dev slice, and a phase findings note exists at `docs/findings/phase-N.md` (~300–800 words: what was built, decisions made, metrics observed, open questions). The findings notes are raw material for the article.

## Honesty rules (project brand, non-negotiable)
- The synthetic PII layer must be labeled synthetic in every artifact: README, docstrings, reports, article. Never imply real rider PII was handled. Correct framing: "reconstructed the pre-anonymization input to demonstrate the transform."
- Document limitations in-place: k-anonymity's known weaknesses (homogeneity attacks, background knowledge), Presidio's non-guarantee of total recall, the gap between this demo and production SFTP/auth infrastructure.

---

# 3. ENVIRONMENT

- **OS:** Windows 11, PowerShell primary shell. Provide PowerShell commands first; Bash equivalents in `scripts/` for portability.
- **Python:** 3.12 via **uv** (Astral). `uv init`, `uv add`, pinned `uv.lock` committed.
- **Project root:** `C:\Users\shane\Projects\SafeHarbor`
- Presidio requires a spaCy model: `uv run python -m spacy download en_core_web_lg` (document in README; fall back to `en_core_web_sm` if download size is a problem on first run, escalate if accuracy suffers).

# 4. APPROVED STACK

| Concern | Tool | Notes |
|---|---|---|
| Env/deps | uv | EdgarRisk toolchain |
| Tabular/SQL at scale | **DuckDB** | Query Parquet in place; SQL is a JD basic qual, write real analytical SQL |
| DataFrames | pandas, pyarrow | Only on filtered/sampled data |
| Validation | **Pandera** | Lighter than Great Expectations, fits pure-function style |
| PII detection | **presidio-analyzer, presidio-anonymizer**, spaCy | Plus custom regex recognizers |
| Synthetic data | **Faker** + numpy seeded RNG | Deterministic, seed in config |
| Policies/config | PyYAML, pydantic, pydantic-settings | Policies validated by pydantic models on load |
| CLI | **Click** | `safeharbor` entrypoint, mirrors `nflgrades` pattern |
| CLI output | Rich | Tables, progress |
| Ledger | hashlib, JSON Lines | No blockchain theater; hash chain is sufficient |
| AI agent | **anthropic** SDK | Phase 6 only |
| Approval console | Streamlit (optional, Phase 6b) | Cut first if time-constrained |
| Plots for article | matplotlib | Risk before/after, equivalence-class distributions |
| Tests | pytest | Hand-crafted edge-case fixtures |
| Lint/format | ruff | CI-style gate |

Anything else: escalate first.

# 5. DATA SPECIFICATION

## 5.1 Real layer: NYC TLC High-Volume FHV trip records
- **Download URL pattern:** `https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_YYYY-MM.parquet`
- **Zone lookup:** `https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv` (LocationID, Borough, Zone, service_zone)
- **Verify URLs against** `https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page` at Phase 0; TLC has announced minor parquet schema standardization changes, so introspect the actual downloaded schema (`DESCRIBE` in DuckDB) and record it in the Phase 0 findings note before locking the Pandera contract.
- **Start with one month** (most recent available; TLC publishes on ~2-month delay). Cache to `data/raw/` with a manifest JSON (source URL, download date, SHA-256, row count) — ADR-0009 pattern from NFL Grades.
- **Filter:** `hvfhs_license_num = 'HV0003'` (Uber). Expect roughly 70–75% of rows.

## 5.2 Expected HVFHV schema (verify on download)
`hvfhs_license_num`, `dispatching_base_num`, `originating_base_num`, `request_datetime`, `on_scene_datetime`, `pickup_datetime`, `dropoff_datetime`, `PULocationID`, `DOLocationID`, `trip_miles`, `trip_time`, `base_passenger_fare`, `tolls`, `bcf`, `sales_tax`, `congestion_surcharge`, `airport_fee`, `tips`, `driver_pay`, `shared_request_flag`, `shared_match_flag`, `access_a_ride_flag`, `wav_request_flag`, `wav_match_flag`; 2025+ files add `cbd_congestion_fee`.

## 5.3 Synthetic PII layer (the input we must reconstruct)
The public file is the *output* of a privacy pipeline; we reconstruct the *input*. Module: `pipeline/synth/generator.py`, seeded and deterministic (config `SYNTH_SEED`, default 4242).

Join keys: generate a surrogate `trip_id` (UUID5 of row attributes, deterministic) on the real data, then attach:

| Field | Generator | Classification (ground truth) |
|---|---|---|
| driver_license_num | TLC-style 6–7 digit | direct identifier |
| driver_name | Faker | direct identifier |
| vehicle_plate | NY plate format regex | direct identifier |
| vehicle_vin | Faker VIN | direct identifier |
| rider_id | UUID4, stable per synthetic rider (Zipf-distributed trip counts so frequent riders exist) | direct identifier |
| rider_phone | Faker US phone | direct identifier |
| rider_email | Faker | direct identifier |
| payment_token | 16-hex | direct identifier |
| device_id | UUID4 | direct identifier |
| support_note | Template-based free text on ~2% of trips, seeded with names, phones, addresses, partial card numbers, plus PII-free decoys | mixed, span-labeled |

**Ground-truth labels are the point.** The generator writes `data/synth/labels.parquet`: every injected PII span with trip_id, field, entity_type, start, end, value_hash. This enables measuring Presidio precision/recall in Phase 2, which upgrades "I used Presidio" to "I measured detection at X% recall and closed the gap with custom recognizers."

Support-note templates must include hard cases: names embedded mid-sentence, phone formats with dots/spaces, addresses without "St/Ave" suffixes, and decoy numerics (trip IDs, fare amounts) that should NOT be flagged, so precision is a real test.

## 5.4 Dev slice
Phase 0 produces `data/dev/dev_slice.parquet`: deterministic 250K-row sample (DuckDB `USING SAMPLE ... REPEATABLE`) of the Uber-filtered month, with synthetic layer attached. All development and tests run against this; full-month runs are verification-only.

# 6. REPOSITORY STRUCTURE

```
SafeHarbor/
  CLAUDE.md                  # agent guide: distilled rules from Section 2 + workflow commands
  README.md                  # recruiter-facing intro (Phase 8)
  pyproject.toml / uv.lock
  .env.example
  .gitignore
  config/
    settings.py              # pydantic-settings
    classification.yaml      # versioned field classification dictionary (Phase 2 output)
  policies/
    tlc_trip_submission.yaml
    mds_aggregate.yaml
    law_enforcement_extract.yaml
    schema.py                # pydantic models that validate policy files on load
  pipeline/
    io/                      # ALL file/DB I/O lives here
      fetch.py               # TLC download + manifest cache
      duck.py                # DuckDB connection + query helpers
      readers.py / writers.py
    synth/
      generator.py           # seeded synthetic PII layer + span labels
      templates.py           # support-note templates incl. hard cases and decoys
    validate/
      contract.py            # Pandera schema
      checks.py              # cross-field checks (fare arithmetic, temporal sanity)
      health.py              # 0-100 certification score: completeness/validity/consistency/uniqueness
    classify/
      dictionary.py          # loads classification.yaml, tier enums
      pii_scan.py            # Presidio engine wiring + custom recognizers
      recognizers.py         # TLC license, NY plate, VIN regex recognizers
      evaluate.py            # precision/recall vs labels.parquet
    transform/
      suppress.py
      pseudonymize.py        # salted SHA-256, salt rotation per export
      generalize.py          # temporal rounding, spatial rollup
      kanon.py               # equivalence classes, small-cell suppression, uniqueness metric
    export/
      profiles.py            # policy -> transform plan compiler
      runner.py              # executes plan, emits export + methodology report
    attest/
      ledger.py              # hash-chained JSONL append + verify
      report.py              # per-export methodology report generator
    agent/
      triage.py              # Claude request parser/mapper (Phase 6)
      guardrails.py          # scope checks, fail-closed logic, output PII re-scan
      approval.py            # approval queue records
  cli.py                     # Click entrypoint `safeharbor`
  data/
    raw/        (gitignored) # downloaded parquet + committed manifests
    synth/      (labels committed only if small; else manifest)
    dev/        (gitignored)
  outputs/
    exports/    (gitignored)
    reports/                 # methodology + certification reports (committed)
    ledger/ledger.jsonl      # committed: the audit trail is a showcase artifact
    dashboard/               # CSV extracts for Tableau (committed)
  docs/
    findings/phase-0.md ... phase-8.md
    adr/                     # any non-trivial design decision gets an ADR
  scripts/
    reproduce.ps1 / reproduce.sh
  tests/
    fixtures/                # tiny hand-crafted DataFrames with known edge cases
    test_validate.py, test_transform.py, test_kanon.py,
    test_ledger.py, test_recognizers.py, test_policies.py, test_guardrails.py
```

# 7. PHASE PLAN WITH ACCEPTANCE CRITERIA

Workflow per phase: implement → `pytest` + `ruff check` green → run CLI command on dev slice → write `docs/findings/phase-N.md` → commit `Phase N: <summary>`.

## Phase 0 — Scaffold, ingest, synthetic layer (est. 2 days)
Build: repo skeleton, uv env, CLAUDE.md, `safeharbor fetch --month YYYY-MM`, manifest cache, schema introspection, Uber filter, synthetic generator + labels, dev slice.
**Accept when:** one real month cached with manifest and SHA-256; introspected schema recorded in findings; `dev_slice.parquet` is 250K rows, reproducible (same seed = same hash); labels.parquet spans align exactly with injected values (test: re-extract by offsets, compare); decoy notes contain zero labeled spans.

## Phase 1 — Validation gate (est. 2 days)
Build: Pandera contract from introspected schema; cross-field checks: dropoff >= pickup, `abs(trip_time - (dropoff - pickup).seconds) <= 60`, non-negative money fields, zone IDs in lookup, duplicate trip detection, per-column null-rate thresholds; certification report with 0-100 health score (VenueInsights breakdown: completeness, validity, consistency, uniqueness); configurable gate threshold (default 90) below which export is refused.
**Accept when:** `safeharbor validate --input dev` emits JSON + human-readable report; tests prove each check fires on a crafted bad fixture and passes on a clean one; intentionally corrupted slice scores measurably lower and is refused by the gate.

## Phase 2 — Classification and PII detection (est. 2-3 days)
Build: `classification.yaml` tiering every column direct/quasi/sensitive/safe; Presidio engine over support_note; custom recognizers for TLC license, NY plate, VIN; evaluation harness computing precision/recall/F1 per entity type vs ground truth.
**Accept when:** `safeharbor classify --input dev` writes a detection report with per-entity precision and recall; recall >= 0.95 and precision >= 0.90 on labeled spans (tune recognizers/thresholds until met, document the tuning in findings); every schema column appears in classification.yaml (test enforces no unclassified columns).

## Phase 3 — Transform engine (est. 3 days)
Build: suppression; salted SHA-256 pseudonymization with per-export salt + ledger fingerprint; temporal rounding (param: minutes); spatial rollup zone->borough (param); k-anonymity over configurable quasi-identifier tuple (default PULocationID x DOLocationID x pickup time bucket): equivalence-class computation in DuckDB SQL, small-cell suppression below k; uniqueness metric = share of rows in classes of size 1, computed before and after.
**Accept when:** all transforms pure functions with unit tests on hand-crafted fixtures (including a fixture where exactly one known cell falls below k); same salt = same pseudonyms, different salt = disjoint pseudonyms (test); `safeharbor risk --input dev` prints before/after uniqueness at minute-level vs bucketed time; full-month run completes without loading raw parquet into pandas.

## Phase 4 — Export profiles (est. 2 days)
Build: three YAML policies (TLC trip submission: row-level, pseudonymized, 15-min rounding, full fare fields, schema matched to HVFHV dictionary; MDS-style aggregate: zone x time-bucket counts, k-suppressed; law-enforcement extract: trip-scoped, minimal fields, requires approval record to run); pydantic policy schema; compiler policy -> ordered transform plan; runner that refuses to run if certification gate failed or (LE profile) approval absent.
**Accept when:** all three exports produce files + methodology reports from one command each (`safeharbor export --profile tlc --input dev`); adding a toy fourth policy file requires zero code changes (test does this); LE profile without approval fails closed with a logged refusal.

## Phase 5 — Attestation ledger (est. 2 days)
Build: append-only JSONL ledger; entry schema: `{seq, timestamp_utc, run_id, command, input_hash, policy_name, policy_version, policy_hash, transforms: [{name, params}], rows_in, rows_out, cells_suppressed, k_achieved, salt_fingerprint, output_hash, operator, prev_entry_hash, entry_hash}`; `entry_hash = sha256(canonical_json(entry minus entry_hash))` chained via `prev_entry_hash`; `safeharbor verify-ledger` walks the chain; methodology report generator pulls from ledger entry (what was shared, withheld, why, under which policy version).
**Accept when:** every pipeline command appends an entry; verify passes on intact ledger; test mutates a historical entry and verify reports the exact break point; methodology report regenerates byte-identical from the same ledger entry.

## Phase 6 — AI triage agent with guardrails (est. 2-3 days, needs ANTHROPIC_API_KEY)
Build: `safeharbor triage --request "free text"`; Claude call parses request into structured form {requester, scope, fields, window, claimed_legal_basis}; deterministic (non-LLM) guardrail layer maps fields against classification.yaml and policies, flags out-of-policy asks; drafts response plan; queues approval record; second-pass Presidio scan over anything the agent drafts; every prompt/response hashed into the ledger. **The agent has no code path to runner.py.** Architecture enforces draft-only, not prompt instructions.
**Accept when:** test suite of >= 10 canned requests (in-policy, out-of-policy, ambiguous, prompt-injection attempt embedded in the request text) produces correct triage decisions; out-of-scope and injection cases fail closed; grep proves agent module never imports the export runner; all agent interactions appear in ledger.
**Optional 6b:** Streamlit approval console. **Cut this first if behind schedule.**

## Phase 7 — Dashboard extracts (est. 1 day agent + 1 day human)
Build (agent): `safeharbor dashboard-extract` emitting tidy CSVs from ledger + reports: requests by status/profile/month, turnaround, health-score trend, suppression rates, k achieved, before/after uniqueness, PII detection metrics.
Human (Shane): build and publish the Tableau Public dashboard. **Claude Code does not attempt Tableau.** Deliberate tool choice: JD names Tableau/Looker/PowerBI and the portfolio has zero public BI artifacts; do not substitute React.
**Accept when:** CSVs load into Tableau without manual cleaning; every dashboard metric traceable to a ledger field.

## Phase 8 — Ship (est. 2-3 days, mostly human)
README (recruiter intro, honest-scope statement, reproduce instructions), reproduce.ps1/.sh (fetch -> synth -> validate -> classify -> risk -> all three exports -> verify-ledger), article on shanethakkar.com opening with the LADOT lawsuit, matplotlib figures (uniqueness before/after, equivalence-class size distribution, detection PR by entity), repo public.
**Accept when:** fresh clone + reproduce script completes end-to-end on one month; README contains zero unearned claims.

**Total: ~3 weeks. Cut order if needed: 6b Streamlit console, then LE profile to a stub. NEVER cut: labeled-PII evaluation, before/after re-identification metric, Tableau dashboard.**

# 8. CLI CONTRACT

```
safeharbor fetch --month 2026-03 [--refresh]
safeharbor synth --input <month|dev> [--seed 4242]
safeharbor validate --input <month|dev>
safeharbor classify --input <month|dev>
safeharbor risk --input <month|dev> [--qi PULocationID,DOLocationID,pickup_bucket] [--bucket-min 15]
safeharbor export --profile <tlc|mds|le> --input <month|dev> [--approval <id>]
safeharbor triage --request "<text>"
safeharbor approve --request-id <id>      # human-only command, writes approval record
safeharbor verify-ledger
safeharbor dashboard-extract
```
Every command: Rich console summary, JSON artifact under outputs/, ledger entry.

# 9. HEADLINE METRICS TO EARN (fill with real numbers)

- N million real Uber trips processed across M months
- X% of trips unique on PU zone x DO zone x minute-level pickup -> < Y% post-policy at k = Z
- P% precision / R% recall on N labeled synthetic PII spans, per entity type
- C validation checks per ingest; 100% of transformations in a verifiable hash chain
- 3 regulator profiles; new profile = 1 YAML file, 0 code changes
- Literature anchor for the article: de Montjoye et al. 2013, four spatiotemporal points uniquely identify 95% of individuals in mobility traces

# 10. RESUME BULLETS (drafts, Shane's style rules applied)

*Built a privacy-safe regulatory data-sharing pipeline converting raw ride-trip data into regulator-ready exports, processing N million real Uber trips from NYC TLC records under policy-driven anonymization with a tamper-evident audit trail.*

• Engineered a six-stage Python pipeline using DuckDB, Pandera, and pyarrow that validates, classifies, and transforms trip data under declarative YAML sharing policies, reducing trip re-identification uniqueness from X% to under Y% via k-anonymity suppression, salted pseudonymization, and temporal generalization.

• Measured PII detection at P% precision and R% recall against N labeled spans by generating a synthetic ground-truth identity layer, extending Microsoft Presidio with custom recognizers for license, plate, and VIN formats.

• Implemented a hash-chained audit ledger recording every transformation, suppression count, and policy version per export, with a verification command proving ledger integrity and an auto-generated methodology report accompanying each release.

• Deployed a Claude-powered triage agent that parses regulator data requests, maps them to sharing policies, and flags out-of-policy asks under hard guardrails: draft-only authority, fail-closed scope checks, and mandatory human approval logged to the ledger.

• Published an automated Tableau compliance dashboard tracking request turnaround, suppression rates, data health scores, and re-identification risk across monthly ingests.

# 11. INTERVIEW AMMUNITION

- **Why this project:** the LADOT lawsuit. Studied the real conflict between Uber and a regulator, built the system that resolves it.
- **Data validation:** certification gate that blocks export below threshold; fare-arithmetic and temporal-sanity checks; health-score breakdown.
- **Responsible AI:** the agent architecturally cannot release data; guardrails are deterministic code, not prompt text; injection test cases in the suite.
- **GDPR/CCPA:** classification tiers; pseudonymization vs anonymization distinction; salt rotation prevents cross-release joins; erasure story: destroying a salt renders prior exports unlinkable.
- **SQL at scale:** DuckDB analytical SQL over 20M+ row Parquet; equivalence-class computation for k-anonymity written in SQL.

# 12. RISKS AND HONEST FLAGS

- Synthetic PII must be labeled synthetic everywhere. Never imply real rider PII was handled.
- Do not present k-anonymity as solving location privacy; document homogeneity and background-knowledge attacks the way EdgarRisk documented blind spots.
- LADOT framing stays neutral-to-sympathetic to both sides; the article's stance is that both parties had legitimate claims and tooling was the gap.
- TLC schema may shift; the Pandera contract derives from the introspected schema recorded in Phase 0 findings, not from this document.
- Presidio does not guarantee total recall; report measured numbers, state the residual-risk caveat.

# 13. HUMAN-ONLY TASKS (Claude Code: do not attempt)

1. Tableau Public dashboard build and publish (Phase 7)
2. Article drafting and publication on shanethakkar.com (Phase 8; separate session with website repo context)
3. `safeharbor approve` invocations: approvals are human acts by design
4. Anthropic API key provisioning
5. Final decisions on k, time buckets, month selection (Section 2 escalation list)
6. Making the GitHub repo public

# 14. CLAUDE.MD SEED (write this file at Phase 0, keep it current)

Distill into the repo's CLAUDE.md: the operating rules (Section 2), the pure-function I/O boundary, the scale guardrail (never load full monthly parquet into pandas), the CLI contract, the phase workflow (implement -> test -> lint -> dev-slice run -> findings note -> commit), the escalation list, and the honesty rules. Add a "current state" section updated at the end of every session: last completed phase, open questions, next step.
