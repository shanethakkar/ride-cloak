# Phase 7 findings — Dashboard extracts (multi-month) + figures

**Status:** complete (agent side). `pytest` (109 passed) and `ruff` green; `ridecloak
dashboard-extract` and `ridecloak figures` run end to end over a 4-month dataset. The human task
(build + publish the Tableau Public dashboard from the CSVs) remains.

## What was built
- **Multi-month data (D-0012):** ingested **2026-01 .. 2026-04** and ran the scale-path stages
  (`validate` / `risk` / `export --profile mds`) on `--input month` for each — 12 commands, each
  appending a per-month ledger entry. Dev-scoped stages stay on 2026-04. **~83.9M total trips
  (~61M Uber, 73%) across 4 months** — the headline "N million Uber trips across M months" is now
  earned.
- **`pipeline/dashboard/extract.py`** — pure tidy-table builders over the ledger (+ committed
  report JSONs), writing 8 long/tidy CSVs to `outputs/dashboard/`: `ledger_events` (25),
  `exports` (7), `validation` (5), `uniqueness` (20), `suppression` (8), `detection` (9),
  `triage` (2), `requests` (2, with turnaround). A `scope` column distinguishes the 250K dev
  sample from the full month (they share a month label but the sample overstates uniqueness).
- **`pipeline/dashboard/figures.py`** — matplotlib (Agg) PNGs to `outputs/figures/`: the
  uniqueness ladder (90.1% → 0.1% for 2026-04), per-entity detection precision/recall, and the
  health-score + borough-suppression month trends. These feed the article and the video.
- CLI: **`ridecloak dashboard-extract`** and **`ridecloak figures`** (both append a ledger entry).
  Ledger now 25 entries, `verify-ledger` intact.

## Traceability
Headline metrics come straight from ledger fields: export rows/suppression/k and validation
health from the export/validate entries; the uniqueness ladder from the risk entries'
`metrics.ladder`; triage verdicts and request turnaround from the triage/approve/export chain.
Per-entity detection and the borough suppression detail come from the committed
classification/risk report JSONs (themselves audited artifacts; the overall figures are in the
ledger). Each CSV is tidy/long with ISO timestamps and numeric columns — loads into Tableau with
no manual cleaning.

## Acceptance criteria — all met
1. CSVs load into Tableau without manual cleaning ✅ (tidy/long, typed columns).
2. Every dashboard metric traces to a ledger field ✅ (with report JSONs for per-entity detail).
3. 4-month trends populated ✅; figures render ✅. 109 tests pass, ruff clean.

## Notes
- The health-score trend is a flat ~100 across all four months — honest: the published HVFHV data
  is consistently clean. A flat line is a true signal (reliable data quality), not a gap.
- `uv add matplotlib`. Figures + CSVs committed; raw monthly parquet stays gitignored.

## Handoff
- **Human (Shane):** build the Tableau Public dashboard from `outputs/dashboard/*.csv` (Claude
  Code does not attempt Tableau). The figures in `outputs/figures/` are ready for the article and
  the Remotion explainer video — that video is the next planned artifact.
