"""Salted SHA-256 pseudonymization.

Pure functions. A salt is generated per export run (see pipeline.io.salts) and
referenced in the ledger by its SHA-256 fingerprint, never by value. Same salt
=> same pseudonyms (joinable within a release); different salt => disjoint
pseudonyms (no cross-release linkage). This is pseudonymization, not
anonymization (limitations.md L-06).
"""

from __future__ import annotations

import hashlib

import pandas as pd

DEFAULT_LENGTH = 16  # hex chars of the digest to keep (64 bits; ample for our key spaces)


def salt_fingerprint(salt: bytes) -> str:
    """SHA-256 fingerprint of a salt, for ledger reference (never the salt itself)."""
    return hashlib.sha256(salt).hexdigest()


def pseudonymize_value(value: object, salt: bytes, length: int = DEFAULT_LENGTH) -> str:
    """Return the salted SHA-256 pseudonym of a single value."""
    digest = hashlib.sha256(salt + str(value).encode("utf-8")).hexdigest()
    return digest[:length]


def pseudonymize(series: pd.Series, salt: bytes, length: int = DEFAULT_LENGTH) -> pd.Series:
    """Pseudonymize a column. Null values pass through as null."""
    return series.map(lambda v: None if pd.isna(v) else pseudonymize_value(v, salt, length))
