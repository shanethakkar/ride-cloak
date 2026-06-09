"""Render the per-export methodology report (pure).

Documents what was shared, what was withheld, why, and under which policy
version. The renderer reads only audit fields, so it produces identical output
whether handed the in-memory export audit or the ledger entry that embeds it —
which is what makes the report regenerate byte-identically from the ledger.
"""

from __future__ import annotations


def render_markdown(result: dict) -> str:
    """Committed-quality methodology report for one export run / ledger entry."""
    lines = [
        f"# RideCloak methodology report — {result['policy_name']} v{result['policy_version']}",
        "",
        f"- Source: `{result['source']}`",
        f"- Generated: {result['generated_utc']}",
        f"- Output kind: {result['output_kind']}",
        f"- Policy hash: `{result['policy_hash'][:16]}...`",
    ]

    if result["refused"]:
        lines += [
            "- **Status: REFUSED (fail-closed)**",
            "",
            "## Refusal",
            "",
            f"No export was produced. Reason: {result['reason']}",
            "",
        ]
        return "\n".join(lines)

    gate = result["gate"]
    lines += [
        f"- Health score: {gate['health_score']} (gate passed)",
        f"- Salt fingerprint: `{result['salt_fingerprint']}`",
        f"- Output: `{result['output_path']}`",
        f"- Output SHA-256: `{result['output_hash'][:16]}...`",
        "",
        "## Volume",
        "",
        f"- Rows in: {result['rows_in']:,}",
        f"- Rows out: {result['rows_out']:,}",
        f"- Cells suppressed: {result['cells_suppressed']:,}",
    ]
    if result.get("k_achieved") is not None:
        lines.append(f"- k achieved: {result['k_achieved']}")
    if "cells_out" in result:
        lines.append(
            f"- Aggregate cells: {result['cells_out']:,} of {result['cells_in']:,} retained"
        )

    lines += [
        "",
        "## What was shared",
        "",
        ", ".join(f"`{c}`" for c in result["columns_shared"]) or "(none)",
        "",
        "## What was withheld",
        "",
        ", ".join(f"`{c}`" for c in result["columns_withheld"]) or "(none)",
        "",
        "## Transforms applied (in order)",
        "",
    ]
    for t in result["transforms"]:
        detail = ", ".join(f"{k}={v}" for k, v in t.items() if k != "op")
        lines.append(f"- **{t['op']}**" + (f" — {detail}" if detail else ""))
    lines.append("")
    return "\n".join(lines)
