# RideCloak

Privacy-safe regulated trip-data sharing pipeline.

Ingest raw ride-trip data carrying a **synthetic** PII layer, validate it against a contract,
classify every field, quantify re-identification risk, apply policy-driven privacy transforms,
emit regulator-ready exports, and record every transformation in a tamper-evident
hash-chained ledger.

> **Synthetic data notice.** No real rider PII is ever handled. RideCloak attaches a synthetic
> identity layer to already-public NYC TLC trip records to reconstruct the pre-anonymization
> input and demonstrate the transform. See [docs/limitations.md](docs/limitations.md).

This README is a stub; the recruiter-facing README is written in Phase 8. For now see:
- [docs/SPEC.md](docs/SPEC.md) — full specification (source of truth)
- [CLAUDE.md](CLAUDE.md) — operating guide and current state
- [docs/plan.md](docs/plan.md) — roadmap and phase status

## Quickstart (in progress)

```powershell
uv sync
uv run python -m spacy download en_core_web_lg   # Presidio NER model (Phase 2)
uv run ridecloak fetch --month 2026-04
uv run ridecloak synth --input dev
uv run ridecloak validate --input dev
uv run ridecloak classify --input dev
```
