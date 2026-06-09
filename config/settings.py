"""Central configuration for RideCloak.

Resolves the project root from this file's location so scripts run from any
working directory, and exposes typed settings plus canonical filesystem paths.
Values come from environment variables / .env (prefix ``RIDECLOAK_``) with the
defaults below; nothing here performs I/O beyond reading the environment.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# config/settings.py -> config/ -> project root
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Typed runtime configuration. Override any field via env or .env."""

    model_config = SettingsConfigDict(
        env_prefix="RIDECLOAK_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Determinism. One seed drives both the synthetic PII layer and the
    # dev-slice selection so a given seed reproduces byte-identical artifacts.
    synth_seed: int = 4242

    # Ingest. The TLC High-Volume FHV feed; HV0003 is Uber's license number.
    tlc_trip_url_template: str = (
        "https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_{month}.parquet"
    )
    zone_lookup_url: str = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
    uber_license_num: str = "HV0003"

    # Dev slice (SPEC 5.4): deterministic 250K-row sample of the Uber-filtered month.
    dev_slice_rows: int = 250_000
    # The month the dev slice derives from (first locked month; decisions.md D-0004).
    dev_source_month: str = "2026-04"

    # Validation gate (Phase 1): export refused below this 0-100 health score.
    gate_threshold: int = Field(default=90, ge=0, le=100)

    # k-anonymity default (Phase 3; decisions.md D-0008). Final per-profile k set in Phase 4.
    k_default: int = Field(default=5, ge=2)
    # Default time-bucket for the risk ladder, in minutes.
    bucket_min_default: int = 15

    # Phase 6 only. Never logged.
    anthropic_api_key: str | None = None

    # --- Canonical paths (derived from PROJECT_ROOT) -------------------------

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def data_raw_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "raw"

    @property
    def raw_manifest_dir(self) -> Path:
        return self.data_raw_dir / "manifests"

    @property
    def data_synth_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "synth"

    @property
    def data_dev_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "dev"

    @property
    def outputs_dir(self) -> Path:
        return PROJECT_ROOT / "outputs"

    @property
    def reports_dir(self) -> Path:
        return self.outputs_dir / "reports"

    @property
    def secrets_dir(self) -> Path:
        return PROJECT_ROOT / "secrets"

    @property
    def classification_yaml_path(self) -> Path:
        return PROJECT_ROOT / "config" / "classification.yaml"

    def raw_parquet_path(self, month: str) -> Path:
        """Local cache path for a month's raw HVFHV parquet (e.g. ``2026-04``)."""
        return self.data_raw_dir / f"fhvhv_tripdata_{month}.parquet"

    def raw_manifest_path(self, name: str) -> Path:
        """Manifest path for a cached artifact, keyed by a stable name."""
        return self.raw_manifest_dir / f"{name}.json"

    @property
    def zone_lookup_path(self) -> Path:
        return self.data_raw_dir / "taxi_zone_lookup.csv"

    @property
    def dev_slice_path(self) -> Path:
        return self.data_dev_dir / "dev_slice.parquet"

    @property
    def labels_path(self) -> Path:
        return self.data_synth_dir / "labels.parquet"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
