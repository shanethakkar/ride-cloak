"""Render a validation report dict to human-readable markdown (pure)."""

from __future__ import annotations

from datetime import UTC, datetime

from pipeline.validate.health import DIMENSIONS


def render_markdown(report: dict) -> str:
    """Return a committed-quality markdown certification report."""
    verdict = "REFUSED" if report["refused"] else "PASSED"
    lines = [
        "# RideCloak validation report",
        "",
        f"- Source: `{report['source']}`",
        f"- Generated: {datetime.now(UTC).isoformat()}",
        f"- Rows: {report['rows']:,}" if report["rows"] is not None else "- Rows: n/a",
        f"- Gate threshold: {report['gate_threshold']}",
        f"- **Verdict: {verdict}**",
        "",
    ]

    if not report["tier1_passed"]:
        lines += [
            "## Tier-1 structural contract: FAILED",
            "",
            "The data violates the structural contract and cannot be scored.",
            "",
            "| column | check | rows |",
            "|---|---|---:|",
        ]
        for f in report["structural_failures"]:
            lines.append(f"| {f['column']} | {f['check']} | {f['count']:,} |")
        lines.append("")
        return "\n".join(lines)

    lines += [
        "## Tier-1 structural contract: PASSED",
        "",
        f"## Health score: {report['health_score']} / 100",
        "",
        "| dimension | score (of 100) |",
        "|---|---:|",
    ]
    for dim in DIMENSIONS:
        lines.append(f"| {dim} | {report['dimensions'][dim]} |")
    lines.append("")

    counts = report.get("counts")
    if counts:
        lines += ["## Quality detail", ""]
        comp = counts["completeness"]
        lines.append(
            f"- Completeness: {comp['null_cells']:,} null cells of "
            f"{comp['total_cells']:,} ({_pct(comp['null_cells'], comp['total_cells'])})"
        )
        lines.append(f"- Validity: {counts['validity']['fail_rows']:,} rows fail a value rule")
        lines.append(
            f"- Consistency: {counts['consistency']['fail_rows']:,} rows fail a cross-field rule"
        )
        lines.append(f"- Uniqueness: {counts['uniqueness']['duplicate_rows']:,} duplicate rows")
        lines.append("")
        firing = _firing_rules(counts)
        if firing:
            lines += ["### Rules that fired", "", "| rule | rows |", "|---|---:|"]
            for name, count in firing:
                lines.append(f"| {name} | {count:,} |")
            lines.append("")

    return "\n".join(lines)


def _firing_rules(counts: dict) -> list[tuple[str, int]]:
    firing: list[tuple[str, int]] = []
    for dim in ("validity", "consistency"):
        for name, count in counts[dim].get("rules", {}).items():
            if count > 0:
                firing.append((name, count))
    return firing


def _pct(num: int, denom: int) -> str:
    return "0.000%" if denom == 0 else f"{num / denom:.3%}"
