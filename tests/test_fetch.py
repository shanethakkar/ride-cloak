"""Fetch/manifest tests: streaming hash + size are correct and atomic.

Uses a local file:// URL so the download path is exercised without network.
"""

from __future__ import annotations

import hashlib

from pipeline.io import fetch


def test_stream_download_hashes_and_sizes(tmp_path):
    payload = b"trip,record\n" * 5000
    src = tmp_path / "src.bin"
    src.write_bytes(payload)
    dest = tmp_path / "nested" / "dest.bin"

    sha, size = fetch._stream_download(src.as_uri(), dest)

    assert dest.exists()
    assert dest.read_bytes() == payload
    assert size == len(payload)
    assert sha == hashlib.sha256(payload).hexdigest()
    # No leftover temp part file.
    assert not dest.with_suffix(dest.suffix + ".part").exists()


def test_stream_download_overwrites_idempotently(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"abc")
    dest = tmp_path / "dest.bin"

    fetch._stream_download(src.as_uri(), dest)
    sha2, size2 = fetch._stream_download(src.as_uri(), dest)

    assert size2 == 3
    assert sha2 == hashlib.sha256(b"abc").hexdigest()
