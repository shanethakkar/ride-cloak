"""RideCloak command-line interface.

Thin Click layer over the pipeline. Each command resolves settings, performs I/O
through pipeline.io, prints a Rich summary, and (later phases) writes a JSON
artifact plus a ledger entry. Heavy imports are deferred into command bodies so
``ridecloak --help`` stays fast.
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from config.settings import get_settings

console = Console()


def _append_ledger(settings, command: str, record: dict) -> dict:
    """Append a hash-chained entry for a command run (decisions.md D-0010)."""
    from pipeline.attest import ledger

    return ledger.append(settings.ledger_path, record, command=command, operator=settings.operator)


@click.group()
@click.version_option(package_name="ridecloak")
def main() -> None:
    """RideCloak: privacy-safe regulated trip-data sharing pipeline."""


@main.command()
@click.option("--month", required=True, help="HVFHV month to fetch, YYYY-MM (e.g. 2026-04).")
@click.option("--refresh", is_flag=True, help="Re-download even if a cached copy exists.")
def fetch(month: str, refresh: bool) -> None:
    """Download a TLC HVFHV month and the zone lookup, caching with manifests."""
    from pipeline.io import fetch as fetch_io

    settings = get_settings()
    console.print(f"[bold]Fetching[/bold] HVFHV month [cyan]{month}[/cyan] ...")
    trip_manifest = fetch_io.fetch_month(month, settings, refresh=refresh)
    zone_manifest = fetch_io.fetch_zone_lookup(settings, refresh=refresh)

    table = Table(title=f"Fetch summary — {month}")
    table.add_column("artifact")
    table.add_column("rows", justify="right")
    table.add_column("bytes", justify="right")
    table.add_column("sha256 (first 12)")
    table.add_row(
        "hvfhv_trip_parquet",
        f"{trip_manifest['row_count']:,}",
        f"{trip_manifest['bytes']:,}",
        trip_manifest["sha256"][:12],
    )
    table.add_row(
        "taxi_zone_lookup",
        "-",
        f"{zone_manifest['bytes']:,}",
        zone_manifest["sha256"][:12],
    )
    console.print(table)
    _append_ledger(
        settings,
        "fetch",
        {
            "input_hash": None,
            "output_hash": trip_manifest["sha256"],
            "metrics": {"month": month, "row_count": trip_manifest["row_count"]},
        },
    )


@main.command()
@click.option(
    "--input",
    "input_sel",
    required=True,
    type=click.Choice(["dev", "month"]),
    help="'dev' builds the 250K dev slice with synthetic layer; 'month' requires --month.",
)
@click.option("--month", default=None, help="Required when --input month.")
@click.option("--seed", default=None, type=int, help="Override the synthetic seed.")
def synth(input_sel: str, month: str | None, seed: int | None) -> None:
    """Attach the synthetic PII layer and write the dev slice + ground-truth labels."""
    from pipeline.synth.devslice import build_dev_slice

    settings = get_settings()
    if input_sel == "month" and not month:
        raise click.UsageError("--input month requires --month YYYY-MM.")

    effective_seed = seed if seed is not None else settings.synth_seed
    console.print(
        f"[bold]Synthesizing[/bold] PII layer on [cyan]{input_sel}[/cyan] "
        f"(seed={effective_seed}) ..."
    )
    result = build_dev_slice(settings, month=month, seed=effective_seed)

    table = Table(title="Synth summary")
    table.add_column("metric")
    table.add_column("value", justify="right")
    table.add_row("trips", f"{result['rows']:,}")
    table.add_row("unique riders", f"{result['unique_riders']:,}")
    table.add_row("support notes", f"{result['notes']:,}")
    table.add_row("labeled spans", f"{result['spans']:,}")
    table.add_row("decoy notes", f"{result['decoy_notes']:,}")
    table.add_row("dev slice sha256 (first 12)", result["slice_sha256"][:12])
    console.print(table)
    console.print(f"dev slice -> {result['slice_path']}")
    console.print(f"labels    -> {result['labels_path']}")
    _append_ledger(
        settings,
        "synth",
        {
            "input_hash": None,
            "output_hash": result["slice_sha256"],
            "metrics": {k: result[k] for k in ("rows", "unique_riders", "notes", "spans")},
        },
    )


@main.command()
@click.option(
    "--input",
    "input_sel",
    required=True,
    type=click.Choice(["dev", "month"]),
    help="'dev' validates the dev slice in pandas; 'month' validates at scale in DuckDB.",
)
@click.option("--month", default=None, help="Required when --input month (YYYY-MM).")
def validate(input_sel: str, month: str | None) -> None:
    """Run the two-tier validation gate and write a JSON + markdown certification report."""
    from pipeline.io import duck, readers, writers
    from pipeline.validate import checks, health, report

    settings = get_settings()
    if input_sel == "month" and not month:
        raise click.UsageError("--input month requires --month YYYY-MM.")

    if input_sel == "dev":
        source = "dev"
        df = readers.read_parquet(settings.dev_slice_path)
        result = health.build_report(df, settings.gate_threshold, source=source)
    else:
        source = f"month:{month}"
        raw = settings.raw_parquet_path(month).as_posix()
        con = duck.connect()
        try:
            con.execute(
                f"CREATE VIEW t AS SELECT * FROM read_parquet('{raw}') "
                f"WHERE hvfhs_license_num = '{settings.uber_license_num}'"
            )
            row = con.execute(checks.month_aggregate_sql("t")).df().iloc[0].to_dict()
        finally:
            con.close()
        tier1, counts = checks.parse_month_aggregate(row)
        result = health.build_report_from_counts(counts, settings.gate_threshold, tier1, source)

    stem = f"validation_{source.replace(':', '_')}"
    json_path = writers.write_json(settings.reports_dir / f"{stem}.json", result)
    md_path = writers.write_text(
        settings.reports_dir / f"{stem}.md", report.render_markdown(result)
    )

    _print_validation_summary(result)
    console.print(f"report -> {json_path}")
    console.print(f"report -> {md_path}")
    _append_ledger(
        settings,
        "validate",
        {
            "input_hash": None,
            "output_hash": None,
            "metrics": {
                "health_score": result["health_score"],
                "refused": result["refused"],
                "source": result["source"],
            },
        },
    )
    if result["refused"]:
        raise SystemExit(1)  # gate blocks: non-zero so pipeline scripts stop


def _print_validation_summary(result: dict) -> None:
    table = Table(title=f"Validation — {result['source']}")
    table.add_column("dimension")
    table.add_column("score", justify="right")
    if result["tier1_passed"]:
        for dim, score in result["dimensions"].items():
            table.add_row(dim, f"{score:.2f}")
        table.add_row("[bold]composite[/bold]", f"[bold]{result['health_score']:.2f}[/bold]")
    else:
        table.add_row("Tier-1 contract", "FAILED")
    console.print(table)
    verdict = "[red]REFUSED[/red]" if result["refused"] else "[green]PASSED[/green]"
    threshold = result["gate_threshold"]
    console.print(f"gate threshold {threshold} -> {verdict}")
    if result["reason"]:
        console.print(f"reason: {result['reason']}")


@main.command()
@click.option(
    "--input",
    "input_sel",
    required=True,
    type=click.Choice(["dev"]),
    help="'dev': classify columns and measure PII detection vs the synthetic labels.",
)
def classify(input_sel: str) -> None:
    """Classify every column and measure Presidio detection precision/recall vs ground truth."""
    from pipeline.classify import dictionary, evaluate, pii_scan, report
    from pipeline.classify.dictionary import Tier
    from pipeline.io import readers, writers

    settings = get_settings()
    cls = dictionary.load(settings.classification_yaml_path)
    df = readers.read_parquet(settings.dev_slice_path)

    unclassified = cls.unclassified(list(df.columns))
    if unclassified:
        console.print(f"[red]Unclassified columns:[/red] {unclassified}")
        raise SystemExit(1)

    noted = df[df["support_note"].notna()].sort_values("trip_id")
    trip_ids = noted["trip_id"].tolist()
    texts = noted["support_note"].astype(str).tolist()

    console.print(f"[bold]Scanning[/bold] {len(texts):,} support notes with Presidio ...")
    analyzer = pii_scan.build_analyzer()
    detections = pii_scan.scan_texts(analyzer, texts)

    labels = readers.read_parquet(settings.labels_path)
    gold = evaluate.gold_from_labels(labels, trip_ids)
    detection = evaluate.evaluate(detections, gold)

    pii_notes = sum(1 for g in gold if g)
    overall = detection["overall"]
    targets = {"recall": 0.95, "precision": 0.90}
    passed = overall["recall"] >= targets["recall"] and overall["precision"] >= targets["precision"]

    result = {
        "source": input_sel,
        "model": pii_scan.DEFAULT_MODEL,
        "threshold": pii_scan.DEFAULT_THRESHOLD,
        "notes_scanned": len(texts),
        "pii_notes": pii_notes,
        "decoy_notes": len(texts) - pii_notes,
        "classification": {t.value: len(cls.columns_in_tier(t)) for t in Tier},
        "detection": detection,
        "targets": targets,
        "passed": passed,
    }

    json_path = writers.write_json(settings.reports_dir / "classification_dev.json", result)
    md_path = writers.write_text(
        settings.reports_dir / "classification_dev.md", report.render_markdown(result)
    )
    _print_classification_summary(result)
    console.print(f"report -> {json_path}")
    console.print(f"report -> {md_path}")
    _append_ledger(
        settings,
        "classify",
        {
            "input_hash": None,
            "output_hash": None,
            "metrics": {
                "precision": overall["precision"],
                "recall": overall["recall"],
                "f1": overall["f1"],
                "passed": passed,
            },
        },
    )
    if not passed:
        raise SystemExit(1)


def _print_classification_summary(result: dict) -> None:
    table = Table(title="PII detection (per entity)")
    table.add_column("entity")
    table.add_column("prec", justify="right")
    table.add_column("recall", justify="right")
    table.add_column("F1", justify="right")
    for entity, m in result["detection"]["per_entity"].items():
        table.add_row(entity, f"{m['precision']:.3f}", f"{m['recall']:.3f}", f"{m['f1']:.3f}")
    o = result["detection"]["overall"]
    table.add_row(
        "[bold]overall[/bold]",
        f"[bold]{o['precision']:.3f}[/bold]",
        f"[bold]{o['recall']:.3f}[/bold]",
        f"[bold]{o['f1']:.3f}[/bold]",
    )
    console.print(table)
    t = result["targets"]
    verdict = "[green]PASSED[/green]" if result["passed"] else "[red]FAILED[/red]"
    console.print(f"targets recall>={t['recall']} precision>={t['precision']} -> {verdict}")


@main.command()
@click.option(
    "--input",
    "input_sel",
    required=True,
    type=click.Choice(["dev", "month"]),
    help="'dev' assesses the dev slice in pandas; 'month' assesses at scale in DuckDB.",
)
@click.option("--month", default=None, help="Required when --input month (YYYY-MM).")
@click.option("--qi", default=None, help="Custom quasi-identifier, comma-separated (dev only).")
@click.option("--bucket-min", default=None, type=int, help="Time-bucket size in minutes.")
def risk(input_sel: str, month: str | None, qi: str | None, bucket_min: int | None) -> None:
    """Report the re-identification uniqueness ladder and k-suppression cost."""
    from pipeline.io import readers, writers
    from pipeline.transform import risk as risk_mod

    settings = get_settings()
    k = settings.k_default
    bucket = bucket_min or settings.bucket_min_default
    if input_sel == "month" and not month:
        raise click.UsageError("--input month requires --month YYYY-MM.")

    if input_sel == "dev":
        source = "dev"
        df = readers.read_parquet(settings.dev_slice_path)
        zl = readers.read_csv(settings.zone_lookup_path)
        lookup = dict(zip(zl["LocationID"], zl["Borough"], strict=True))
        custom_qi = None
        if qi:
            try:
                custom_qi = [risk_mod.QI_TOKENS[t.strip()] for t in qi.split(",")]
            except KeyError as exc:
                raise click.UsageError(
                    f"Unknown --qi token {exc}; allowed: {sorted(risk_mod.QI_TOKENS)}"
                ) from exc
        result = risk_mod.assess_dev(df, lookup, bucket, k, custom_qi=custom_qi)
    else:
        source = f"month:{month}"
        result = _risk_month(month, bucket, k, settings)

    result["source"] = source
    stem = f"risk_{source.replace(':', '_')}"
    json_path = writers.write_json(settings.reports_dir / f"{stem}.json", result)
    md_path = writers.write_text(
        settings.reports_dir / f"{stem}.md", risk_mod.render_markdown(result)
    )
    _print_risk_summary(result)
    console.print(f"report -> {json_path}")
    console.print(f"report -> {md_path}")
    _append_ledger(
        settings,
        "risk",
        {
            "input_hash": None,
            "output_hash": None,
            "source": result["source"],
            "metrics": {
                "k": result["k"],
                "bucket_min": result["bucket_min"],
                "ladder": result["ladder"],
            },
        },
    )


def _risk_month(month: str, bucket: int, k: int, settings) -> dict:
    from pipeline.io import duck
    from pipeline.transform import kanon
    from pipeline.transform import risk as risk_mod

    raw = settings.raw_parquet_path(month).as_posix()
    lk = settings.zone_lookup_path.as_posix()
    con = duck.connect()
    try:
        con.execute(f"CREATE VIEW z AS SELECT LocationID, Borough FROM read_csv('{lk}')")
        con.execute(
            f"CREATE VIEW j AS SELECT d.PULocationID AS pu, d.DOLocationID AS do_id, "
            f"zp.Borough AS pb, zd.Borough AS db, d.pickup_datetime AS pickup_datetime "
            f"FROM (SELECT * FROM read_parquet('{raw}') "
            f"WHERE hvfhs_license_num = '{settings.uber_license_num}') d "
            f"JOIN z zp ON d.PULocationID = zp.LocationID "
            f"JOIN z zd ON d.DOLocationID = zd.LocationID"
        )
        total = int(con.execute("SELECT count(*) FROM j").fetchone()[0])
        ladder = [
            {
                "qi": label,
                "uniqueness": round(con.execute(kanon.uniqueness_sql("j", e)).fetchone()[0], 4),
            }
            for label, e in risk_mod.month_ladder_exprs(bucket)
        ]
        suppression = []
        for label, exprs in risk_mod.month_suppression_exprs(bucket):
            supp = con.execute(kanon.suppression_sql("j", exprs, k)).fetchone()[0]
            kach = con.execute(kanon.k_achieved_sql("j", exprs, k)).fetchone()[0]
            rows_out = int(round(total * (1 - supp)))
            suppression.append(
                {
                    "qi": label,
                    "k": k,
                    "rows_in": total,
                    "rows_out": rows_out,
                    "cells_suppressed": total - rows_out,
                    "suppressed": round(supp, 4),
                    "k_achieved": int(kach) if kach is not None else None,
                }
            )
    finally:
        con.close()
    return {
        "bucket_min": bucket,
        "k": k,
        "rows": total,
        "ladder": ladder,
        "suppression": suppression,
    }


def _print_risk_summary(result: dict) -> None:
    ladder = Table(title=f"Uniqueness ladder — {result['source']}")
    ladder.add_column("quasi-identifier")
    ladder.add_column("uniqueness", justify="right")
    for rung in result["ladder"]:
        ladder.add_row(rung["qi"], f"{rung['uniqueness']:.2%}")
    console.print(ladder)

    supp = Table(title=f"k-anonymity suppression (k={result['k']})")
    supp.add_column("quasi-identifier")
    supp.add_column("suppressed", justify="right")
    supp.add_column("rows out", justify="right")
    for s in result["suppression"]:
        supp.add_row(s["qi"], f"{s['suppressed']:.2%}", f"{s['rows_out']:,}")
    console.print(supp)


_PROFILE_FILES = {
    "tlc": "tlc_trip_submission",
    "mds": "mds_aggregate",
    "le": "law_enforcement_extract",
}


@main.command()
@click.option("--profile", required=True, type=click.Choice(["tlc", "mds", "le"]))
@click.option(
    "--input",
    "input_sel",
    required=True,
    type=click.Choice(["dev", "month"]),
    help="'dev' for row-level/aggregate; 'month' only for the MDS aggregate (scale path).",
)
@click.option("--month", default=None, help="Required when --input month (YYYY-MM).")
@click.option("--approval", default=None, help="Approval record id (required for the LE profile).")
def export(profile: str, input_sel: str, month: str | None, approval: str | None) -> None:
    """Run a sharing policy and emit a regulator export + methodology report."""
    import hashlib

    from pipeline.export import runner
    from pipeline.io import readers
    from policies.schema import OutputKind, load_policy

    settings = get_settings()
    policy, policy_hash = load_policy(settings.policies_dir / f"{_PROFILE_FILES[profile]}.yaml")

    if input_sel == "month":
        if policy.output_kind != OutputKind.AGGREGATE:
            raise click.UsageError(
                "--input month is only supported for the MDS aggregate; row-level profiles "
                "(tlc, le) operate on the dev slice where the synthetic identity layer exists."
            )
        if not month:
            raise click.UsageError("--input month requires --month YYYY-MM.")
        result = _export_mds_month(month, policy, policy_hash, settings)
    else:
        df = readers.read_parquet(settings.dev_slice_path)
        zl = readers.read_csv(settings.zone_lookup_path)
        lookup = dict(zip(zl["LocationID"], zl["Borough"], strict=True))
        input_hash = hashlib.sha256(settings.dev_slice_path.read_bytes()).hexdigest()
        detector = None
        if policy.row_level and policy.row_level.redact_note:
            from pipeline.classify import pii_scan

            analyzer = pii_scan.build_analyzer()
            console.print("[bold]Scanning notes for redaction[/bold] ...")
            detector = lambda texts: pii_scan.scan_texts(analyzer, texts)  # noqa: E731
        result = runner.run_export(
            df,
            policy,
            policy_hash,
            settings,
            lookup,
            source="dev",
            input_hash=input_hash,
            note_detector=detector,
            approval_id=approval,
        )

    _print_export_summary(result)
    if result["refused"]:
        raise SystemExit(1)


def _export_mds_month(month: str, policy, policy_hash: str, settings) -> dict:
    """Scale path: compute the MDS aggregate over a full month in DuckDB (no pandas load)."""
    from datetime import UTC, datetime

    from pipeline.attest import report
    from pipeline.io import duck, writers

    a = policy.aggregate
    raw = settings.raw_parquet_path(month).as_posix()
    lk = settings.zone_lookup_path.as_posix()
    con = duck.connect()
    try:
        con.execute(f"CREATE VIEW z AS SELECT LocationID, Borough FROM read_csv('{lk}')")
        bucket = f"time_bucket(INTERVAL '{a.time_bucket_minutes} minutes', d.pickup_datetime)"
        con.execute(
            "CREATE VIEW j AS SELECT zp.Borough AS PUBorough, zd.Borough AS DOBorough, "
            f"{bucket} AS pickup_bucket "
            f"FROM (SELECT * FROM read_parquet('{raw}') "
            f"WHERE hvfhs_license_num = '{settings.uber_license_num}') d "
            "JOIN z zp ON d.PULocationID = zp.LocationID "
            "JOIN z zd ON d.DOLocationID = zd.LocationID"
        )
        dims = ", ".join(a.dimensions)
        agg = con.execute(
            f"SELECT {dims}, count(*) AS trip_count FROM j GROUP BY {dims} "
            f"HAVING count(*) >= {a.k} ORDER BY trip_count DESC"
        ).df()
        cells_in = int(
            con.execute(f"SELECT count(*) FROM (SELECT {dims} FROM j GROUP BY {dims})").fetchone()[
                0
            ]
        )
        total = int(con.execute("SELECT count(*) FROM j").fetchone()[0])
    finally:
        con.close()

    source = f"month:{month}"
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.exports_dir / f"{policy.name}_{source.replace(':', '_')}.csv"
    agg.to_csv(output_path, index=False)
    import hashlib

    result = {
        "policy_name": policy.name,
        "policy_version": policy.version,
        "policy_hash": policy_hash,
        "output_kind": policy.output_kind.value,
        "source": source,
        "input_hash": None,
        "requires_approval": policy.requires_approval,
        "approval_id": None,
        "gate": {"health_score": None, "refused": False},
        "salt_fingerprint": "n/a",
        "rows_in": total,
        "rows_out": int(agg["trip_count"].sum()),
        "cells_in": cells_in,
        "cells_out": len(agg),
        "cells_suppressed": cells_in - len(agg),
        "k_achieved": int(agg["trip_count"].min()) if len(agg) else None,
        "columns_shared": list(agg.columns),
        "columns_withheld": [],
        "transforms": [
            {
                "op": "aggregate",
                "dimensions": a.dimensions,
                "minutes": a.time_bucket_minutes,
                "k": a.k,
            }
        ],
        "generated_utc": datetime.now(UTC).isoformat(),
        "output_path": str(output_path.relative_to(settings.project_root)),
        "output_hash": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "refused": False,
        "reason": None,
    }
    entry = _append_ledger(settings, "export", result)
    stem = f"export_{policy.name}_{source.replace(':', '_')}"
    writers.write_text(settings.reports_dir / f"{stem}.md", report.render_markdown(entry))
    writers.write_json(settings.reports_dir / f"{stem}.json", entry)
    return entry


def _print_export_summary(result: dict) -> None:
    table = Table(title=f"Export — {result['policy_name']} ({result['source']})")
    table.add_column("field")
    table.add_column("value", justify="right")
    if result["refused"]:
        table.add_row("status", "[red]REFUSED[/red]")
        table.add_row("reason", result["reason"])
    else:
        table.add_row("rows in", f"{result['rows_in']:,}")
        table.add_row("rows out", f"{result['rows_out']:,}")
        table.add_row("cells suppressed", f"{result['cells_suppressed']:,}")
        if result.get("k_achieved") is not None:
            table.add_row("k achieved", str(result["k_achieved"]))
        table.add_row("salt fingerprint", str(result["salt_fingerprint"])[:16])
        table.add_row("output", result["output_path"])
    console.print(table)


@main.command(name="verify-ledger")
def verify_ledger() -> None:
    """Walk the hash chain and report whether the audit ledger is intact."""
    from pipeline.attest import ledger

    settings = get_settings()
    result = ledger.verify(settings.ledger_path)
    if result["ok"]:
        console.print(f"[green]Ledger intact[/green] — {result['entries']} entries verified")
    else:
        console.print(f"[red]Ledger BROKEN[/red] at seq {result['break_seq']}: {result['reason']}")
        raise SystemExit(1)


@main.command()
@click.option("--request", "request_text", required=True, help="Free-text regulator data request.")
def triage(request_text: str) -> None:
    """Parse a free-text request, apply deterministic guardrails, and queue a draft.

    The LLM only extracts; the verdict is decided by code and fails closed. This
    command never exports data — it writes a pending recommendation for a human.
    """
    from pipeline.agent import approval, guardrails
    from pipeline.agent import triage as triage_mod

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise click.UsageError("Set RIDECLOAK_ANTHROPIC_API_KEY in .env to use triage.")

    console.print("[bold]Parsing request with the triage model[/bold] ...")
    parsed, hashes = triage_mod.parse_request(request_text, settings)
    decision = guardrails.evaluate(parsed)
    draft = guardrails.build_draft(parsed, decision)
    console.print("[bold]Re-scanning the draft for residual PII[/bold] ...")
    draft_safe, redacted = guardrails.output_rescan(draft)

    request_id = approval.new_request_id()
    approval.queue_triage(settings, request_id, parsed, decision, draft_safe)
    _append_ledger(
        settings,
        "triage",
        {
            "input_hash": hashes["prompt_sha"],
            "output_hash": hashes["response_sha"],
            "metrics": {
                "verdict": decision.verdict.value,
                "profile": decision.profile,
                "request_id": request_id,
                "pii_redacted_in_draft": redacted,
            },
        },
    )
    _print_triage_summary(decision, request_id, draft_safe)


def _print_triage_summary(decision, request_id: str, draft: str) -> None:
    colors = {"allow": "green", "refuse": "red", "escalate": "yellow"}
    verdict = decision.verdict.value
    table = Table(title=f"Triage — {request_id}")
    table.add_column("field")
    table.add_column("value")
    table.add_row("verdict", f"[{colors[verdict]}]{verdict.upper()}[/{colors[verdict]}]")
    table.add_row("profile", str(decision.profile))
    table.add_row("fields allowed", ", ".join(decision.fields_allowed) or "(none)")
    table.add_row("fields refused", ", ".join(decision.fields_refused) or "(none)")
    console.print(table)
    for r in decision.reasons:
        console.print(f"  - {r}")
    console.print(
        f"\n[dim]Draft only. To release LE data a human must run "
        f"`ridecloak approve --request-id {request_id}` then `ridecloak export`.[/dim]"
    )


@main.command()
@click.option("--request-id", required=True, help="Identifier of the request being approved.")
@click.option("--note", default="", help="Optional approval note.")
def approve(request_id: str, note: str) -> None:
    """Record a human approval for a gated export (human-only act, SPEC section 13)."""
    import getpass

    from pipeline.io import approvals

    settings = get_settings()
    path = approvals.write_approval(
        request_id, settings.approvals_dir, operator=getpass.getuser(), note=note
    )
    console.print(f"[green]Approval recorded[/green] for '{request_id}' -> {path}")
    _append_ledger(
        settings,
        "approve",
        {"input_hash": None, "output_hash": None, "metrics": {"request_id": request_id}},
    )


if __name__ == "__main__":
    main()
