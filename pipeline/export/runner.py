"""Execute a compiled policy plan and emit an export plus a methodology report.

Fails closed: if the validation gate refuses the input, or an approval-gated
profile has no approval, no export is written and a refusal is logged. The audit
dict returned carries the fields the Phase 5 ledger records.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from config.settings import Settings
from pipeline.export import report
from pipeline.export.profiles import compile_policy
from pipeline.io import approvals, salts, writers
from pipeline.transform import generalize, kanon, pseudonymize, suppress
from pipeline.transform.pseudonymize import salt_fingerprint
from pipeline.validate import health
from policies.schema import OutputKind, Policy

NoteDetector = Callable[[list], list[list[dict]]]
_PSEUDO_NULL_FP = "n/a"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _resolve_dimensions(
    df: pd.DataFrame, tokens: list[str], lookup: dict[int, str], minutes: int
) -> pd.DataFrame:
    """Build the named dimension columns referenced by an aggregate policy."""
    cols: dict[str, pd.Series] = {}
    for token in tokens:
        if token == "PUBorough":
            cols[token] = generalize.rollup_zone(df["PULocationID"], lookup)
        elif token == "DOBorough":
            cols[token] = generalize.rollup_zone(df["DOLocationID"], lookup)
        elif token == "pickup_bucket":
            cols[token] = generalize.round_time(df["pickup_datetime"], minutes)
        elif token == "dropoff_bucket":
            cols[token] = generalize.round_time(df["dropoff_datetime"], minutes)
        elif token in df.columns:
            cols[token] = df[token]
        else:
            raise ValueError(f"Unknown aggregate dimension: {token}")
    return pd.DataFrame(cols)


def _run_row_level(
    df: pd.DataFrame, plan: list[dict], salt: bytes, lookup: dict[int, str], detector: NoteDetector
) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    audit = {"transforms": [], "rows_in": len(df), "cells_suppressed": 0, "k_achieved": None}
    for step in plan:
        op = step["op"]
        if op == "redact_note":
            dets = detector(out["support_note"].tolist())
            out["support_note"], red = suppress.redact_series(out["support_note"], dets)
            audit["transforms"].append({"op": op, **red})
        elif op == "pseudonymize":
            present = [c for c in step["columns"] if c in out.columns]
            for col in present:
                out[col] = pseudonymize.pseudonymize(out[col], salt)
            audit["transforms"].append({"op": op, "columns": present})
        elif op == "generalize_time":
            mins = step["minutes"]
            for col in ("pickup_datetime", "dropoff_datetime"):
                if col in out.columns:
                    out[col] = generalize.round_time(out[col], mins)
            audit["transforms"].append({"op": op, "minutes": mins})
        elif op == "rollup_zone":
            out["PUBorough"] = generalize.rollup_zone(out["PULocationID"], lookup)
            out["DOBorough"] = generalize.rollup_zone(out["DOLocationID"], lookup)
            out = out.drop(columns=["PULocationID", "DOLocationID"])
            audit["transforms"].append({"op": op})
        elif op == "drop_columns":
            out, dropped = suppress.drop_columns(out, step["columns"])
            audit["transforms"].append({"op": op, **dropped})
        elif op == "kanon":
            out, ka = kanon.suppress_below_k(out, step["qi"], step["k"])
            audit["cells_suppressed"] += ka["cells_suppressed"]
            audit["k_achieved"] = ka["k_achieved"]
            audit["transforms"].append(
                {"op": op, **{x: ka[x] for x in ("qi", "k", "cells_suppressed", "k_achieved")}}
            )
        elif op == "select":
            keep = [c for c in step["columns"] if c in out.columns]
            out = out[keep]
            audit["transforms"].append({"op": op, "columns": keep})
    audit["rows_out"] = len(out)
    return out, audit


def _run_aggregate(
    df: pd.DataFrame, step: dict, lookup: dict[int, str]
) -> tuple[pd.DataFrame, dict]:
    dims = _resolve_dimensions(df, step["dimensions"], lookup, step["minutes"])
    counts = dims.groupby(step["dimensions"], dropna=False).size().reset_index(name="trip_count")
    cells_in = len(counts)
    kept = counts[counts["trip_count"] >= step["k"]].reset_index(drop=True)
    audit = {
        "transforms": [{"op": "aggregate", **{x: step[x] for x in ("dimensions", "minutes", "k")}}],
        "rows_in": len(df),
        "rows_out": int(kept["trip_count"].sum()),
        "cells_in": cells_in,
        "cells_out": len(kept),
        "cells_suppressed": cells_in - len(kept),
        "k_achieved": int(kept["trip_count"].min()) if len(kept) else None,
    }
    return kept, audit


def _refusal(
    policy: Policy, policy_hash: str, source: str, reason: str, settings: Settings
) -> dict:
    result = {
        "policy_name": policy.name,
        "policy_version": policy.version,
        "policy_hash": policy_hash,
        "output_kind": policy.output_kind.value,
        "source": source,
        "refused": True,
        "reason": reason,
        "generated_utc": datetime.now(UTC).isoformat(),
        "output_path": None,
        "transforms": [],
    }
    md = report.render_markdown(result)
    writers.write_text(settings.reports_dir / f"export_{policy.name}_{source}.md", md)
    writers.write_json(settings.reports_dir / f"export_{policy.name}_{source}.json", result)
    return result


def run_export(
    df: pd.DataFrame,
    policy: Policy,
    policy_hash: str,
    settings: Settings,
    lookup: dict[int, str],
    source: str,
    input_hash: str,
    note_detector: NoteDetector | None = None,
    approval_id: str | None = None,
) -> dict:
    """Run a policy on ``df``; write the export + methodology report; return the audit."""
    # Gate 1: validation certification must pass.
    cert = health.build_report(df, settings.gate_threshold, source=source)
    if cert["refused"]:
        return _refusal(
            policy, policy_hash, source, f"validation gate refused: {cert['reason']}", settings
        )

    # Gate 2: approval-gated profiles fail closed without an approval record.
    if policy.requires_approval and not approvals.approval_exists(
        approval_id, settings.approvals_dir
    ):
        return _refusal(
            policy, policy_hash, source, "approval required but no approval record found", settings
        )

    plan = compile_policy(policy)
    salt_fp = _PSEUDO_NULL_FP
    salt = b""
    if any(s["op"] == "pseudonymize" for s in plan):
        salt = salts.generate_salt()
        salt_fp = salt_fingerprint(salt)
        salts.write_salt(salt, settings.salts_dir)

    if policy.output_kind == OutputKind.AGGREGATE:
        out, audit = _run_aggregate(df, plan[0], lookup)
        ext, writer = "csv", lambda p: out.to_csv(p, index=False)
    else:
        if any(s["op"] == "redact_note" for s in plan) and note_detector is None:
            raise ValueError("policy redacts notes but no note_detector was provided")
        out, audit = _run_row_level(df, plan, salt, lookup, note_detector)
        ext, writer = "parquet", lambda p: out.to_parquet(p, index=False)

    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.exports_dir / f"{policy.name}_{source}.{ext}"
    writer(output_path)

    original_cols = set(df.columns)
    shared_cols = list(out.columns)
    result = {
        "policy_name": policy.name,
        "policy_version": policy.version,
        "policy_hash": policy_hash,
        "output_kind": policy.output_kind.value,
        "source": source,
        "input_hash": input_hash,
        "requires_approval": policy.requires_approval,
        "approval_id": approval_id,
        "gate": {"health_score": cert["health_score"], "refused": False},
        "salt_fingerprint": salt_fp,
        "columns_shared": shared_cols,
        "columns_withheld": sorted(original_cols - set(shared_cols)),
        "generated_utc": datetime.now(UTC).isoformat(),
        "output_path": str(output_path.relative_to(settings.project_root)),
        "output_hash": _sha256_file(output_path),
        "refused": False,
        "reason": None,
        **audit,
    }
    md = report.render_markdown(result)
    writers.write_text(settings.reports_dir / f"export_{policy.name}_{source}.md", md)
    writers.write_json(settings.reports_dir / f"export_{policy.name}_{source}.json", result)
    return result
