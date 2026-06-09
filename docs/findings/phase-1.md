# Phase 1 findings — Validation gate

**Status:** complete. `pytest` (30 passed) and `ruff check`/`format` green; `ridecloak validate
--input dev` and `--input month --month 2026-04` both run end to end and PASS.

## What was built
Two-tier validation gate (decisions.md D-0006) under `pipeline/validate/` (pure core):
- **`contract.py` — Tier 1 (hard).** Pandera `DataFrameSchema` over the 25 real HVFHV columns:
  dtypes, value domains (zone IDs in 1-265, `trip_time >= 0`, `trip_miles >= 0`, license =
  HV0003), and nullability. `strict=False` ignores the synth columns; `coerce=True` smooths the
  parquet `datetime64[us]`/`int32`/`string` dtypes. Returns `{passed, failures}`.
- **`checks.py` — Tier 2 (soft).** Per-rule masks for validity (per-field money non-negative,
  `trip_miles >= 0`, flags in {Y,N}) and consistency (`dropoff >= pickup`,
  `|trip_time - wall-clock duration| <= 60s`), plus completeness (null cells) and uniqueness
  (duplicate rows). Same rules are emitted as a **single-pass DuckDB aggregation**
  (`month_aggregate_sql`) for the scale path.
- **`health.py` — score + gate.** Four equally weighted dimensions (25 each); subscore =
  `100*(1 - fail_rate)`; composite = mean; gate refuses below `gate_threshold` (default 90). A
  Tier-1 failure short-circuits to a refusal with no numeric score.
- **`report.py`** renders a committed-quality markdown certification report; `cli validate`
  writes JSON + markdown to `outputs/reports/` and prints a Rich per-dimension summary.

## Calibration (full-month profile, recorded before locking the contract)
Profiled all **15,378,858 HV0003 rows** of 2026-04 (`data/raw/manifests/profile_2026-04.json`):
- **Zero nulls** in every column even at full scale.
- Negatives only in `base_passenger_fare` (5,426 = 0.035%, min -222.34) and `driver_pay`
  (7, min -32.77) — legitimate refund/adjustment rows. This is why money non-negativity is a
  Tier-2 validity ding, **not** a hard fail; a strict contract would wrongly reject real data.
- Temporal: `dropoff < pickup` = 0; `|trip_time - duration| > 60s` = 561 (0.0036%).
- Zones: 0 out of range (lookup is contiguous 1-265). Flags strictly {Y,N}.
These set the contract's nullable flags (optional columns nullable for cross-month robustness
despite 0 observed nulls) and confirm the real data passes its own gate comfortably.

## Metrics observed
- **Clean dev slice (250K): composite 99.99 / 100, PASSED.** Validity 99.96 (the 89 negative
  `base_passenger_fare` rows = 0.036%); other dimensions 100.
- **Full month (15.4M): composite 99.99, PASSED in 5.5s** via the single-pass DuckDB
  aggregation — no parquet loaded into pandas (scale guardrail honored, and a real SQL-at-scale
  artifact).
- **Corrupted fixture: composite 78.83, REFUSED** (completeness 98.67, validity 66.67,
  consistency 66.67, uniqueness 83.33) — proving the gate discriminates.

## Acceptance criteria — all met
1. `validate --input dev` emits JSON + human-readable report and passes clean 2026-04
   (score ≥ 90) ✅  2. Each check fires on a crafted bad fixture and passes on a clean one ✅
   (per-rule tests)  3. A corrupted slice scores measurably lower and is refused ✅
   4. Full-month profile recorded ✅. 30 tests pass, ruff clean.

## Decisions / notes
- Two-tier gate + equal weights locked in D-0006.
- The CLI exits non-zero when the gate refuses, so reproduce scripts stop before exporting
  refused data.
- A non-editable wheel build would not currently include the root `cli.py` (we use
  `dev-mode-dirs` for the editable `ridecloak` entrypoint); revisit only if a wheel is needed.

## Open questions for later phases
- Phase 3/4: the duplicate-detection key here is the full real row; confirm whether a business
  key (pickup × PU × DO × driver) is wanted for the export profiles.
- Fare-arithmetic cross-check (sum of components vs total) was deferred — the HVFHV components
  don't cleanly sum to `base_passenger_fare`; revisit if a defensible identity exists.
