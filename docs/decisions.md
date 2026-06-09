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
  | k-anonymity threshold | k = 5 | Phase 3 |
  | TLC profile time bucket | 15 min | Phase 4 |
  | MDS profile time bucket | 60 min | Phase 4 |
  | First data month | most recent available (TLC ~2-month publish delay → ~2026-03/04, verify at Phase 0) | Phase 0 |
  | Additional months beyond the first | none yet | post-Phase 0 |
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
- spaCy model choice: `en_core_web_lg` vs `en_core_web_sm` fallback if download size is a
  problem; escalate if accuracy suffers (SPEC §3). → resolve in Phase 2.
