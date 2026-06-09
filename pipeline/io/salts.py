"""Per-export salt generation and storage.

Salts live only under ``secrets/salts/`` (gitignored) and are referenced
elsewhere by their SHA-256 fingerprint, never by value. Destroying a salt file
renders its prior exports unlinkable (the erasure story, methodology.md).
"""

from __future__ import annotations

import os
from pathlib import Path

from pipeline.transform.pseudonymize import salt_fingerprint

SALT_BYTES = 16


def generate_salt(nbytes: int = SALT_BYTES) -> bytes:
    """Generate a cryptographically random salt."""
    return os.urandom(nbytes)


def write_salt(salt: bytes, salts_dir: Path) -> Path:
    """Persist a salt under ``salts_dir`` named by its fingerprint; return the path."""
    salts_dir.mkdir(parents=True, exist_ok=True)
    path = salts_dir / f"{salt_fingerprint(salt)}.salt"
    path.write_bytes(salt)
    return path


def read_salt(path: Path) -> bytes:
    return path.read_bytes()
