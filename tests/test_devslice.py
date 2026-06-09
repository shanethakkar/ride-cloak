"""Dev-slice integration test: real 250K slice, reproducible by hash.

Skipped when the cached monthly Parquet is absent (e.g. fresh clone without a
fetch), so the unit suite stays runnable everywhere. On a machine that has run
`ridecloak fetch`, this proves the SPEC 5.4 reproducibility criterion end to end.
"""

from __future__ import annotations

import hashlib

import pytest

from config.settings import get_settings
from pipeline.io import readers
from pipeline.synth import devslice

settings = get_settings()
_raw = settings.raw_parquet_path(settings.dev_source_month)

pytestmark = pytest.mark.skipif(
    not _raw.exists(),
    reason=f"raw month not cached at {_raw}; run `ridecloak fetch` to enable",
)


def test_dev_slice_is_250k_and_reproducible():
    first = devslice.build_dev_slice(settings)
    assert first["rows"] == settings.dev_slice_rows

    df = readers.read_parquet(settings.dev_slice_path)
    assert len(df) == settings.dev_slice_rows
    assert df["trip_id"].is_unique

    # Same seed + month must reproduce a byte-identical slice file.
    second = devslice.build_dev_slice(settings)
    assert second["slice_sha256"] == first["slice_sha256"]
    rebuilt_hash = hashlib.sha256(settings.dev_slice_path.read_bytes()).hexdigest()
    assert rebuilt_hash == first["slice_sha256"]


def test_dev_slice_labels_realign_on_disk():
    devslice.build_dev_slice(settings)
    df = readers.read_parquet(settings.dev_slice_path)
    labels = readers.read_parquet(settings.labels_path)
    notes = df.set_index("trip_id")["support_note"]

    assert len(labels) > 0
    sample = labels.sample(min(500, len(labels)), random_state=0)
    for row in sample.itertuples(index=False):
        extracted = notes.loc[row.trip_id][row.start : row.end]
        assert hashlib.sha256(extracted.encode("utf-8")).hexdigest() == row.value_hash
