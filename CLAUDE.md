# CLAUDE.md — RideCloak

Privacy-safe regulated trip-data sharing pipeline. Full spec: [docs/SPEC.md](docs/SPEC.md)
(the source of truth — read it before writing code). This file is the lean operating guide;
detailed, evolving context lives in the living docs indexed below.

> **Naming:** the project and CLI are **RideCloak** / `ridecloak`. The SPEC's older examples say
> `safeharbor`; translate those to `ridecloak`. See [decisions.md](docs/decisions.md) D-0001.

## Living docs (read on demand; keep current — see Maintenance)
- [docs/plan.md](docs/plan.md) — roadmap, current state, phase status, pending escalations.
- [docs/decisions.md](docs/decisions.md) — dated decision log (rollup over `docs/adr/`).
- [docs/limitations.md](docs/limitations.md) — honest limits; what RideCloak does not do.
- [docs/methodology.md](docs/methodology.md) — pipeline approach, threat model, metric defs.
- Also: `docs/findings/phase-N.md` (per-phase build notes), `docs/adr/` (full ADRs),
  `outputs/reports/` (per-export methodology reports, generated at runtime).

## Maintenance rule — KEEP THE LIVING DOCS CURRENT (highest-priority standing instruction)

**IMPORTANT: These docs are only useful if they are always current. Updating them is part of
the task, not optional cleanup. You MUST treat a doc update as a required step of any change —
the work is not done until the relevant doc reflects it.**

The moment you learn something durable, update the matching doc **in the same turn, before
moving on** — never batch these or defer them to "later":

- **The plan changes in any way** — scope, sequencing, a phase starts/finishes, the next step
  shifts, an acceptance criterion is met, or we agree to do something differently → **you MUST
  update [plan.md](docs/plan.md)** (Current State + the affected phase) immediately. Any time
  the plan is updated, plan.md is updated. No exceptions.
- A decision made or an open question resolved → append to [decisions.md](docs/decisions.md)
  (full ADR in `docs/adr/` if non-trivial).
- A limit, caveat, or measured bound → [limitations.md](docs/limitations.md) (and document it
  in place too — docstring/report/README).
- A new/changed method or a pinned parameter/metric → [methodology.md](docs/methodology.md).

**End-of-session checklist (run every session, no exceptions):** update [plan.md](docs/plan.md)
Current State and the Current State block at the bottom of this file; confirm any decisions,
limitations, or methodology changes from the session were written to their docs. If nothing
changed in a given doc, that is fine — but you must have actively checked. Tick acceptance
criteria only when actually verified (`pytest` + `ruff` green, CLI run on dev slice).

If you ever notice a doc is stale or contradicts reality, fixing it takes priority over new
work — a wrong doc is worse than a missing one.

## Operating rules (distilled from SPEC §2 — binding)
- **Python 3.12**, type hints on all public functions, docstrings (purpose / inputs / outputs).
- **No emojis. No AI-sounding comments.** Comments explain *why*, not *what*. Production-grade.
- **`pathlib` everywhere**; resolve project root from file location so scripts run from anywhere.
- **Pure-function core:** everything in `pipeline/validate/`, `pipeline/classify/`,
  `pipeline/transform/` takes DataFrames/Arrow in and returns DataFrames + an audit-record dict
  out. **No file/DB I/O inside math/transform modules** — I/O lives only in `pipeline/io/` and
  the CLI layer.
- **Idempotent** file-producing ops: re-running overwrites cleanly, never duplicates.
- **`ruff` lint+format and `pytest` must both pass** before any phase is done.

## Scale guardrail (do not violate)
HVFHV monthly Parquet is ~17–20M rows. **Never `pd.read_parquet` a full monthly file into
pandas.** Query Parquet in place with **DuckDB**; pull only filtered/aggregated results into
pandas. Develop against the 250K-row dev slice; full-month runs are verification-only.

## Secrets & config
- `pydantic-settings` + `.env` (gitignored); commit `.env.example` with placeholders.
- `ANTHROPIC_API_KEY` only for Phase 6. Never hardcode, never log it.
- Pseudonymization salts: generated per export run, stored only in `secrets/salts/`
  (gitignored), referenced in the ledger by SHA-256 **fingerprint**, never by value.

## Honesty rules (project brand — non-negotiable)
- The PII layer is **synthetic** and must be labeled synthetic in every artifact. Never imply
  real rider PII was handled. Framing: "reconstructed the pre-anonymization input to demonstrate
  the transform." Details: [limitations.md](docs/limitations.md).
- Document limitations in place: k-anonymity's homogeneity/background-knowledge weaknesses,
  Presidio's non-guarantee of total recall, the demo-vs-production gap.

## Phase workflow (SPEC §7)
implement → `pytest` + `ruff check` green → run the phase CLI command on the dev slice →
write `docs/findings/phase-N.md` (~300–800 words) → commit `Phase N: <summary>`.

## Git discipline
- One commit per completed phase minimum; message `Phase N: <summary>`.
- `.gitignore`: `data/raw/`, `data/dev/`, `secrets/`, `.env`, `outputs/exports/`. Commit
  manifests, configs, policies, reports, and the ledger. The synth generator + seed are
  committed; generated synthetic data is not (it's reproducible).

## Escalate to Shane — do not decide alone (SPEC §2)
1. Final k threshold (build as a policy param; dev default k=5).
2. Time-bucket sizes per profile (defaults: TLC 15 min, MDS 60 min).
3. Months of data beyond the first.
4. Any dependency outside the approved stack (SPEC §4).
5. Anything requiring a paid service.
6. Renaming the project (already settled: RideCloak).

Human-only actions (never attempt): Tableau build/publish, article writing, `ridecloak approve`,
API-key provisioning, final k/bucket/month calls, making the repo public. (SPEC §13)

## CLI contract (entrypoint `ridecloak`, Click)
```
ridecloak fetch --month 2026-03 [--refresh]
ridecloak synth --input <month|dev> [--seed 4242]
ridecloak validate --input <month|dev>
ridecloak classify --input <month|dev>
ridecloak risk --input <month|dev> [--qi PULocationID,DOLocationID,pickup_bucket] [--bucket-min 15]
ridecloak export --profile <tlc|mds|le> --input <month|dev> [--approval <id>]
ridecloak triage --request "<text>"
ridecloak approve --request-id <id>      # human-only
ridecloak verify-ledger
ridecloak dashboard-extract
```
Every command: Rich console summary, a JSON artifact under `outputs/`, and a ledger entry.

## Environment
Windows 11, PowerShell primary (provide PowerShell first; Bash equivalents in `scripts/`).
Python 3.12 via **uv** (`uv init`, `uv add`, commit `uv.lock`). Presidio needs a spaCy model
(`uv run python -m spacy download en_core_web_lg`; `en_core_web_sm` fallback — escalate if
accuracy suffers). Approved stack only (SPEC §4); anything else, escalate first.

## Current State
- **Phases 0–2 complete (2026-06-09).** P0: scaffold, ingest, synthetic PII layer + labels,
  250K dev slice. P1: two-tier validation gate (Pandera + equal-weighted 0–100 score), dev +
  scale-safe month paths. P2: classification dictionary (all 36 columns tiered) + Presidio
  detection over the synthetic notes — 8 entity types, 6 custom recognizers, measured **overall
  precision 0.997, recall 0.998** vs ground truth. 51 tests pass, ruff green.
- **Next step:** Phase 3 — transform engine: suppression, salted-SHA-256 pseudonymization,
  temporal rounding, spatial rollup, k-anonymity (equivalence classes in DuckDB SQL, small-cell
  suppression, before/after uniqueness). Decides final k. See [docs/plan.md](docs/plan.md).
- **Setup:** Presidio needs the spaCy model: `uv run python -m spacy download en_core_web_lg`.
