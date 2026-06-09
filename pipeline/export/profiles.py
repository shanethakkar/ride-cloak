"""Compile a validated policy into an ordered transform plan.

The plan is a list of ``{op, ...}`` steps the runner dispatches. Keeping it
declarative data (not code) is what lets a new policy run with zero code changes
and lets a test assert the exact compiled order.
"""

from __future__ import annotations

from policies.schema import OutputKind, Policy

# Row-level step order. Redaction runs first (it needs the original note text);
# k-suppression runs after generalization; the column whitelist runs last.
ROW_LEVEL_ORDER = (
    "redact_note",
    "pseudonymize",
    "generalize_time",
    "rollup_zone",
    "drop_columns",
    "kanon",
    "select",
)


def compile_policy(policy: Policy) -> list[dict]:
    """Return the ordered transform plan for a policy."""
    if policy.output_kind == OutputKind.AGGREGATE:
        a = policy.aggregate
        return [
            {
                "op": "aggregate",
                "dimensions": a.dimensions,
                "minutes": a.time_bucket_minutes,
                "k": a.k,
            }
        ]

    r = policy.row_level
    steps: dict[str, dict] = {}
    if r.redact_note:
        steps["redact_note"] = {"op": "redact_note"}
    if r.pseudonymize_columns:
        steps["pseudonymize"] = {"op": "pseudonymize", "columns": r.pseudonymize_columns}
    if r.time_bucket_minutes:
        steps["generalize_time"] = {"op": "generalize_time", "minutes": r.time_bucket_minutes}
    if r.rollup_zone:
        steps["rollup_zone"] = {"op": "rollup_zone"}
    if r.drop_columns:
        steps["drop_columns"] = {"op": "drop_columns", "columns": r.drop_columns}
    if r.kanon:
        steps["kanon"] = {"op": "kanon", "qi": r.kanon.qi, "k": r.kanon.k}
    if r.select_columns:
        steps["select"] = {"op": "select", "columns": r.select_columns}

    return [steps[name] for name in ROW_LEVEL_ORDER if name in steps]
