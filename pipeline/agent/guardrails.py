"""Deterministic guardrails: decide the verdict from the extracted fields.

No LLM here. The verdict is a pure function of the structured request and the
classification dictionary, and it fails closed. Because the decision never reads
anything the model "said" about approval, a prompt injection that pollutes the
model's output cannot widen access; the worst it can do is request fields, which
are then evaluated against policy and refused or escalated.
"""

from __future__ import annotations

from pipeline.agent.schema import TriageDecision, TriageRequest, Verdict

# Keyword -> tier mapping for free-text field requests. Checked most-sensitive
# first, so "pickup location" reads as quasi while "home address" reads as direct.
_DIRECT_KW = (
    "name",
    "license",
    "plate",
    "vin",
    "phone",
    "telephone",
    "email",
    "payment",
    "card",
    "device",
    "rider id",
    "driver id",
    "ssn",
    "address",
    "identity",
    "identities",
)
_SENSITIVE_KW = (
    "disab",
    "wheelchair",
    "wav",
    "access-a-ride",
    "access a ride",
    "paratransit",
    "accessible",
    "support note",
    "note",
    "free text",
    "free-text",
)
_QUASI_KW = (
    "pickup",
    "drop",
    "location",
    "zone",
    "borough",
    "gps",
    "coordinate",
    "datetime",
    "timestamp",
    "time",
    "date",
    "mile",
    "distance",
    "duration",
)
_SAFE_KW = (
    "fare",
    "fee",
    "tax",
    "toll",
    "tip",
    "count",
    "number of",
    "total",
    "aggregate",
    "statistic",
    "surcharge",
    "amount",
)

_AGG_KW = (
    "count",
    "aggregate",
    "statistic",
    "total",
    "number of",
    "trend",
    "by zone",
    "by borough",
    "per zone",
    "distribution",
    "summary",
    "how many",
)
_LE_KW = (
    "investigation",
    "law enforcement",
    "police",
    "subpoena",
    "warrant",
    "court order",
    "suspect",
    "specific individual",
    "specific trip",
    "particular trip",
    "case number",
    "criminal",
)
_ROW_KW = (
    "trip record",
    "all trips",
    "full dataset",
    "row-level",
    "row level",
    "raw trip",
    "every trip",
    "complete record",
    "microdata",
)


def field_tier(field: str) -> str | None:
    """Classify a free-text requested field into a privacy tier, or None if unknown."""
    f = field.lower()
    if any(k in f for k in _DIRECT_KW):
        return "direct"
    if any(k in f for k in _SENSITIVE_KW):
        return "sensitive"
    if any(k in f for k in _QUASI_KW):
        return "quasi"
    if any(k in f for k in _SAFE_KW):
        return "safe"
    return None


def map_to_profile(parsed: TriageRequest) -> str | None:
    """Map the request's intent to a sharing profile, or None if ambiguous."""
    blob = f"{parsed.scope} {' '.join(parsed.fields)}".lower()
    if any(k in blob for k in _LE_KW):
        return "le"
    if any(k in blob for k in _AGG_KW):
        return "mds"
    if any(k in blob for k in _ROW_KW):
        return "tlc"
    return None


def evaluate(parsed: TriageRequest) -> TriageDecision:
    """Deterministic verdict from the extracted request. Fails closed."""
    tiers = [(f, field_tier(f)) for f in parsed.fields]
    direct = [f for f, t in tiers if t == "direct"]
    sensitive = [f for f, t in tiers if t == "sensitive"]
    unknown = [f for f, t in tiers if t is None]
    safe_quasi = [f for f, t in tiers if t in ("quasi", "safe")]
    profile = map_to_profile(parsed)

    # REFUSE takes precedence: raw direct identifiers never leave.
    if direct:
        return TriageDecision(
            verdict=Verdict.REFUSE,
            profile=None,
            fields_refused=direct,
            reasons=[
                f"requests raw direct identifiers ({', '.join(direct)}); "
                "RideCloak never releases identities in the clear"
            ],
        )

    # ESCALATE on anything ambiguous or special-category. Fail closed.
    escalate_reasons: list[str] = []
    if profile is None:
        escalate_reasons.append("request does not map to a known sharing profile (ambiguous)")
    if unknown:
        escalate_reasons.append(f"unrecognized fields need human classification: {unknown}")
    if sensitive:
        escalate_reasons.append(
            f"sensitive/special-category fields ({', '.join(sensitive)}) require human review"
        )
    if profile == "le" and not parsed.claimed_legal_basis:
        escalate_reasons.append("law-enforcement request states no legal basis")

    if escalate_reasons:
        return TriageDecision(
            verdict=Verdict.ESCALATE,
            profile=profile,
            fields_allowed=safe_quasi,
            fields_refused=[],
            reasons=escalate_reasons,
        )

    return TriageDecision(
        verdict=Verdict.ALLOW,
        profile=profile,
        fields_allowed=safe_quasi,
        reasons=[
            f"maps to profile '{profile}'; requested fields are within policy. "
            "Draft only — a human must approve before any export."
        ],
    )


def build_draft(parsed: TriageRequest, decision: TriageDecision) -> str:
    """Human-readable draft recommendation (echoes request text -> re-scanned)."""
    lines = [
        f"Requester: {parsed.requester}",
        f"Scope: {parsed.scope}",
        f"Verdict: {decision.verdict.value.upper()}",
        f"Recommended profile: {decision.profile or '(none)'}",
        f"Fields allowed: {', '.join(decision.fields_allowed) or '(none)'}",
        f"Fields refused: {', '.join(decision.fields_refused) or '(none)'}",
        "Reasons:",
        *[f"  - {r}" for r in decision.reasons],
        "",
        "This is a draft recommendation. No data is released by this step. A human "
        "must run `ridecloak approve` and then `ridecloak export` to share anything.",
    ]
    return "\n".join(lines)


def output_rescan(text: str) -> tuple[str, int]:
    """Second-pass Presidio scan over drafted text; redact any residual PII spans."""
    from pipeline.classify import pii_scan
    from pipeline.transform.suppress import redact_spans

    analyzer = pii_scan.build_analyzer()
    dets = pii_scan.scan_text(analyzer, text)
    if not dets:
        return text, 0
    redacted = redact_spans(text, [(d["start"], d["end"]) for d in dets])
    return redacted, len(dets)
