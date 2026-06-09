"""TLC data fetch with manifest cache.

Downloads a month's HVFHV Parquet and the zone lookup, caching each with a JSON
manifest (source URL, download date, SHA-256, byte size, row count). Re-fetching
is skipped when a valid cache exists unless ``refresh`` is set. Streaming hashing
keeps memory flat regardless of the ~500 MB file size.
"""

from __future__ import annotations

import hashlib
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.settings import Settings
from pipeline.io import duck, writers

_CHUNK = 1 << 20  # 1 MiB streaming chunks


def _stream_download(url: str, dest: Path) -> tuple[str, int]:
    """Stream ``url`` to ``dest``, returning (sha256_hex, byte_count).

    Writes to a temp sibling then atomically replaces the target so an
    interrupted download never leaves a corrupt cache file in place.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    sha = hashlib.sha256()
    total = 0
    req = urllib.request.Request(url, headers={"User-Agent": "RideCloak/0.1"})
    with urllib.request.urlopen(req) as resp, tmp.open("wb") as fh:  # noqa: S310 (trusted TLC host)
        while chunk := resp.read(_CHUNK):
            fh.write(chunk)
            sha.update(chunk)
            total += len(chunk)
    tmp.replace(dest)
    return sha.hexdigest(), total


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def fetch_month(
    month: str,
    settings: Settings,
    refresh: bool = False,
) -> dict[str, Any]:
    """Fetch (or reuse) one HVFHV month and return its manifest.

    Args:
        month: ``YYYY-MM`` (e.g. ``2026-04``).
        settings: resolved configuration providing URLs and cache paths.
        refresh: re-download even if a cached manifest exists.

    Returns:
        Manifest dict: source_url, download_date_utc, sha256, bytes, row_count,
        path, month.
    """
    dest = settings.raw_parquet_path(month)
    manifest_path = settings.raw_manifest_path(f"fhvhv_tripdata_{month}")

    if dest.exists() and manifest_path.exists() and not refresh:
        from pipeline.io.readers import read_json

        return read_json(manifest_path)

    url = settings.tlc_trip_url_template.format(month=month)
    sha256, size = _stream_download(url, dest)
    rows = duck.row_count(dest)

    manifest = {
        "artifact": "hvfhv_trip_parquet",
        "month": month,
        "source_url": url,
        "download_date_utc": _utc_now_iso(),
        "sha256": sha256,
        "bytes": size,
        "row_count": rows,
        "path": str(dest.relative_to(settings.project_root)),
    }
    writers.write_json(manifest_path, manifest)
    return manifest


def fetch_zone_lookup(settings: Settings, refresh: bool = False) -> dict[str, Any]:
    """Fetch (or reuse) the taxi zone lookup CSV and return its manifest."""
    dest = settings.zone_lookup_path
    manifest_path = settings.raw_manifest_path("taxi_zone_lookup")

    if dest.exists() and manifest_path.exists() and not refresh:
        from pipeline.io.readers import read_json

        return read_json(manifest_path)

    sha256, size = _stream_download(settings.zone_lookup_url, dest)
    manifest = {
        "artifact": "taxi_zone_lookup_csv",
        "source_url": settings.zone_lookup_url,
        "download_date_utc": _utc_now_iso(),
        "sha256": sha256,
        "bytes": size,
        "path": str(dest.relative_to(settings.project_root)),
    }
    writers.write_json(manifest_path, manifest)
    return manifest
