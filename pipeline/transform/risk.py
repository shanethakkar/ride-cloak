"""Re-identification risk assessment: the uniqueness ladder and k-suppression cost.

Shows how uniqueness falls as the quasi-identifier is generalized
(zone x minute -> zone x bucket -> zone x hour -> borough x bucket) and what
small-cell suppression costs at k. The dev path runs in pandas; the month path
uses SQL expression lists (executed by the CLI against DuckDB) so a full month is
assessed without loading the raw parquet into pandas.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from pipeline.transform.generalize import rollup_zone, round_time
from pipeline.transform.kanon import suppress_below_k, uniqueness

# Maps --qi tokens to the working columns the risk frame exposes.
QI_TOKENS = {
    "PULocationID": "PU",
    "DOLocationID": "DO",
    "pickup_bucket": "t_buck",
    "PUBorough": "pb",
    "DOBorough": "db",
}


def assess_dev(
    df: pd.DataFrame,
    lookup: dict[int, str],
    bucket_min: int,
    k: int,
    custom_qi: list[str] | None = None,
) -> dict:
    """Compute the uniqueness ladder and k-suppression cost on an in-memory frame.

    ``custom_qi`` (working-column names, e.g. from a --qi override) adds one extra
    suppression line for that quasi-identifier.
    """
    pickup = df["pickup_datetime"]
    work = pd.DataFrame(
        {
            "PU": df["PULocationID"].to_numpy(),
            "DO": df["DOLocationID"].to_numpy(),
            "t_min": round_time(pickup, 1).to_numpy(),
            "t_buck": round_time(pickup, bucket_min).to_numpy(),
            "t_hr": round_time(pickup, 60).to_numpy(),
            "pb": rollup_zone(df["PULocationID"], lookup).to_numpy(),
            "db": rollup_zone(df["DOLocationID"], lookup).to_numpy(),
        }
    )
    ladder = [
        {"qi": "zone x minute", "uniqueness": round(uniqueness(work, ["PU", "DO", "t_min"]), 4)},
        {
            "qi": f"zone x {bucket_min}min",
            "uniqueness": round(uniqueness(work, ["PU", "DO", "t_buck"]), 4),
        },
        {"qi": "zone x 60min", "uniqueness": round(uniqueness(work, ["PU", "DO", "t_hr"]), 4)},
        {
            "qi": f"borough x {bucket_min}min",
            "uniqueness": round(uniqueness(work, ["pb", "db", "t_buck"]), 4),
        },
    ]
    suppression_qis = [
        (f"zone x {bucket_min}min", ["PU", "DO", "t_buck"]),
        (f"borough x {bucket_min}min", ["pb", "db", "t_buck"]),
    ]
    if custom_qi:
        suppression_qis.append((f"custom: {'+'.join(custom_qi)}", custom_qi))

    suppression = []
    for label, qi in suppression_qis:
        _, audit = suppress_below_k(work, qi, k)
        suppression.append(
            {
                "qi": label,
                "k": k,
                "rows_in": audit["rows_in"],
                "rows_out": audit["rows_out"],
                "cells_suppressed": audit["cells_suppressed"],
                "suppressed": round(audit["cells_suppressed"] / audit["rows_in"], 4),
                "k_achieved": audit["k_achieved"],
            }
        )
    return {
        "bucket_min": bucket_min,
        "k": k,
        "rows": len(df),
        "ladder": ladder,
        "suppression": suppression,
    }


# --- Month/scale path: QI expression lists over a joined DuckDB view ----------
# The view exposes pu, do (zone ids), pb, db (boroughs) and pickup_datetime.


def _bucket_expr(bucket_min: int) -> str:
    return f"time_bucket(INTERVAL '{bucket_min} minutes', pickup_datetime)"


def month_ladder_exprs(bucket_min: int) -> list[tuple[str, list[str]]]:
    # ``do`` is a SQL keyword; the joined view aliases the dropoff zone as ``do_id``.
    minute = "date_trunc('minute', pickup_datetime)"
    hour = "time_bucket(INTERVAL '60 minutes', pickup_datetime)"
    bucket = _bucket_expr(bucket_min)
    return [
        ("zone x minute", ["pu", "do_id", minute]),
        (f"zone x {bucket_min}min", ["pu", "do_id", bucket]),
        ("zone x 60min", ["pu", "do_id", hour]),
        (f"borough x {bucket_min}min", ["pb", "db", bucket]),
    ]


def month_suppression_exprs(bucket_min: int) -> list[tuple[str, list[str]]]:
    bucket = _bucket_expr(bucket_min)
    return [
        (f"zone x {bucket_min}min", ["pu", "do_id", bucket]),
        (f"borough x {bucket_min}min", ["pb", "db", bucket]),
    ]


def render_markdown(report: dict) -> str:
    """Committed-quality markdown report for `ridecloak risk`."""
    lines = [
        "# RideCloak re-identification risk report",
        "",
        f"- Source: `{report['source']}`",
        f"- Generated: {datetime.now(UTC).isoformat()}",
        f"- Rows: {report['rows']:,}",
        f"- Time bucket: {report['bucket_min']} min | k: {report['k']}",
        "",
        "## Uniqueness ladder (share of rows unique on the QI)",
        "",
        "| quasi-identifier | uniqueness |",
        "|---|---:|",
    ]
    for rung in report["ladder"]:
        lines.append(f"| {rung['qi']} | {rung['uniqueness']:.2%} |")
    lines += [
        "",
        f"## k-anonymity suppression cost (k = {report['k']})",
        "",
        "| quasi-identifier | rows in | rows out | suppressed | k achieved |",
        "|---|---:|---:|---:|---:|",
    ]
    for s in report["suppression"]:
        k_ach = s["k_achieved"] if s["k_achieved"] is not None else "-"
        lines.append(
            f"| {s['qi']} | {s['rows_in']:,} | {s['rows_out']:,} | "
            f"{s['suppressed']:.2%} | {k_ach} |"
        )
    lines.append("")
    lines.append(
        "Generalization is the dominant lever: zone-level data cannot be k-anonymized "
        "without rolling up to borough (decisions.md D-0008)."
    )
    lines.append("")
    return "\n".join(lines)
