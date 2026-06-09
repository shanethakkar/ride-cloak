"""Seeded synthetic PII layer and ground-truth span labels.

Pure core: given a DataFrame of real trip rows and a seed, return the same rows
enriched with synthetic identity fields and a free-text support note, plus a
labels DataFrame of every injected PII span. No file or DB I/O here.

Determinism contract: identical input rows (in the same order) and the same seed
produce byte-identical output. Callers must pass rows in a canonical order
(the dev-slice builder sorts by trip_id before calling in).
"""

from __future__ import annotations

import hashlib
import uuid

import numpy as np
import pandas as pd
from faker import Faker

from pipeline.synth import identifiers, templates

# Fixed namespace so trip_id is a deterministic UUID5 of row attributes.
TRIP_ID_NAMESPACE = uuid.UUID("6f1d3b2a-0c4e-5a7b-9d8c-1e2f3a4b5c6d")

# Stable row attributes that define a trip's surrogate identity.
TRIP_ID_KEYS = [
    "request_datetime",
    "pickup_datetime",
    "dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "trip_miles",
    "base_passenger_fare",
    "driver_pay",
]

# Synthetic columns appended to each trip (the reconstructed pre-anonymization input).
RIDER_FIELDS = ["rider_id", "rider_phone", "rider_email", "device_id", "payment_token"]
DRIVER_FIELDS = ["driver_license_num", "driver_name", "vehicle_plate", "vehicle_vin"]
SYNTH_COLUMNS = ["trip_id", *RIDER_FIELDS, *DRIVER_FIELDS, "support_note"]

NOTE_RATE = 0.02  # fraction of trips carrying a support note
PII_NOTE_SHARE = 0.75  # of noted trips, fraction that are PII notes (rest are decoys)


def compute_trip_id(df: pd.DataFrame) -> pd.Series:
    """Deterministic UUID5 surrogate key from stable trip attributes."""
    keys = df[TRIP_ID_KEYS].astype(str).agg("|".join, axis=1)
    return keys.map(lambda k: str(uuid.uuid5(TRIP_ID_NAMESPACE, k)))


def _zipf_weights(n: int, exponent: float) -> np.ndarray:
    ranks = np.arange(1, n + 1, dtype=float)
    w = 1.0 / np.power(ranks, exponent)
    return w / w.sum()


def _build_rider_pool(n: int, faker: Faker, rng: np.random.Generator) -> dict[str, np.ndarray]:
    return {
        "rider_id": np.array([identifiers.uuid4_from(rng) for _ in range(n)], dtype=object),
        "rider_phone": np.array([faker.phone_number() for _ in range(n)], dtype=object),
        "rider_email": np.array([faker.unique.email() for _ in range(n)], dtype=object),
        "device_id": np.array([identifiers.uuid4_from(rng) for _ in range(n)], dtype=object),
        "payment_token": np.array([identifiers.payment_token(rng) for _ in range(n)], dtype=object),
    }


def _build_driver_pool(n: int, faker: Faker, rng: np.random.Generator) -> dict[str, np.ndarray]:
    return {
        "driver_license_num": np.array(
            [identifiers.tlc_license(rng) for _ in range(n)], dtype=object
        ),
        "driver_name": np.array([faker.name() for _ in range(n)], dtype=object),
        "vehicle_plate": np.array([identifiers.ny_plate(rng) for _ in range(n)], dtype=object),
        "vehicle_vin": np.array([identifiers.vehicle_vin(rng) for _ in range(n)], dtype=object),
    }


def _render(parts: templates.PartList) -> tuple[str, list[tuple[str, int, int, str]]]:
    """Concatenate template parts, recording (entity_type, start, end, value) spans."""
    text = ""
    spans: list[tuple[str, int, int, str]] = []
    for part in parts:
        if isinstance(part, tuple):
            _, entity_type, value = part
            start = len(text)
            text += value
            spans.append((entity_type, start, len(text), value))
        else:
            text += part
    return text, spans


def _value_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate(df: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Enrich ``df`` with the synthetic PII layer and return (enriched, labels, stats).

    Args:
        df: real trip rows in canonical order (caller sorts by trip_id).
        seed: drives both numpy RNG and Faker for full reproducibility.

    Returns:
        enriched: ``df`` plus SYNTH_COLUMNS.
        labels: one row per injected PII span
            (trip_id, field, entity_type, start, end, value_hash).
        stats: counts (rows, unique_riders, notes, spans, decoy_notes).
    """
    n = len(df)
    rng = np.random.default_rng(seed)
    faker = Faker("en_US")
    faker.seed_instance(seed)

    out = df.reset_index(drop=True).copy()
    out["trip_id"] = compute_trip_id(out)

    # Identity pools: riders and drivers recur across trips (Zipf-skewed), so
    # frequent riders exist for the re-identification story.
    n_riders = max(1, n // 5)
    n_drivers = max(1, n // 8)
    riders = _build_rider_pool(n_riders, faker, rng)
    drivers = _build_driver_pool(n_drivers, faker, rng)

    rider_idx = rng.choice(n_riders, size=n, p=_zipf_weights(n_riders, 1.07))
    driver_idx = rng.choice(n_drivers, size=n, p=_zipf_weights(n_drivers, 1.03))

    for field in RIDER_FIELDS:
        out[field] = riders[field][rider_idx]
    for field in DRIVER_FIELDS:
        out[field] = drivers[field][driver_idx]

    # Support notes on ~NOTE_RATE of trips; a mix of PII templates and decoys.
    note_mask = rng.random(n) < NOTE_RATE
    is_pii = rng.random(n) < PII_NOTE_SHARE

    notes: list[str | None] = [None] * n
    label_rows: list[dict[str, object]] = []
    decoy_notes = 0

    for i in np.nonzero(note_mask)[0]:
        if is_pii[i]:
            template = templates.PII_TEMPLATES[rng.integers(len(templates.PII_TEMPLATES))]
            text, spans = _render(template(faker, rng))
            notes[i] = text
            trip_id = out.at[i, "trip_id"]
            for entity_type, start, end, value in spans:
                label_rows.append(
                    {
                        "trip_id": trip_id,
                        "field": "support_note",
                        "entity_type": entity_type,
                        "start": start,
                        "end": end,
                        "value_hash": _value_hash(value),
                    }
                )
        else:
            template = templates.DECOY_TEMPLATES[rng.integers(len(templates.DECOY_TEMPLATES))]
            text, _ = _render(template(faker, rng))
            notes[i] = text
            decoy_notes += 1

    out["support_note"] = pd.array(notes, dtype="string")

    labels = pd.DataFrame(
        label_rows,
        columns=["trip_id", "field", "entity_type", "start", "end", "value_hash"],
    )

    stats = {
        "rows": n,
        "unique_riders": int(np.unique(rider_idx).size),
        "notes": int(note_mask.sum()),
        "spans": int(len(labels)),
        "decoy_notes": int(decoy_notes),
    }
    return out, labels, stats
