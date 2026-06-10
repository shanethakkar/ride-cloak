# Phase 8 findings — Ship

**Status:** agent-side deliverables complete. `pytest` (109 passed) and `ruff` green; the
reproduce script runs the whole pipeline end to end and regenerates every committed artifact.
The remaining items (Tableau dashboard, publishing the article, making the repo public) are
Shane's.

## What was built
- **`scripts/reproduce.sh` / `reproduce.ps1`** — one command that runs the full pipeline and
  regenerates the ledger, reports, dashboard CSVs, and figures. Parameterized by `MONTHS`
  (default the 4-month showcase; `MONTHS="2026-04"` for the SPEC single-month acceptance). Resets
  the append-only ledger so the canonical run starts fresh; the AI triage step is key-gated and
  skipped without a key; the LE export fails closed (no approval) by design.
- **`README.md`** — recruiter-facing: the LADOT framing, the headline uniqueness finding (with the
  committed figure), a results-at-a-glance table, the six-stage architecture, the responsible-AI
  agent, the audit ledger, quickstart + reproduce, an honest-scope section, the tech stack, and
  links to the living docs. Zero unearned claims; every number traces to a committed artifact.
- **`docs/article-draft.md`** — a full first-draft article for shanethakkar.com in Shane's
  first-person voice (no AI-tell cadence), opening on the Uber-v-LA lawsuit, landing the
  re-identification finding, walking the pipeline, and featuring the guarded agent and the ledger.
  For Shane to edit and publish.

## Verification
`./scripts/reproduce.sh` completed end to end: 4 months ingested, dev + per-month scale stages,
TLC export, LE export refused (fail-closed), triage ALLOW + injection REFUSE, dashboard + figures,
and `verify-ledger` → **"Ledger intact — 26 entries verified."** The committed ledger, CSVs, and
figures are exactly what a fresh clone reproduces.

## Acceptance criteria — met (agent side)
1. A fresh clone + reproduce script completes end to end (single-month or full) ✅.
2. README contains zero unearned claims ✅ (every metric is a committed, reproducible artifact).
3. 109 tests pass, ruff clean.

## Human tasks remaining (SPEC §13)
- Build + publish the **Tableau Public dashboard** from `outputs/dashboard/*.csv`.
- Edit + publish the **article** (`docs/article-draft.md`) on shanethakkar.com.
- Make the **GitHub repo public**.

## Notes
- The explainer video was considered and **cut**: for a data-science portfolio the article + repo
  + dashboard carry the scope, and a Remotion production was not worth the effort. The figures
  built in Phase 7 serve the article directly. (See the discussion captured in the project chat.)
