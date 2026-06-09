"""Evaluation-matcher tests (pure, fast — no Presidio/model needed)."""

from __future__ import annotations

from pipeline.classify import evaluate


def _det(entity, start, end, score=0.9):
    return {"entity_type": entity, "start": start, "end": end, "score": score}


def _gold(entity, start, end):
    return {"entity_type": entity, "start": start, "end": end}


def test_overlap_same_type_is_true_positive():
    tp, fp, fn = evaluate.match_note([_det("PERSON", 0, 5)], [_gold("PERSON", 2, 8)])
    assert tp == ["PERSON"] and fp == [] and fn == []


def test_type_mismatch_is_fp_and_fn():
    tp, fp, fn = evaluate.match_note([_det("LOCATION", 0, 5)], [_gold("PERSON", 0, 5)])
    assert tp == [] and fp == ["LOCATION"] and fn == ["PERSON"]


def test_no_overlap_is_fp_and_fn():
    tp, fp, fn = evaluate.match_note([_det("PERSON", 0, 4)], [_gold("PERSON", 10, 14)])
    assert tp == [] and fp == ["PERSON"] and fn == ["PERSON"]


def test_detection_on_decoy_is_false_positive():
    tp, fp, fn = evaluate.match_note([_det("TLC_LICENSE", 0, 7)], [])
    assert tp == [] and fp == ["TLC_LICENSE"] and fn == []


def test_missed_gold_is_false_negative():
    tp, fp, fn = evaluate.match_note([], [_gold("PHONE_NUMBER", 0, 12)])
    assert tp == [] and fp == [] and fn == ["PHONE_NUMBER"]


def test_one_detection_cannot_satisfy_two_gold_spans():
    # A single wide detection overlaps two adjacent gold spans; only one is a TP.
    tp, fp, fn = evaluate.match_note(
        [_det("PERSON", 0, 20)],
        [_gold("PERSON", 1, 5), _gold("PERSON", 10, 15)],
    )
    assert tp == ["PERSON"]
    assert fn == ["PERSON"]


def test_evaluate_aggregates_prf():
    detections = [[_det("PERSON", 0, 5)], [_det("LOCATION", 0, 5)], []]
    gold = [[_gold("PERSON", 0, 5)], [_gold("PERSON", 0, 5)], [_gold("EMAIL_ADDRESS", 0, 5)]]
    result = evaluate.evaluate(detections, gold)
    # PERSON: 1 TP, 1 FN (second note had a LOCATION detection, not PERSON)
    assert result["per_entity"]["PERSON"]["tp"] == 1
    assert result["per_entity"]["PERSON"]["fn"] == 1
    assert result["per_entity"]["PERSON"]["recall"] == 0.5
    # LOCATION: 1 FP; EMAIL: 1 FN
    assert result["per_entity"]["LOCATION"]["fp"] == 1
    assert result["per_entity"]["EMAIL_ADDRESS"]["fn"] == 1
    # overall micro: TP=1, FP=1, FN=2
    assert result["overall"]["tp"] == 1
    assert result["overall"]["fp"] == 1
    assert result["overall"]["fn"] == 2
