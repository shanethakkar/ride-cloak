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


if __name__ == "__main__":
    main()
