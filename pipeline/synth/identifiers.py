"""Deterministic identifier-format generators shared by the structured synth
layer and the free-text support-note templates.

Keeping these in one place means a driver's license/plate/VIN have the same
format whether they appear as a structured column or embedded mid-sentence in a
support note, which is what lets the Phase 2 custom recognizers be measured
against ground truth. All draw from a seeded numpy Generator for reproducibility.
"""

from __future__ import annotations

import uuid
from string import ascii_uppercase

from numpy.random import Generator

# VIN alphabet excludes I, O, Q to avoid confusion with 1/0 (real VIN spec).
VIN_CHARS = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"


def uuid4_from(rng: Generator) -> str:
    """A UUID4-shaped value sourced from the seeded RNG (deterministic)."""
    return str(uuid.UUID(bytes=rng.bytes(16), version=4))


def tlc_license(rng: Generator) -> str:
    """TLC-style 6-7 digit driver license number."""
    return str(int(rng.integers(100_000, 10_000_000)))


def ny_plate(rng: Generator) -> str:
    """NY-style plate: three letters, hyphen, four digits."""
    letters = "".join(rng.choice(list(ascii_uppercase), size=3))
    return f"{letters}-{int(rng.integers(1000, 10000))}"


def vehicle_vin(rng: Generator) -> str:
    """17-character VIN (excludes I/O/Q)."""
    return "".join(rng.choice(list(VIN_CHARS), size=17))


def payment_token(rng: Generator) -> str:
    """16 hex characters."""
    return rng.bytes(8).hex()


def phone(rng: Generator) -> str:
    """US 10-digit phone in a separator format chosen to stress detection."""
    area = rng.integers(200, 989)
    pre = rng.integers(200, 989)
    line = rng.integers(0, 9999)
    if bool(rng.integers(0, 2)):
        return f"({area}) {pre}-{line:04d}"
    sep = rng.choice([".", " ", "-", ""])
    return f"{area}{sep}{pre}{sep}{line:04d}"
