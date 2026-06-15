# Decisions Log

**Role of this file.** A chronological, lightweight record of every project decision and its
rationale. It is the running index over the heavier `docs/adr/` directory: routine or
fast-moving calls live here as dated entries; a genuinely non-trivial architectural decision
gets a full ADR in `docs/adr/` and is cross-linked from here.

**How and when to update.** Append a new entry the moment a decision is made or an open
question is resolved — do not batch them. Never rewrite history: if a decision is reversed,
add a new entry that supersedes the old one and mark the old one `Superseded`. Each entry:
date, status, the decision, why, and any alternatives considered.

Statuses: `Accepted` · `Open` (decision deferred, default noted) · `Superseded`.

---

## D-0001 — Project name is RideCloak
- **Date:** 2026-06-09
- **Status:** Accepted
- **Decision:** The project is named **RideCloak**. The Click CLI entrypoint is `ridecloak`;
  the package, README, and all user-facing strings use RideCloak. The repo folder
  (`ride-cloak`) already matched this; the SPEC's working name "SafeHarbor" is retired.
- **Why:** SPEC §2 lists renaming as a decision Shane must make. The repo was already created
  as `ride-cloak`, and Shane confirmed RideCloak. Locking it now avoids a later rename touching
  the CLI entrypoint, package metadata, and every doc.
- **Affects:** CLI entrypoint, `pyproject.toml` project name, README, every reference in SPEC
  examples that says `safeharbor` (translate to `ridecloak` at implementation time). The SPEC
  text itself stays as-is (historical source of truth); new artifacts use RideCloak.
- **Alternatives:** Keep "SafeHarbor" (rejected — diverges from the repo folder); defer naming
  (rejected — it gates the CLI entrypoint and scaffolding).

## D-0002 — Living-documentation layer, structured per Claude Code best practice
- **Date:** 2026-06-09
- **Status:** Accepted
- **Decision:** Maintain four living docs in `docs/` — `decisions.md`, `limitations.md`,
  `methodology.md`, `plan.md` — indexed from a lean root `CLAUDE.md`. `CLAUDE.md` links the
  docs with one-line descriptions for read-on-demand rather than bulk-importing them.
- **Why:** Claude Code loads `CLAUDE.md` into context every turn, so it must stay short
  (~under 200 lines); detailed material belongs in separate, self-describing files referenced
  from it. This keeps institutional memory in-repo for any future agent or human without
  bloating per-turn context. (Source: Claude Code memory/best-practices docs.)
- **Relationship to SPEC docs:** These four complement — do not replace — the SPEC's prescribed
  `docs/adr/` (full ADRs for non-trivial design decisions) and `docs/findings/phase-N.md`
  (per-phase build notes). `decisions.md` is the dated rollup over `docs/adr/`; `methodology.md`
  is the project-level narrative, distinct from per-export auto-generated reports under
  `outputs/reports/`.
- **Alternatives:** Single large CLAUDE.md (rejected — context bloat); docs at repo root
  (rejected — `docs/` keeps them beside SPEC.md/adr/findings); collapse ADRs into decisions.md
  (rejected — SPEC explicitly wants full ADRs for non-trivial design decisions).

## D-0003 — SPEC escalation defaults deferred per-phase
- **Date:** 2026-06-09
- **Status:** Open
- **Decision:** The SPEC §2 escalation parameters are **not** finalized now. Each is decided
  when its phase needs it, using the SPEC default until Shane confirms. Tracked below.
- **Why:** These are privacy-policy and data-scope choices best made with the phase's real
  data in hand (e.g. observed equivalence-class sizes inform the final k). Building them as
  policy parameters (per SPEC) means the defaults are safe to develop against.
- **Open parameters and their working defaults:**
  | Parameter | Working default | Decided in |
  |---|---|---|
  | k-anonymity threshold | k = 5 | **Resolved D-0008** (default; final per-profile in Phase 4) |
  | TLC profile time bucket | 15 min | **Resolved D-0009** |
  | MDS profile time bucket | 60 min | **Resolved D-0009** (borough geography) |
  | First data month | most recent available (TLC ~2-month publish delay → ~2026-03/04, verify at Phase 0) | Phase 0 |
  | Additional months beyond the first | 2026-01 .. 2026-04 | **Resolved D-0012** (Phase 7 trends) |
- **How to close:** When a phase consumes one of these, confirm the value with Shane, then add
  a new `Accepted` decision entry recording the final value and the data that justified it.

## D-0004 — First data month is 2026-04
- **Date:** 2026-06-09
- **Status:** Accepted
- **Decision:** The first (and currently only) ingested month is **2026-04**. The dev slice
  derives from it (`settings.dev_source_month`).
- **Why:** At Phase 0 (2026-06-09) it was the most recent published HVFHV month — 2026-05
  returned HTTP 403 (not yet released), consistent with TLC's ~2-month publishing delay.
- **Facts:** 20,995,953 total rows; HV0003 (Uber) = 15,378,858 rows (73.2%, within the
  expected 70–75%); file SHA-256 `15525aea9f82…`. Introspected schema = the expected 25 columns
  including `cbd_congestion_fee`, **no drift** (recorded in
  [findings/phase-0.md](findings/phase-0.md) and `data/raw/manifests/schema_2026-04.json`).
- **Closes:** the "first data month" row of D-0003. Additional months remain Shane's call (D-0003).

## D-0006 — Phase 1 validation: two-tier gate, equal-weighted health score
- **Date:** 2026-06-09
- **Status:** Accepted
- **Decision:** Validation is two-tier. **Tier 1 (hard)** is the Pandera contract — column
  presence, dtypes, and value domains; any violation fails validation outright. **Tier 2
  (soft)** is the 0-100 health score over four equally weighted dimensions (completeness,
  validity, consistency, uniqueness, 25 each); the configurable gate (default 90) refuses
  export below threshold. Legitimate real-data anomalies (e.g. 89 negative `base_passenger_fare`
  rows = 0.036%, rare `trip_time` outliers) are **validity/consistency dings, not hard
  failures**, so clean published data passes its own gate while injected corruption drops it.
- **Why:** Profiling 2026-04 showed the published data is the clean pipeline *output* (zero
  nulls, zero out-of-range zones, zero dup rows) but carries genuine refund/adjustment negatives.
  A strict hard-fail would wrongly reject real data; an all-soft model would lose the structural
  guarantee. Two-tier keeps both. Equal weights are the most defensible/explainable choice.
- **Calibration:** the contract's nullable flags and per-column null-rate thresholds are set
  from a **full-month** (~21M row) profile, not the 250K sample (which showed 0 nulls and is
  optimistic for known-optional columns). Recorded in the Phase 1 findings note.
- **Alternatives:** strict hard-fail (rejected — fails real data, needs a quarantine step);
  all-soft (rejected — drops the structural guarantee); weighted-toward-correctness (deferred —
  equal is the baseline; revisit if a dimension proves uninformative).

## D-0014 — Public-facing framing stays neutral toward Uber
- **Date:** 2026-06-15
- **Status:** Accepted
- **Decision:** Public artifacts (README, and by extension the shanethakkar.com article) describe
  the oversight-vs-privacy tension without casting Uber as an antagonist. The 2020 LA / Mobility
  Data Specification episode is framed as ride-hail operators pressing a legitimate rider-privacy
  concern, with the regulator's oversight interest treated as equally legitimate. References to
  "Uber trips" / "filter to Uber" stay — they are factual data-scope (the HVFHV dataset filtered
  to Uber records), not a value judgment. README "Why this exists" was reworded accordingly.
- **Why:** Shane's request — the repo is a public, recruiter-facing portfolio piece and must never
  read as anti-Uber. The privacy-defender framing is also historically accurate: in that dispute
  the operators argued *for* rider privacy.
- **Affects:** `README.md` "Why this exists" and the live article (`/articles/ridecloak`), which
  got the same treatment: title changed to "I Built the Missing Piece of the Ride-Hail Data Fight"
  and the opening reframed — Uber presented as the privacy advocate, the "lost its appeal and
  complied" framing dropped, "dumping vehicles in poor neighborhoods" softened. Homepage card +
  `CONTEXT.md` title updated to match.
- **Alternatives:** Drop the Uber/MDS reference entirely (rejected — it is the genuine motivation
  and anchors the article; neutral framing reaches the goal without losing the hook).

## D-0013 — Phase 2 PII metrics reported in- *and* out-of-distribution; not re-tuned
- **Date:** 2026-06-12
- **Status:** Accepted
- **Context:** A reviewer noted the headline 0.997/0.998 is in-distribution — the recognizers
  were tuned against the same synthetic note formats they are scored on, so the number measures
  fit, not generalization.
- **Decision:** Build a **format-split** held-out evaluation (`pipeline/classify/heldout.py`):
  notes whose PII uses formats the recognizers were never built for, with a unit test asserting
  the held-out values do not match the recognizer regexes (a real format split, not a row split).
  Score the **unmodified** recognizers on it and **report both numbers**, leading with the split
  between generalizing components (Presidio built-in EMAIL, spaCy NER PERSON) and the overfit
  hand-tuned regexes. **Do not re-tune** the recognizers to recover the held-out recall.
- **Result:** held-out overall precision 0.948, recall 0.338 (vs in-dist 0.997/0.998). EMAIL
  1.0/1.0 and PERSON 0.91/0.98 hold; PHONE/CREDIT_CARD/NY_PLATE/VEHICLE_VIN/TLC_LICENSE collapse
  to ~0 recall; LOCATION 0.32. Precision stays high — the failure mode is missed PII, not false
  alarms. Synthetic-to-synthetic; not a real-world generalization claim.
- **Why not re-tune:** broadening the regexes to the held-out shapes and re-scoring the same set
  just moves the leakage up a level (fitting the held-out formats). The honest finding is
  architectural — learned/statistical components degrade gracefully under format drift, brittle
  hand-tuned regexes do not — and is more valuable reported than optimized away.
- **Affects:** [findings/phase-2.md](findings/phase-2.md) (method + both tables),
  [limitations.md](limitations.md) L-03, README, resume-context, article-draft. The Phase-2
  recognizers and `evaluate.py` are unchanged.

## D-0012 — Phase 7 dashboard extracts: multi-month + bundled figures
- **Date:** 2026-06-09
- **Status:** Accepted (closes the D-0003 "additional months" row)
- **Decisions:**
  1. **Ingest 4 months — 2026-01 .. 2026-04** — and run the scale-path stages
     (`validate`/`risk`/`export --profile mds`) on `--input month` for each, so the dashboard
     shows real *trends* and the headline "N million Uber trips across M months" is true. Row-level
     TLC/LE exports stay on 2026-04 (the synthetic identity layer lives only there).
  2. **Bundle figure generation into Phase 7** — a `ridecloak figures` step emits committed
     matplotlib PNGs (uniqueness before/after, detection precision/recall, month trends,
     equivalence-class distribution) from the same extracts, ready for the article + the video.
- **Why:** trends and a real "M months" number are what convey the scope to recruiters; the
  figures share the dashboard's data and the video (next) needs them, so building them now is
  efficient. (`uv add matplotlib`.)
- **Ledger note:** the multi-month scale commands append to the existing append-only ledger
  (chain stays valid); the dashboard reads the accumulated trail.

## D-0011 — Phase 6 AI triage agent with guardrails
- **Date:** 2026-06-09
- **Status:** Accepted
- **Decisions:**
  1. **Triage model = `claude-sonnet-4-6`** (configurable via `settings.triage_model`). The LLM
     only *extracts* a free-text request into a structured form; the policy decision is
     deterministic code, so Sonnet is ample and ~40% cheaper than Opus (~$0.024/call).
  2. **Skip Phase 6b** (Streamlit approval console) — the SPEC's designated first cut. The
     approval queue + fail-closed flow are fully exercised via the CLI.
  3. **Architectural draft-only (the core invariant):** the LLM output is *untrusted input*. It
     never decides policy and `pipeline/agent/` has **no import of `pipeline.export.runner`**
     (grep-enforced by a test). The deterministic guardrail layer derives the verdict from the
     *extracted fields*, ignoring anything the model says about "approval" — so a prompt
     injection that makes the model emit "approve everything" changes nothing, and even an
     `allow` verdict only produces a draft + a pending request a human must `approve` before any
     `export`.
  4. **Cost/test posture:** the ≥10-request guardrail suite (in-policy / out-of-policy /
     ambiguous / injection) runs **offline** against the deterministic guardrails with stubbed
     parses — no API key, no cost, CI-safe. Only a small, skippable smoke test makes a live
     Sonnet call when a key is present.
- **Why:** the responsible-AI thesis is that safety is *deterministic code, not prompt text*;
  Sonnet keeps the live cost trivial; offline tests keep CI free and fast.
- **Key handling:** `RIDECLOAK_ANTHROPIC_API_KEY` in `.env` (gitignored) →
  `settings.anthropic_api_key`, passed explicitly to the SDK; never logged.

## D-0010 — Phase 5 attestation ledger
- **Date:** 2026-06-09
- **Status:** Accepted
- **Decisions:**
  1. **Every command appends a hash-chained entry** (fetch, synth, validate, classify, risk,
     export, approve) — one provenance chain from ingest to release (SPEC literal).
  2. **Operator label = a generic service id** (`ridecloak-pipeline`), configurable via
     `RIDECLOAK_OPERATOR`. Keeps a local username out of the committed/public ledger.
  3. **The ledger entry embeds the full export audit** (a superset of the SPEC §7 fields:
     adds columns_shared/withheld, gate score, generated_utc, refused/reason). The methodology
     report is then a pure function of the entry, so it **regenerates byte-identically** from the
     ledger entry, and the whole entry is hash-protected.
  4. `entry_hash = sha256(canonical_json(entry without entry_hash))`, chained via
     `prev_entry_hash`; genesis `prev_entry_hash = "0"*64`. Append-only JSONL at
     `outputs/ledger/ledger.jsonl` (committed showcase artifact).
- **Why:** full provenance is the strongest audit story and matches the SPEC; a generic operator
  avoids leaking a personal username into a public artifact; embedding the audit makes the
  byte-identical regeneration structural rather than fragile.
- **Note:** the ledger is append-only by design (the one non-idempotent artifact); the reproduce
  script resets it at the start of a canonical run.

## D-0009 — Phase 4 export profiles
- **Date:** 2026-06-09
- **Status:** Accepted (closes the D-0003 time-bucket row)
- **Decisions:**
  1. **Per-profile parameters (escalation #2 confirmed).**
     - **TLC trip submission** — row-level; direct identifiers pseudonymized; `pickup_datetime`
       rounded to **15 min**; support_note PII spans redacted; **zone-level location kept**; full
       fare fields; **no k-suppression** (mirrors the real mandated row-level submission).
     - **MDS aggregate** — count-per-cell over **borough × borough × 60 min**, **k=5** small-cell
       suppression. (Recommendation: zone-level is the SPEC literal but suppresses 87% of cells,
       leaving a near-useless aggregate; borough retains ~all rows while k=5 still fires at 17%
       of cells. Zone is one YAML change away; the 87% finding is documented in methodology.)
     - **LE extract** — minimal trip-scoped fields (pseudonymized trip key + zone/time), requires
       an approval record to run.
  2. **Row-level exports (TLC, LE) operate on the dev slice**, because the reconstructed
     synthetic identity layer (the columns being pseudonymized/redacted) only exists there. The
     **MDS aggregate** needs no PII and can run on the dev slice or the **full month via SQL**.
  3. **LE approval & SPEC §13.** Build `ridecloak approve` (writes an approval record) and the
     runner's fail-closed gate, but **Claude never invokes `approve`** (human-only act). The
     committed showcase artifact is the **fail-closed refusal**; the with-approval happy path is
     exercised in tests (a fixture writes the approval). Shane runs `approve` for a real LE export.
  4. **Policy language is declarative.** The pydantic policy schema + compiler express all three
     profiles from YAML; a toy fourth policy produces an export with **zero code changes** (tested).
- **Why:** keeps the privacy parameters as policy not code; grounds MDS geography in the Phase 3
  sparsity finding; honors the human-only approval boundary; satisfies "new regulator = new YAML".

## D-0008 — Phase 3 transform engine & the zone-level k-anonymity finding
- **Date:** 2026-06-09
- **Status:** Accepted (k default closes the D-0003 k row)
- **Headline finding (profiled on the dev slice).** Raw zone-level trip data **cannot be
  k-anonymized without generalization**: uniqueness on PU×DO zone × pickup time is 99.8%
  (minute), 97.1% (15-min), 90.4% (60-min); k=5 on that QI suppresses ~100% of rows. Rolling
  zones up to **borough** collapses uniqueness to 5.4% (15-min) / 1.1% (60-min), making k-anon
  viable: k=5 then costs ~23% (15-min) / ~4.7% (60-min) suppression. **Generalization is the
  primary privacy lever; k-anonymity is applied after generalization.** This is the de Montjoye
  result made concrete and the spine of the article.
- **Decisions:**
  1. **k = 5 default** (configurable param; the final per-profile k is set in Phase 4).
  2. **`risk` default QI = PU×DO zone × 15-min** (SPEC default). The command reports the full
     ladder (minute → 15-min → 60-min → borough) so the ~100% zone-level suppression is shown
     honestly as the core finding, not hidden behind a pre-generalized default.
  3. **support_note → redact detected PII spans** on export: build a redaction transform that
     masks the Presidio-detected spans in place (integrates Phase 2 detection into the transform
     pipeline), keeping non-PII text. (A second-pass re-scan of agent output is a Phase 6
     guardrail.)
  4. **k-suppression = drop records** in classes smaller than k (record suppression);
     `cells_suppressed` = rows removed.
  5. **Pseudonymization = salted SHA-256**, one salt generated per export run, stored only in
     `secrets/salts/` (gitignored), referenced in the ledger by SHA-256 **fingerprint** of the
     salt. Same salt → same pseudonyms (joinable within a release); different salt → disjoint.
- **Why:** the profiling shows k alone is not the lever (zone granularity dominates); honesty
  rules require showing the stark zone-level result rather than masking it; redaction showcases
  the detection→transform link and is the strongest demo; record-drop is the standard k-anon
  mechanism for row-level releases.

## D-0007 — Phase 2 classification & PII detection design
- **Date:** 2026-06-09
- **Status:** Accepted
- **Decisions:**
  1. **Extend the synthetic support notes** to embed TLC-license, NY-plate, and VIN spans (with
     realistic context words), regenerating the dev slice + labels. This makes the three custom
     recognizers measurable against ground truth so "extended Presidio and measured/closed the
     detection gap" is an honest, quantified claim — not just structured-column tagging. This
     revises the Phase 0 support-note scope (was 5 entity types: PERSON, PHONE_NUMBER,
     EMAIL_ADDRESS, LOCATION, CREDIT_CARD; now 8, adding TLC_LICENSE, NY_PLATE, VEHICLE_VIN).
     The dev-slice hash changes; determinism (same seed = same hash) still holds.
  2. **spaCy model: `en_core_web_lg`** backs Presidio NER (SPEC default; best non-transformer
     accuracy for the PERSON/LOCATION recall ≥ 0.95 target). Closes the Phase 0/SPEC §3 open item.
  3. **Disability/accessibility flags are `sensitive`** in classification.yaml:
     `access_a_ride_flag`, `wav_request_flag`, `wav_match_flag` (GDPR special-category-adjacent).
     The shared-ride flags stay `safe`.
  4. **Detection scoring = overlap + compatible entity type** (any character overlap counts as a
     true positive). Standard in PII-eval literature; tolerant of boundary/tokenization jitter.
- **Why:** (1) without the formats in free text the recognizers are untestable; (2) recall
  target needs the stronger model; (3) accessibility status is a genuine privacy dimension;
  (4) exact-boundary matching understates real performance and is brittle to tokenization.
- **Implementation note:** extending the synth touches the Phase 0 generator/templates — handled
  as the first step of Phase 2, with `ridecloak synth --input dev` re-run. Custom-recognizer
  entity types: `TLC_LICENSE`, `NY_PLATE`, `VEHICLE_VIN`.

## D-0005 — labels.parquet stays under gitignored data/synth/ (not committed)
- **Date:** 2026-06-09
- **Status:** Accepted
- **Decision:** Do not commit `labels.parquet`; it lives under gitignored `data/synth/`.
- **Why:** It is fully reproducible from the committed generator + seed (`ridecloak synth`), so
  committing it adds binary churn for no recoverability gain. SPEC §6 left this conditional on
  size; reproducibility, not size, is the deciding factor. Revisit only if a consumer needs it
  without running synth.

---

## Pending / unresolved questions
_Move these into numbered decisions as they resolve._

- ~~TLC Parquet schema may have shifted.~~ **Resolved (Phase 0):** introspected schema = the
  expected 25 columns, no drift; recorded in `data/raw/manifests/schema_2026-04.json`. Phase 1
  builds the Pandera contract from that file.
- ~~Whether `data/synth/labels.parquet` is committed.~~ **Resolved:** D-0005 (not committed,
  reproducible from seed).
- ~~spaCy model choice.~~ **Resolved:** D-0007 — `en_core_web_lg`.
