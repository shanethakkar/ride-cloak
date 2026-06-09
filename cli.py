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


if __name__ == "__main__":
    main()
