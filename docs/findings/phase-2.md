# Phase 2 findings — Classification & PII detection

**Status:** complete. `pytest` and `ruff` green; `ridecloak classify --input dev`
runs end to end and PASSES the targets with wide margin: **overall precision 0.997, recall
0.998, F1 0.998** (targets: recall >= 0.95, precision >= 0.90). These are **in-distribution**
numbers — the recognizers were tuned against the same synthetic note formats they are scored
on. A later format-split held-out probe (see "Held-out unseen-format evaluation" below) shows
how much of that is fit rather than generalization; read the two together.

## What was built
- **Synthetic layer extended (D-0007).** Moved the license/plate/VIN/phone format generators
  into `pipeline/synth/identifiers.py` (shared by the structured layer and the note templates),
  added three PII templates embedding `TLC_LICENSE` / `NY_PLATE` / `VEHICLE_VIN` with context
  words, and a decoy carrying a bare 7-digit "confirmation number" (a precision trap). Re-ran
  synth: 8 entity types, 7,826 labeled spans (was 5 types / 7,404).
- **`config/classification.yaml` + `dictionary.py`.** Pydantic-validated dictionary tiering all
  36 dev-slice columns (25 real + synth) direct/quasi/sensitive/safe. Disability/accessibility
  flags are `sensitive` (D-0007). A test enforces no unclassified column.
- **`recognizers.py`.** Six custom Presidio recognizers: `TLC_LICENSE` (context-gated — base
  score below threshold, only crosses it near "TLC"/"license"), `NY_PLATE`, `VEHICLE_VIN`,
  masked `CREDIT_CARD` (Presidio's built-in only matches Luhn-valid full numbers), a US `PHONE`
  pattern, and a `street_address` recognizer for the no-suffix address hard case.
- **`pii_scan.py`.** AnalyzerEngine (spaCy `en_core_web_lg`) + custom recognizers, scanning the
  free-text note only; plus an overlap **deconfliction** pass (keep highest score) that removes
  spurious overlaps. Structured columns are dictionary-classified, not scanned.
- **`evaluate.py`.** Greedy one-to-one matcher; a detection is a TP on overlap + compatible type
  (D-0007). Per-entity and micro-averaged precision/recall/F1.
- **`ridecloak classify --input dev`** writes `outputs/reports/classification_dev.{json,md}` and
  a Rich per-entity table; exits non-zero if targets are missed.

## Tuning (the real work — documented per acceptance)
1. **Baseline** (lg + license/plate/vin/card recognizers): overall P 0.847, R 0.633. Failures:
   PHONE 0.00/0.00; LOCATION recall 0.04; PERSON precision 0.74.
2. **Diagnosis 1:** Presidio's phonenumbers recognizer never fired on our formats; no-suffix
   addresses ("842 Sandra") had the street name tagged as **PERSON** by spaCy — simultaneously
   missing the LOCATION and creating the PERSON false positive.
   **Fix:** custom US-phone recognizer + a street-address recognizer scored above PERSON, plus
   overlap deconfliction. -> P 0.912, R 0.950.
3. **Diagnosis 2:** LOCATION precision 0.63, PHONE recall 0.78. Root cause: **Presidio compiles
   pattern regexes with `IGNORECASE` by default**, so the address `[A-Z][a-z]+` matched
   lowercase tokens ("9 minutes", "8143 about"). Those high-scoring bogus LOCATION spans then
   deconflicted away the real phone numbers (e.g. the "8143" tail of a phone). One bug, two
   symptoms.
   **Fix:** case-sensitive flags (`re.MULTILINE | re.DOTALL`) on the address recognizer.
   -> overall **P 0.997, R 0.998**.

## Final metrics (dev slice, 4,952 notes: 3,702 PII + 1,250 decoy)
| entity | precision | recall | F1 |
|---|---:|---:|---:|
| CREDIT_CARD | 1.000 | 1.000 | 1.000 |
| EMAIL_ADDRESS | 1.000 | 1.000 | 1.000 |
| LOCATION | 0.986 | 1.000 | 0.993 |
| NY_PLATE | 1.000 | 1.000 | 1.000 |
| PERSON | 0.999 | 0.994 | 0.996 |
| PHONE_NUMBER | 0.999 | 0.999 | 0.999 |
| TLC_LICENSE | 1.000 | 1.000 | 1.000 |
| VEHICLE_VIN | 1.000 | 1.000 | 1.000 |
| **overall** | **0.997** | **0.998** | **0.998** |

## Held-out unseen-format evaluation (added 2026-06-12)

A reviewer pointed out the table above is **in-distribution**: the recognizers were tuned on the
same synthetic note formats they are scored against, so 0.997/0.998 measures fit, not
generalization. To probe generalization I built a **format-split** held-out set
(`pipeline/classify/heldout.py`) — notes whose PII uses shapes the recognizers were *not* built
for: slash- and 2-2-grouped phones (`212/555/1234`, `212 555 12 34`), numbered-ordinal and bare
neighborhood locations (`200 5th Avenue`, `Astoria`), bullet/grouped-star masked cards
(`•••• 1234`, `****-****-****-1234`), spaced plates and VINs — plus a TLC **context** probe (same
6-7 digit shape, no trigger words). A unit test asserts these values do not match the recognizer
regexes, so the set is genuinely unseen format, not relabeled training data. The **unmodified**
Phase-2 recognizers are then scored on 4,000 such notes.

Reproduce: `uv run python -c "from pipeline.classify import heldout, pii_scan, evaluate; t,g =
heldout.generate_heldout(4000, seed=2026); a = pii_scan.build_analyzer();
print(evaluate.evaluate(pii_scan.scan_texts(a, t), g)['overall'])"`

| entity | in-dist P/R | held-out P/R | what carries it |
|---|---:|---:|---|
| EMAIL_ADDRESS | 1.000 / 1.000 | **1.000 / 1.000** | Presidio built-in |
| PERSON | 0.999 / 0.994 | **0.906 / 0.982** | spaCy NER |
| LOCATION | 0.986 / 1.000 | 0.935 / **0.317** | NER (names) vs custom regex (streets) |
| PHONE_NUMBER | 0.999 / 0.999 | 1.000 / **0.002** | custom regex — overfit |
| CREDIT_CARD | 1.000 / 1.000 | **0.000 / 0.000** | custom regex — overfit |
| NY_PLATE | 1.000 / 1.000 | **0.000 / 0.000** | custom regex — overfit |
| TLC_LICENSE | 1.000 / 1.000 | **0.000 / 0.000** | context recognizer — overfit |
| VEHICLE_VIN | 1.000 / 1.000 | **0.000 / 0.000** | custom regex — overfit |
| **overall** | **0.997 / 0.998** | **0.948 / 0.338** | |

**What this shows — a clean, unflattering split:**
- The components I did **not** hand-build generalize: Presidio's built-in **EMAIL** holds at
  1.00/1.00 and spaCy's NER **PERSON** at 0.91/0.98.
- Every **custom regex/context recognizer overfit** to the formats it was written against. PHONE,
  CREDIT_CARD, NY_PLATE, VEHICLE_VIN, and TLC_LICENSE collapse to ~0 recall on the new shapes;
  LOCATION holds 0.32 recall only because NER catches the neighborhood names while the
  numbered-street regex misses the addresses.
- **Precision stays high (0.95).** The failure mode is **silence (missed PII), not false alarms** —
  which in a privacy tool is the dangerous direction: a silent miss leaks, a false alarm only
  over-redacts.

**Why not re-tune to close the gap.** Broadening the regexes to cover these specific shapes and
re-scoring on the same held-out set would just move the leakage up a level (fitting the held-out
formats). The honest read is architectural, not a number to be optimized: learned/statistical
components (NER, Presidio) degrade gracefully under format drift; brittle hand-tuned regexes do
not. The production posture is to treat the generalizing components as the recall backbone and the
custom regexes as high-precision adjuncts — recorded here, not silently patched.

**Caveat (binding).** This is synthetic-to-synthetic. It measures robustness across format
variation *I imagined*, not real-world performance, and is **not** a real-world generalization
figure (limitations.md L-03).

## Acceptance criteria — all met
1. `classify --input dev` writes a per-entity precision/recall report (JSON + markdown) ✅
2. recall >= 0.95 and precision >= 0.90 on labeled spans (0.998 / 0.997), tuning documented ✅
3. test enforces every schema column appears in classification.yaml ✅. 51 tests pass, ruff clean.

## Decisions / notes
- **Setup step:** the spaCy model is not a pinned dependency; install it with
  `uv run python -m spacy download en_core_web_lg` (documented for reproduce/README).
- **`classify` is dev-scoped on purpose.** Detection metrics require ground-truth labels, which
  exist only for the synthetic dev slice; classifying a full month's free text has no labels to
  measure against, so `--input` accepts only `dev`.
- These are in-distribution numbers on the labeled synthetic set, **not** a guarantee on unseen
  data. The held-out section above quantifies the drop on unseen formats (overall recall
  0.998 -> 0.338); limitations.md L-03 carries the honest summary.

## Open questions for later phases
- Phase 3: direct identifiers in `support_note` should be suppressed/redacted on export using
  these detections (Presidio anonymizer or our own); confirm redaction vs whole-field drop.
