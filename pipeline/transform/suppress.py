"""Suppression transforms: whole-column drop and free-text span redaction.

``redact_spans`` masks PII spans in place using offsets from the Phase 2
detector, keeping the non-PII text. It is pure (offsets in, masked text out); the
detection source is wired at the composition layer so this module stays
decoupled from the classifier.
"""

from __future__ import annotations

import pandas as pd

REDACTION_MASK = "[REDACTED]"


def drop_columns(df: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, dict]:
    """Drop the named columns if present; return the frame and an audit record."""
    present = [c for c in columns if c in df.columns]
    return df.drop(columns=present), {"dropped_columns": present}


def redact_spans(text: str, spans: list[tuple[int, int]], mask: str = REDACTION_MASK) -> str:
    """Replace each (start, end) span with ``mask``, processing right-to-left so
    earlier offsets stay valid as the string length changes."""
    redacted = text
    for start, end in sorted(spans, key=lambda s: s[0], reverse=True):
        redacted = redacted[:start] + mask + redacted[end:]
    return redacted


def redact_series(
    texts: pd.Series,
    detections: list[list[dict]],
    mask: str = REDACTION_MASK,
) -> tuple[pd.Series, dict]:
    """Redact a column of free text given per-row detection records.

    ``detections[i]`` holds the detection dicts ({start, end, ...}) for ``texts.iloc[i]``.
    Returns the redacted series and an audit record (rows touched, spans masked).
    """
    out: list[str | None] = []
    rows_redacted = 0
    spans_masked = 0
    for value, dets in zip(texts.tolist(), detections, strict=True):
        if value is None or pd.isna(value) or not dets:
            out.append(value)
            continue
        spans = [(d["start"], d["end"]) for d in dets]
        out.append(redact_spans(str(value), spans, mask))
        rows_redacted += 1
        spans_masked += len(spans)
    audit = {"rows_redacted": rows_redacted, "spans_masked": spans_masked}
    return pd.Series(out, index=texts.index, dtype="string"), audit
