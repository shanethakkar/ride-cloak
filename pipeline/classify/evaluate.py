"""Measure detection quality against the synthetic ground-truth spans.

A detection is a true positive if it overlaps a gold span of a compatible entity
type (decisions.md D-0007). Matching is greedy and one-to-one per note so a single
detection cannot satisfy two gold spans. Pure functions over plain records.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

# Normalize detection types to label types where they differ. Empty today (our
# label types already equal Presidio's), but the hook keeps the matcher honest.
ALIAS: dict[str, str] = {}


def _norm(entity_type: str) -> str:
    return ALIAS.get(entity_type, entity_type)


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def match_note(detections: list[dict], gold: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """Return (tp_types, fp_types, fn_types) for one note via greedy matching."""
    gold_state = [
        {"type": g["entity_type"], "s": g["start"], "e": g["end"], "hit": False} for g in gold
    ]
    det_state = [
        {"type": d["entity_type"], "s": d["start"], "e": d["end"], "hit": False} for d in detections
    ]

    tp: list[str] = []
    for g in gold_state:
        for d in det_state:
            if d["hit"] or _norm(d["type"]) != _norm(g["type"]):
                continue
            if _overlaps(d["s"], d["e"], g["s"], g["e"]):
                d["hit"] = True
                g["hit"] = True
                tp.append(g["type"])
                break
    fn = [g["type"] for g in gold_state if not g["hit"]]
    fp = [d["type"] for d in det_state if not d["hit"]]
    return tp, fp, fn


def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def evaluate(detections_per_note: list[list[dict]], gold_per_note: list[list[dict]]) -> dict:
    """Aggregate per-entity and overall (micro-averaged) precision/recall/F1."""
    tp_c: Counter[str] = Counter()
    fp_c: Counter[str] = Counter()
    fn_c: Counter[str] = Counter()
    for detections, gold in zip(detections_per_note, gold_per_note, strict=True):
        tp, fp, fn = match_note(detections, gold)
        tp_c.update(tp)
        fp_c.update(fp)
        fn_c.update(fn)

    entities = sorted(set(tp_c) | set(fp_c) | set(fn_c))
    per_entity = {e: _prf(tp_c[e], fp_c[e], fn_c[e]) for e in entities}
    overall = _prf(sum(tp_c.values()), sum(fp_c.values()), sum(fn_c.values()))
    return {"per_entity": per_entity, "overall": overall}


def gold_from_labels(labels: pd.DataFrame, trip_ids: list[str]) -> list[list[dict]]:
    """Build per-note gold spans aligned to ``trip_ids`` (decoys get an empty list)."""
    by_trip: dict[str, list[dict]] = {}
    for row in labels.itertuples(index=False):
        by_trip.setdefault(row.trip_id, []).append(
            {"entity_type": row.entity_type, "start": int(row.start), "end": int(row.end)}
        )
    return [by_trip.get(tid, []) for tid in trip_ids]
