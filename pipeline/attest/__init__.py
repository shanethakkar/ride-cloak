"""Attestation: a hash-chained append-only ledger and the methodology report.

Every pipeline command appends a tamper-evident entry; ``verify`` walks the chain
and reports the exact break point if any entry was altered. The methodology
report regenerates byte-identically from a ledger entry.
"""
