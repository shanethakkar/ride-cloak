"""Held-out PII eval tests: reproducibility, no overlap with SEEN formats, end to end."""

from __future__ import annotations

import hashlib
import json
import re

import numpy as np
import pytest
import spacy

from pipeline.classify import heldout, recognizers

# Map each custom recognizer's entity to (regex, flags) so we can prove a held-out
# value's shape is not something the recognizer was built for.
_DEFAULT_FLAGS = re.DOTALL | re.MULTILINE | re.IGNORECASE


def _regexes_by_entity() -> dict[str, list[re.Pattern]]:
    out: dict[str, list[re.Pattern]] = {}
    for rec in recognizers.custom_recognizers():
        flags = getattr(rec, "global_regex_flags", _DEFAULT_FLAGS)
        for pat in rec.patterns:
            for entity in rec.supported_entities:
                out.setdefault(entity, []).append(re.compile(pat.regex, flags))
    return out


def test_heldout_is_reproducible():
    a_texts, a_gold = heldout.generate_heldout(500, seed=4242)
    b_texts, b_gold = heldout.generate_heldout(500, seed=4242)
    assert a_texts == b_texts
    assert a_gold == b_gold
    digest = hashlib.sha256(json.dumps([a_texts, a_gold]).encode()).hexdigest()
    again = hashlib.sha256(json.dumps([b_texts, b_gold]).encode()).hexdigest()
    assert digest == again


def test_gold_spans_are_in_bounds_and_nonempty():
    texts, gold = heldout.generate_heldout(300, seed=7)
    for text, spans in zip(texts, gold, strict=True):
        for s in spans:
            assert 0 <= s["start"] < s["end"] <= len(text)
            assert text[s["start"] : s["end"]].strip()


def test_format_holdout_values_do_not_match_their_recognizer_regex():
    """The format-generalization values must not be shapes the recognizers target."""
    rng = np.random.default_rng(123)
    regexes = _regexes_by_entity()
    cases = {
        "PHONE_NUMBER": [heldout.ho_phone_slash(rng), heldout.ho_phone_grouped(rng)],
        "LOCATION": [heldout.ho_address_numbered(rng), heldout.ho_place(rng)],
        "CREDIT_CARD": [
            heldout.ho_card_last4(rng),
            heldout.ho_card_bullet(rng),
            heldout.ho_card_stars_grouped(rng),
        ],
        "NY_PLATE": [heldout.ho_plate_spaced(rng)],
        "VEHICLE_VIN": [heldout.ho_vin_spaced(rng)],
    }
    for entity, values in cases.items():
        for value in values:
            for rx in regexes.get(entity, []):
                assert rx.search(value) is None, (
                    f"{entity} held-out value '{value}' matched {rx.pattern}"
                )


def test_tlc_holdout_is_a_context_probe_not_a_format_probe():
    """TLC keeps the 6-7 digit shape (matches the regex) but the note has no trigger word."""
    value = heldout.ho_tlc_nocontext(np.random.default_rng(1))
    assert re.fullmatch(r"\d{6,7}", value)  # same shape the recognizer targets
    triggers = {"tlc", "license", "lic", "medallion", "hack", "driver", "number"}
    texts, _ = heldout.generate_heldout(400, seed=9)
    tlc_notes = [t for t in texts if "Operator badge" in t]
    assert tlc_notes
    for note in tlc_notes:
        words = set(re.findall(r"[a-z]+", note.lower()))
        assert words.isdisjoint(triggers), f"trigger word leaked into TLC held-out note: {note}"


@pytest.mark.skipif(
    not spacy.util.is_package("en_core_web_lg"), reason="en_core_web_lg not installed"
)
def test_heldout_eval_runs_end_to_end():
    from pipeline.classify import evaluate, pii_scan

    texts, gold = heldout.generate_heldout(40, seed=3)
    analyzer = pii_scan.build_analyzer()
    detections = pii_scan.scan_texts(analyzer, texts)
    result = evaluate.evaluate(detections, gold)
    assert "overall" in result and "precision" in result["overall"]
    assert result["per_entity"]  # at least one entity scored
