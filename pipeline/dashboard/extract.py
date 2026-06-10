"""Build tidy/long CSV extracts from the ledger (+ committed report JSONs).

Pure builders take the loaded ledger entries and return DataFrames; the
orchestrator reads the ledger and reports, builds, and writes CSVs. Tidy/long
shape (one observation per row, consistent types, ISO dates) so the CSVs load
into Tableau with no manual cleaning.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import Settings
from pipeline.attest import ledger
from pipeline.io import readers


def month_of(source: str | None, dev_month: str) -> str | None:
    """Map a ledger ``source`` to its data month."""
    if not source:
        return None
    if source.startswith("month:"):
        return source.split(":", 1)[1]
    if source == "dev":
        return dev_month
    return source


def scope_of(source: str | None) -> str | None:
    """'dev' (sampled 250K) vs 'month' (full month) — they share a month label but
    differ (the dev sample overstates uniqueness)."""
    if not source:
        return None
    return "dev" if source == "dev" else "month"


def ledger_events(entries: list[dict]) -> pd.DataFrame:
    """The audit spine: one row per ledger entry."""
    return pd.DataFrame(
        [
            {
                "seq": e["seq"],
                "timestamp_utc": e["timestamp_utc"],
                "command": e["command"],
                "operator": e["operator"],
                "entry_hash": e["entry_hash"][:16],
            }
            for e in entries
        ]
    )


def exports(entries: list[dict], dev_month: str) -> pd.DataFrame:
    rows = []
    for e in entries:
        if e["command"] != "export":
            continue
        gate = e.get("gate") or {}
        rows_in = e.get("rows_in")
        rows.append(
            {
                "timestamp_utc": e["timestamp_utc"],
                "month": month_of(e.get("source"), dev_month),
                "scope": scope_of(e.get("source")),
                "policy_name": e.get("policy_name"),
                "output_kind": e.get("output_kind"),
                "rows_in": rows_in,
                "rows_out": e.get("rows_out"),
                "cells_suppressed": e.get("cells_suppressed"),
                "suppression_rate": (e["cells_suppressed"] / rows_in) if rows_in else None,
                "k_achieved": e.get("k_achieved"),
                "health_score": gate.get("health_score"),
                "refused": e.get("refused"),
            }
        )
    return pd.DataFrame(rows)


def validation(entries: list[dict], dev_month: str) -> pd.DataFrame:
    rows = []
    for e in entries:
        if e["command"] != "validate":
            continue
        m = e.get("metrics") or {}
        rows.append(
            {
                "timestamp_utc": e["timestamp_utc"],
                "month": month_of(m.get("source"), dev_month),
                "scope": scope_of(m.get("source")),
                "health_score": m.get("health_score"),
                "refused": m.get("refused"),
            }
        )
    return pd.DataFrame(rows)


def uniqueness(entries: list[dict], dev_month: str) -> pd.DataFrame:
    """Long: month x scope x quasi-identifier -> uniqueness (from the risk entry ladder)."""
    rows = []
    for e in entries:
        if e["command"] != "risk":
            continue
        m = e.get("metrics") or {}
        month = month_of(e.get("source"), dev_month)
        scope = scope_of(e.get("source"))
        for rung in m.get("ladder", []):
            rows.append(
                {"month": month, "scope": scope, "qi": rung["qi"], "uniqueness": rung["uniqueness"]}
            )
    return pd.DataFrame(rows)


def suppression(risk_reports: list[dict]) -> pd.DataFrame:
    """Long: month x quasi-identifier -> k-suppression cost (from risk report JSONs)."""
    rows = []
    for rpt in risk_reports:
        source = rpt.get("source", "")
        month = source.split(":", 1)[1] if source.startswith("month:") else source
        for s in rpt.get("suppression", []):
            rows.append(
                {
                    "month": month,
                    "qi": s["qi"],
                    "k": s["k"],
                    "suppressed": s["suppressed"],
                    "rows_out": s["rows_out"],
                }
            )
    return pd.DataFrame(rows)


def detection(classification_report: dict | None) -> pd.DataFrame:
    """Per-entity precision/recall/F1 from the classification report (+ overall)."""
    if not classification_report:
        return pd.DataFrame()
    det = classification_report["detection"]
    rows = []
    for entity, m in det["per_entity"].items():
        rows.append({"entity": entity, **m})
    rows.append({"entity": "overall", **det["overall"]})
    return pd.DataFrame(rows)


def triage(entries: list[dict]) -> pd.DataFrame:
    rows = []
    for e in entries:
        if e["command"] != "triage":
            continue
        m = e.get("metrics") or {}
        rows.append(
            {
                "timestamp_utc": e["timestamp_utc"],
                "request_id": m.get("request_id"),
                "verdict": m.get("verdict"),
                "profile": m.get("profile"),
                "pii_redacted_in_draft": m.get("pii_redacted_in_draft"),
            }
        )
    return pd.DataFrame(rows)


def requests(entries: list[dict]) -> pd.DataFrame:
    """Turnaround: join triage -> approve -> export by request id."""
    triage_ts: dict[str, str] = {}
    verdict: dict[str, str] = {}
    approve_ts: dict[str, str] = {}
    export_ts: dict[str, str] = {}
    for e in entries:
        m = e.get("metrics") or {}
        if e["command"] == "triage" and m.get("request_id"):
            triage_ts[m["request_id"]] = e["timestamp_utc"]
            verdict[m["request_id"]] = m.get("verdict")
        elif e["command"] == "approve" and m.get("request_id"):
            approve_ts[m["request_id"]] = e["timestamp_utc"]
        elif e["command"] == "export" and e.get("approval_id"):
            export_ts[e["approval_id"]] = e["timestamp_utc"]

    rows = []
    for rid, t_ts in triage_ts.items():
        a_ts, x_ts = approve_ts.get(rid), export_ts.get(rid)
        turnaround = None
        if x_ts:
            turnaround = (pd.Timestamp(x_ts) - pd.Timestamp(t_ts)).total_seconds() / 3600
        rows.append(
            {
                "request_id": rid,
                "verdict": verdict.get(rid),
                "triage_utc": t_ts,
                "approved_utc": a_ts,
                "exported_utc": x_ts,
                "turnaround_hours": turnaround,
                "final_status": "exported" if x_ts else ("approved" if a_ts else "pending"),
            }
        )
    return pd.DataFrame(rows)


def build_all(settings: Settings) -> dict[str, pd.DataFrame]:
    """Read the ledger + reports and return every table as a DataFrame (no writes)."""
    entries = ledger.read_entries(settings.ledger_path)
    dev_month = settings.dev_source_month

    risk_reports = [
        readers.read_json(p) for p in sorted(settings.reports_dir.glob("risk_month_*.json"))
    ]
    cls_path = settings.reports_dir / "classification_dev.json"
    cls_report = readers.read_json(cls_path) if cls_path.exists() else None

    return {
        "ledger_events": ledger_events(entries),
        "exports": exports(entries, dev_month),
        "validation": validation(entries, dev_month),
        "uniqueness": uniqueness(entries, dev_month),
        "suppression": suppression(risk_reports),
        "detection": detection(cls_report),
        "triage": triage(entries),
        "requests": requests(entries),
    }


def extract_all(settings: Settings) -> dict[str, tuple[Path, int]]:
    """Build every table and write it as a tidy CSV; return a manifest."""
    settings.dashboard_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, tuple[Path, int]] = {}
    for name, df in build_all(settings).items():
        path = settings.dashboard_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        manifest[name] = (path, len(df))
    return manifest
