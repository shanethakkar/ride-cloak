"""Render the classification + detection result to markdown (pure)."""

from __future__ import annotations

from datetime import UTC, datetime


def render_markdown(result: dict) -> str:
    """Committed-quality markdown report for `ridecloak classify`."""
    det = result["detection"]
    targets = result["targets"]
    verdict = "PASSED" if result["passed"] else "FAILED"
    lines = [
        "# RideCloak classification & PII detection report",
        "",
        f"- Source: `{result['source']}`",
        f"- Generated: {datetime.now(UTC).isoformat()}",
        f"- Notes scanned: {result['notes_scanned']:,} "
        f"({result['pii_notes']:,} PII, {result['decoy_notes']:,} decoy)",
        f"- spaCy model: `{result['model']}` | score threshold: {result['threshold']}",
        f"- Targets: recall >= {targets['recall']}, precision >= {targets['precision']}",
        f"- **Verdict: {verdict}** "
        f"(overall recall {det['overall']['recall']}, precision {det['overall']['precision']})",
        "",
        "## Field classification",
        "",
        "| tier | columns |",
        "|---|---:|",
    ]
    for tier, count in result["classification"].items():
        lines.append(f"| {tier} | {count} |")
    lines += [
        "",
        "## Detection metrics (per entity)",
        "",
        "| entity | TP | FP | FN | precision | recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for entity, m in det["per_entity"].items():
        lines.append(
            f"| {entity} | {m['tp']} | {m['fp']} | {m['fn']} | "
            f"{m['precision']} | {m['recall']} | {m['f1']} |"
        )
    o = det["overall"]
    lines.append(
        f"| **overall** | {o['tp']} | {o['fp']} | {o['fn']} | "
        f"{o['precision']} | {o['recall']} | {o['f1']} |"
    )
    lines.append("")
    return "\n".join(lines)
