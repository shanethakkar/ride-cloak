# Methodology

**Role of this file.** The project-level narrative of *how* RideCloak works and *why* each
technique was chosen — the "documented, auditable analysis" the JD calls for. This is distinct
from the per-export methodology **reports** auto-generated at runtime under `outputs/reports/`
(those describe one specific export: what was shared, withheld, why, under which policy
version). This file describes the approach in general.

**How and when to update.** Update when a method is added, changed, or when a phase pins down a
parameter or measured value that the methodology references (e.g. the final k, measured
detection rates). Keep it conceptual and durable; put run-specific numbers in the per-export
reports and the headline-metrics tracking, and link measured bounds to `limitations.md`.

---

## 1. Problem framing

The public NYC TLC High-Volume FHV dataset is the **output** of a privacy pipeline. RideCloak
reconstructs the plausible **input** — real trip records plus a *synthetic* identity layer —
and then rebuilds the pipeline that would responsibly turn that input back into a
regulator-ready release. The motivating real-world tension (Uber v. LADOT, 2020; Uber's
biweekly TLC SFTP submissions under Local Law 149) is that regulators have a legitimate claim
to trip data and riders to privacy, and the pipeline in the middle is where that conflict is
resolved. RideCloak is that pipeline, made auditable.

## 2. Pipeline stages

```
ingest → validate → classify → transform → export → attest
```

- **Ingest** (`pipeline/io/`, `pipeline/synth/`): download a real TLC month, cache with a
  manifest (source URL, date, SHA-256, row count), introspect the actual schema, filter to Uber
  (`hvfhs_license_num = 'HV0003'`), attach the seeded synthetic PII layer plus ground-truth
  span labels, and cut a deterministic dev slice. Real-data scale is handled in DuckDB; pandas
  only ever sees filtered/sampled rows.
- **Validate** (`pipeline/validate/`): a Pandera contract derived from the *introspected*
  schema, plus cross-field checks (temporal ordering, fare arithmetic, zone-ID membership,
  duplicate detection, null-rate thresholds). Produces a 0–100 health score across four
  dimensions; a configurable gate refuses export below threshold.
- **Classify** (`pipeline/classify/`): every column tiered direct / quasi / sensitive / safe in
  a versioned `classification.yaml`; Presidio plus custom recognizers scan free-text
  `support_note`; an evaluation harness measures detection against the synthetic labels.
- **Transform** (`pipeline/transform/`): suppression, salted-SHA-256 pseudonymization,
  temporal generalization, spatial rollup, and k-anonymity with small-cell suppression. All
  pure functions: DataFrame in, DataFrame + audit-record dict out.
- **Export** (`pipeline/export/`): a declarative YAML policy compiles to an ordered transform
  plan; the runner executes it, emits the export file, and writes a methodology report. The
  runner refuses to run if the validation gate failed or (law-enforcement profile) an approval
  record is absent.
- **Attest** (`pipeline/attest/`): every command appends an entry to a hash-chained JSONL
  ledger; `verify-ledger` walks the chain and detects any mutation.

## 3. Privacy model and techniques

- **Classification tiers** drive everything downstream: direct identifiers are
  suppressed or pseudonymized; quasi-identifiers are generalized and feed k-anonymity;
  sensitive fields are handled per policy; safe fields pass through.
- **Pseudonymization** is salted SHA-256 with a **per-export** salt. Same salt → same
  pseudonyms (joinable within a release); different salt → disjoint pseudonyms (no cross-release
  linkage). Salts live only in `secrets/salts/` (gitignored) and are referenced in the ledger by
  SHA-256 fingerprint, never by value. This is pseudonymization, **not** anonymization
  (see [limitations.md](limitations.md) L-06). The **erasure story**: destroying a salt renders
  its prior exports unlinkable — the GDPR/CCPA right-to-erasure narrative as a design property.
- **Generalization**: temporal rounding (parameter: minutes) and spatial rollup
  (zone → borough) coarsen quasi-identifiers before risk measurement.
- **k-anonymity**: equivalence classes are computed in DuckDB SQL over a configurable
  quasi-identifier tuple (default `PULocationID × DOLocationID × pickup time bucket`); rows in
  classes smaller than k are suppressed. The guarantee is syntactic and has known weaknesses
  (see [limitations.md](limitations.md) L-02).

## 4. Threat model

- **Adversary:** a recipient of a released export (or a leak of one) attempting to
  re-identify riders or drivers by matching quasi-identifiers against external knowledge.
- **In scope:** re-identification via unique or near-unique spatiotemporal signatures; linkage
  across releases; PII leaking through free-text fields; tampering with the audit trail.
- **Mitigations:** generalization + k-suppression reduce uniqueness; per-export salt rotation
  blocks cross-release linkage; PII scanning (with a second pass over anything the AI agent
  drafts) catches free-text leakage; the hash chain makes ledger tampering detectable.
- **Out of scope:** an adversary with prior knowledge that a specific person took a specific
  trip (k-anonymity does not defend this); transport/auth/network attacks on a delivery channel
  RideCloak does not implement (see [limitations.md](limitations.md) L-04).

## 5. AI triage agent (responsible-AI posture)

The Claude triage agent parses a free-text regulator request into a structured form, maps the
requested fields against `classification.yaml` and the policies, flags out-of-policy asks,
drafts a response plan, and queues an approval record. Its guardrails are **deterministic code,
not prompt text**: the agent has **no code path to the export runner** (enforced by
architecture and proven by a grep test), scope checks **fail closed**, a second Presidio pass
re-scans anything it drafts, and every prompt/response is hashed into the ledger. Human approval
is mandatory and is itself a human-only action.

## 6. Metric definitions

- **Re-identification uniqueness:** share of rows that are unique on the quasi-identifier tuple
  (a class of size 1). Reported **before and after** the policy transform; the headline is the
  drop (e.g. X% → < Y% at k = Z). Minute-level vs bucketed time is compared.
- **k achieved:** the minimum equivalence-class size in the released table after small-cell
  suppression (≥ the policy k by construction); reported per export.
- **Cells suppressed:** count of rows/cells removed by small-cell suppression, per export.
- **Precision / recall / F1 (PII detection):** measured per entity type against the synthetic
  ground-truth spans in `labels.parquet`. Precision = correct detections / all detections;
  recall = correct detections / all true spans; F1 = harmonic mean. These are measured floors on
  the labeled test set, not guarantees on unseen data ([limitations.md](limitations.md) L-03).
- **Health score (0–100):** weighted composite of completeness, validity, consistency, and
  uniqueness from the validation gate.

## 7. Literature anchor

de Montjoye, Hidalgo, Verleysen & Blondel (2013), *Unique in the Crowd: The privacy bounds of
human mobility* — four spatiotemporal points uniquely identify 95% of individuals in mobility
traces. This is the quantitative basis for why raw trip data is re-identifiable and why
generalization + k-suppression are necessary (and why they are insufficient alone).

---

_Run-specific numbers (final k, measured detection rates, before/after uniqueness) live in the
per-export reports and the headline-metrics tracking; backfill the bounds referenced above into
[limitations.md](limitations.md) as phases complete._
