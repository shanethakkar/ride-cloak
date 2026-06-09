# Phase 3 findings — Transform engine

**Status:** complete. `pytest` (64 passed) and `ruff` green; `ridecloak risk --input dev` and
`--input month --month 2026-04` both run end to end (the month in 4.3s via DuckDB, no pandas).

## What was built
Pure transforms under `pipeline/transform/` (DataFrame in -> DataFrame + audit-dict out):
- **`generalize.py`** — `round_time` (floor to N-min bucket) and `rollup_zone` (zone -> borough
  via the taxi-zone lookup).
- **`pseudonymize.py`** — salted SHA-256 (`pseudonymize`, `salt_fingerprint`); per-export salt
  generated/stored by `pipeline/io/salts.py` under gitignored `secrets/salts/`, referenced by
  fingerprint only.
- **`suppress.py`** — `drop_columns` and `redact_spans` (masks PII spans in free text using the
  Phase 2 detector's offsets; pure offset-masking, detection wired at the composition layer).
- **`kanon.py`** — `uniqueness`, `suppress_below_k` (drop records in classes < k; audit
  rows_in/rows_out/cells_suppressed/k_achieved), plus DuckDB SQL builders
  (`uniqueness_sql`, `suppression_sql`, `k_achieved_sql`) for the scale path.
- **`risk.py` + `ridecloak risk`** — the uniqueness ladder and k-suppression cost; dev in
  pandas, month via the SQL builders over a borough-joined DuckDB view.

## The headline finding (the spine of the article)
Re-identification uniqueness on the **full 15.4M-row month**, and the k=5 suppression cost:

| quasi-identifier | uniqueness | k=5 suppressed |
|---|---:|---:|
| zone x minute | 90.1% | - |
| zone x 15-min | 46.0% | 85.3% |
| zone x 60-min | 21.6% | - |
| **borough x 15-min** | **0.06%** | **0.26%** |

**Raw zone-level trip data cannot be k-anonymized** — at zone x 15-min, k=5 suppresses 85% of
rows. **Generalization is the dominant lever:** rolling zones up to borough drops uniqueness to
0.06% and k=5 then suppresses only 0.26% — the data survives essentially intact. This is the de
Montjoye result made concrete and quantified end to end.

## Honest note on the dev slice vs the month
The 250K dev slice is a *sample*, so it is sparser and **overstates uniqueness**: it reads
zone x minute 99.8% / borough x 15-min 5.4% (k=5 borough suppression 23%). The full-month
figures above are the true distribution and the ones to cite. `risk` reports both; the report
header records the source so the two are never conflated.

## Metrics / scale
- `risk --input month` assessed 15.4M rows in **4.3s** computing equivalence classes in DuckDB
  SQL — no raw parquet loaded into pandas (scale guardrail honored; a real SQL-at-scale artifact).

## Acceptance criteria — all met
1. All transforms are pure functions with unit tests on hand-crafted fixtures, including a
   fixture where **exactly one known cell falls below k** ✅
2. Same salt = same pseudonyms, different salt = disjoint ✅ (tested)
3. `ridecloak risk --input dev` prints before/after uniqueness at minute-level vs bucketed ✅
4. Full-month run completes without loading raw parquet into pandas ✅. 64 tests pass, ruff clean.

## Decisions / notes
- k=5 default, raw-zone default QI with the full ladder shown, support_note span redaction,
  record-drop suppression, salted-SHA-256 + per-export salt fingerprint (all D-0008).
- The redaction transform is built and unit-tested; it is *composed* into an export in Phase 4
  (it consumes Phase 2 detections at the export-runner layer).

## Open questions for later phases
- Phase 4: the export profiles choose the per-profile k and bucket and compose these transforms
  into ordered plans (TLC row-level pseudonymized; MDS borough/zone aggregate, k-suppressed; LE
  minimal + approval). The audit dicts here already carry the ledger fields for Phase 5.
