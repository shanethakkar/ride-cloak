"""0-100 health score and the export gate.

Four equally weighted dimensions (completeness, validity, consistency,
uniqueness — 25 points each; decisions.md D-0006). Each dimension subscore is
``100 * (1 - fail_rate)``. The composite is their mean; the configurable gate
threshold (default 90) decides whether export is refused. A Tier-1 structural
failure short-circuits to a refusal with no numeric score.
"""

from __future__ import annotations

from pipeline.validate import checks, contract

DIMENSIONS = ("completeness", "validity", "consistency", "uniqueness")


def _round(value: float) -> float:
    return round(value, 4)


def score_dimensions(counts: dict) -> dict[str, float]:
    """Map Tier-2 counts to the four 0-100 dimension subscores."""
    n = counts["n"]
    comp = counts["completeness"]
    total_cells = comp["total_cells"]

    completeness = 100.0 if total_cells == 0 else 100.0 * (1 - comp["null_cells"] / total_cells)
    if n == 0:
        validity = consistency = uniqueness = 100.0
    else:
        validity = 100.0 * (1 - counts["validity"]["fail_rows"] / n)
        consistency = 100.0 * (1 - counts["consistency"]["fail_rows"] / n)
        uniqueness = 100.0 * (1 - counts["uniqueness"]["duplicate_rows"] / n)

    return {
        "completeness": _round(completeness),
        "validity": _round(validity),
        "consistency": _round(consistency),
        "uniqueness": _round(uniqueness),
    }


def composite(dimensions: dict[str, float]) -> float:
    """Equal-weighted mean of the four dimension subscores."""
    return _round(sum(dimensions[d] for d in DIMENSIONS) / len(DIMENSIONS))


def _assemble(tier1: dict, counts: dict | None, gate_threshold: int, source: str) -> dict:
    if not tier1["passed"]:
        return {
            "source": source,
            "tier1_passed": False,
            "structural_failures": tier1["failures"],
            "rows": counts["n"] if counts else None,
            "dimensions": None,
            "health_score": None,
            "gate_threshold": gate_threshold,
            "refused": True,
            "reason": "Tier-1 structural contract violation",
        }
    dimensions = score_dimensions(counts)
    score = composite(dimensions)
    refused = score < gate_threshold
    return {
        "source": source,
        "tier1_passed": True,
        "structural_failures": [],
        "rows": counts["n"],
        "dimensions": dimensions,
        "health_score": score,
        "gate_threshold": gate_threshold,
        "refused": refused,
        "reason": None if not refused else f"health score {score} below gate {gate_threshold}",
        "counts": counts,
    }


def build_report(df, gate_threshold: int, source: str = "dev") -> dict:
    """Full validation report for an in-memory DataFrame (the dev path)."""
    tier1 = contract.validate_contract(df)
    if not tier1["passed"]:
        return _assemble(tier1, {"n": len(df)}, gate_threshold, source)
    counts = checks.quality_counts(df)
    return _assemble(tier1, counts, gate_threshold, source)


def build_report_from_counts(counts: dict, gate_threshold: int, tier1: dict, source: str) -> dict:
    """Validation report from pre-aggregated counts (the month/scale path)."""
    return _assemble(tier1, counts, gate_threshold, source)
