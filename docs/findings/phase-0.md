# Phase 0 findings — Scaffold, ingest, synthetic layer

**Status:** complete. `pytest` (13 passed) and `ruff check` / `ruff format` green; `ridecloak
fetch` and `ridecloak synth --input dev` run end to end on the dev slice.

## What was built
- **Repo + toolchain:** uv project (`pyproject.toml`, `uv.lock`), flat layout matching SPEC §6
  (`config/`, `pipeline/`, `policies/`, `cli.py`, `tests/`). Ruff (select F/E/W/I/B/C4/UP/N,
  line length 100) and pytest configured in `pyproject.toml`. `.gitignore`, `.env.example`,
  `config/settings.py` (pydantic-settings, prefix `RIDECLOAK_`, paths resolved from project root).
- **Ingest (`pipeline/io/`):** `fetch.py` streams the TLC HVFHV Parquet and zone lookup to
  `data/raw/` with atomic temp-then-replace and streaming SHA-256; writes a JSON manifest per
  artifact. `duck.py` wraps DuckDB (connect with optional thread pin, `DESCRIBE` schema
  introspection, `row_count`, `query_df`). `readers.py`/`writers.py` hold small-artifact I/O;
  writers are idempotent (mkdir + overwrite).
- **Synthetic layer (`pipeline/synth/`):** `generator.py` is the pure core — given real rows +
  a seed it returns the rows enriched with a synthetic identity layer plus a `labels` frame of
  every injected PII span; no I/O. `templates.py` holds support-note builders with the SPEC hard
  cases. `devslice.py` orchestrates the deterministic 250K sample and writes the artifacts.
- **CLI:** `ridecloak fetch --month` and `ridecloak synth --input dev|month` with Rich summaries.

## Ingest facts (2026-04, the locked first month — decisions.md D-0004)
- Most recent available month as of 2026-06-09 is **2026-04** (2026-05 returns HTTP 403, not yet
  published — consistent with TLC's ~2-month delay).
- Raw file: **20,995,953 rows**, 509,865,567 bytes,
  SHA-256 `15525aea9f82d55b885c6053414054e63f4c9abb3cdc44d78120a77d3aecc92b`.
- **Uber (HV0003): 15,378,858 rows = 73.2%** — within the SPEC's expected 70–75% band.

## Introspected schema (recorded before locking the Pandera contract — SPEC §5.2)
`DESCRIBE` reports **25 columns**, exactly the SPEC's expected set including the 2025+
`cbd_congestion_fee` (DOUBLE). **No drift surprises.** Types: `VARCHAR` for the five license/base
and five flag fields; `TIMESTAMP` for the four datetimes; `INTEGER` for PU/DOLocationID; `BIGINT`
for `trip_time`; `DOUBLE` for all money/miles fields. The machine-readable schema is committed at
`data/raw/manifests/schema_2026-04.json` for Phase 1 to build the contract from.

## Dev slice + labels
- Deterministic 250K-row Uber sample selected by `ORDER BY md5(concat_ws(... 10 attribute cols
  ...)) LIMIT 250000` under `threads=1`, so the same month + seed reproduce a byte-identical
  file. Verified: two builds produce identical SHA-256 (`85668d0269af…`), 250K unique `trip_id`.
- `trip_id` is a deterministic UUID5 of stable trip attributes (the join key).
- Identities: riders and drivers are Zipf-skewed pools (exponents 1.07 / 1.03) so frequent
  riders exist for the re-identification story — **26,677 unique riders** across 250K trips.
- Support notes on **4,952 trips (1.98%)**; **3,702** are PII notes yielding **7,404 labeled
  spans**, **1,250** are decoys with zero spans. Span distribution: PERSON 2,456, PHONE_NUMBER
  1,860, EMAIL_ADDRESS 1,258, LOCATION 1,195, CREDIT_CARD 635.

## Acceptance criteria — all met
1. Month cached with manifest + SHA-256 ✅  2. Introspected schema recorded ✅
3. `dev_slice.parquet` = 250K rows, reproducible (same seed = same hash) ✅ (integration test)
4. Labels re-extract byte-for-byte by offset (hash match) ✅  5. Decoy notes have zero spans ✅

## Decisions / notes
- First month locked to 2026-04 (decisions.md D-0004). `labels.parquet` is small (7,404 rows)
  but lives under gitignored `data/synth/`; the commit-or-manifest call is deferred to when its
  size matters — labels are reproducible from the seed regardless.

## Open questions for later phases
- Phase 1: choose null-rate thresholds and the exact cross-field tolerances from the real
  column null rates (not yet profiled).
- Phase 2: the five synthetic entity types map to Presidio defaults; confirm the address
  hard-case (no St/Ave suffix) is detectable as `LOCATION` and tune recognizers to hit
  recall ≥ 0.95 / precision ≥ 0.90.
