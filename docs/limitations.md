# Limitations Register

**Role of this file.** The single consolidated, honest account of what RideCloak does *not*
do, what its techniques cannot guarantee, and where the demo diverges from a production system.
It is the living version of SPEC §12 and the SPEC §2 honesty rules. The project's brand is
honesty; this file is where that brand is enforced and kept current.

**How and when to update.** Add or sharpen a limitation the moment one is discovered or
measured — especially when a phase produces a real number that bounds a claim (e.g. measured
Presidio recall < 100%). Every limitation here must also be documented *in place* (docstring,
report, README) per the SPEC; this file is the index, not a substitute. Never delete a
limitation to make the project look better — that violates the honesty rules. If a limitation
is genuinely retired, explain why with evidence.

Each entry: the limitation, why it exists, how RideCloak discloses it, and (where relevant)
the measured bound.

---

## L-01 — The PII layer is synthetic, and must be labeled synthetic everywhere
- **Limitation:** No real rider PII is ever handled. RideCloak generates a synthetic identity
  layer and attaches it to real (already-public, already-anonymized) NYC TLC trip records to
  *reconstruct the pre-anonymization input* and demonstrate the transform.
- **Why:** The public HVFHV dataset is the *output* of a privacy pipeline; the input never
  existed in our hands. Implying otherwise would be dishonest and is forbidden by SPEC §2.
- **Disclosure:** The word "synthetic" appears in README, every docstring touching the synth
  layer, every report, and the article. Correct framing: "reconstructed the pre-anonymization
  input to demonstrate the transform." Never "handled rider PII."

## L-02 — k-anonymity does not solve location privacy
- **Limitation:** k-anonymity protects against re-identification by quasi-identifier matching,
  but is known to be vulnerable to **homogeneity attacks** (all rows in an equivalence class
  share a sensitive value) and **background-knowledge attacks** (an adversary who knows side
  facts narrows the class). It says nothing about an adversary who already knows a target was
  at a place and time.
- **Why:** It is a syntactic guarantee over the released table, not a semantic privacy
  guarantee. de Montjoye et al. (2013) showed four spatiotemporal points uniquely identify 95%
  of individuals in mobility traces — generalization mitigates but does not eliminate this.
- **Disclosure:** Documented in `methodology.md`, in the per-export methodology report, and in
  the article. RideCloak presents k-anonymity as risk *reduction* with a measured before/after
  uniqueness metric, never as a solved problem. (Documented the way EdgarRisk documented its
  blind spots.)
- **Measured bound (Phase 3, full 2026-04 month, 15.4M rows):** uniqueness falls from 90.1%
  (zone x minute) to 0.06% (borough x 15-min); at zone x 15-min k=5 suppresses 85% of rows
  (zone-level k-anon is infeasible), while at borough x 15-min k=5 suppresses only 0.26%.
  Generalization, not k alone, is the lever. See [findings/phase-3.md](findings/phase-3.md).

## L-03 — Presidio does not guarantee total recall
- **Limitation:** The PII detection stage will miss some real PII spans; recall is < 100%.
- **Why:** NER/recognizer-based detection is probabilistic and pattern-bound. Novel formats,
  obfuscation, and context-dependent identifiers escape it.
- **Disclosure:** RideCloak *measures* precision/recall/F1 per entity type against the
  synthetic ground-truth labels (`labels.parquet`) and reports the real numbers. The Phase 2
  acceptance bar (recall ≥ 0.95, precision ≥ 0.90 on labeled spans) is a measured floor on the
  test set, **not** a guarantee on unseen data. The residual-risk caveat is stated wherever the
  numbers appear.
- **Measured bound — in-distribution (Phase 2, dev slice, 7,826 labeled spans across 8 entity
  types):** overall precision 0.997, recall 0.998, F1 0.998; per-entity recall >= 0.994 and
  precision >= 0.986. **These are in-distribution numbers** — the recognizers were tuned on the
  same synthetic note formats they are scored against, so this measures fit, not generalization.
- **Measured bound — held-out unseen formats (added 2026-06-12):** scored on 4,000 notes whose
  PII uses formats the recognizers were *not* built for (a format split, not a row split; a unit
  test confirms the values do not match the recognizer regexes), the **unmodified** recognizers
  fall to **overall precision 0.948, recall 0.338**. The drop is not uniform, and that is the
  point: the components not hand-built generalize (Presidio built-in EMAIL 1.00/1.00; spaCy NER
  PERSON 0.91/0.98), while every custom regex/context recognizer overfits its target format
  (PHONE, CREDIT_CARD, NY_PLATE, VEHICLE_VIN, TLC_LICENSE collapse to ~0 recall; LOCATION holds
  0.32). **Precision stays high (0.95): the failure mode is missed PII, not false alarms.** This
  is synthetic-to-synthetic — robustness across format variation we imagined, **not** a
  real-world generalization claim. See [findings/phase-2.md](findings/phase-2.md).

## L-04 — This is a demo, not production data-sharing infrastructure
- **Limitation:** RideCloak demonstrates the data-transformation and audit core. It does **not**
  implement the production operational layer: real SFTP delivery to a regulator, authentication
  and authorization, key management, network security, retention/deletion enforcement at scale,
  or live scheduling.
- **Why:** Scope is a portfolio demonstration of the privacy/validation/audit pipeline and the
  guarded AI triage pattern — not a deployable government integration.
- **Disclosure:** README "honest-scope statement" names the gap explicitly. The ledger and
  policy engine are real and verifiable; the delivery/auth surfaces are out of scope and said
  to be so.

## L-05 — TLC schema may shift; the contract is derived, not assumed
- **Limitation:** The HVFHV Parquet schema has changed over time (SPEC §5.2 notes 2025+
  `cbd_congestion_fee` and announced standardization). The field list in the SPEC is indicative,
  not authoritative.
- **Why:** TLC controls the upstream format and revises it.
- **Disclosure:** The Pandera contract is built from the **introspected** schema recorded in the
  Phase 0 findings note (`DESCRIBE` in DuckDB), not from the SPEC. Any drift is captured there
  before the contract is locked.

## L-06 — Pseudonymization is not anonymization
- **Limitation:** Salted SHA-256 pseudonyms are reversible-in-principle by anyone holding the
  salt and are linkable within a single release. They are not anonymous identifiers.
- **Why:** A keyed hash is a pseudonym (GDPR sense), not anonymized data; it reduces but does
  not erase linkage.
- **Disclosure:** `methodology.md` states the pseudonymization-vs-anonymization distinction
  explicitly. Salt rotation per export prevents cross-release joins; the erasure story
  (destroying a salt renders prior exports unlinkable) is the GDPR/CCPA narrative, documented as
  a property of the design, not a cryptographic anonymity claim.

## L-07 — LADOT framing stays neutral to both sides
- **Limitation (editorial):** The article and any narrative framing must not take a partisan
  stance in the Uber–LADOT dispute.
- **Why:** Both the regulator (legitimate claim to oversight data) and the riders (legitimate
  privacy interest) had valid positions; RideCloak's thesis is that *tooling* was the gap.
- **Disclosure:** All narrative artifacts keep the stance neutral-to-sympathetic to both sides.

---

## Metrics to backfill (replace "TBD" with measured values as phases complete)
- ~~L-03: per-entity precision / recall / F1 (Phase 2).~~ Done (see L-03).
- ~~L-02: before/after re-identification uniqueness at the chosen k (Phase 3).~~ Done (see L-02).
