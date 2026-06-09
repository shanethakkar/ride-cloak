"""Custom-recognizer behavior + the end-to-end detection target.

These need the spaCy model and (for the target test) the dev slice, so they skip
cleanly where those are absent. The analyzer is built once per module.
"""

from __future__ import annotations

import pytest
import spacy

from config.settings import get_settings
from pipeline.classify import evaluate, pii_scan

pytestmark = pytest.mark.skipif(
    not spacy.util.is_package(pii_scan.DEFAULT_MODEL),
    reason=f"{pii_scan.DEFAULT_MODEL} not installed",
)

settings = get_settings()


@pytest.fixture(scope="module")
def analyzer():
    return pii_scan.build_analyzer()


def _types(analyzer, text):
    return {d["entity_type"] for d in pii_scan.scan_text(analyzer, text)}


def test_tlc_license_fires_with_context(analyzer):
    assert "TLC_LICENSE" in _types(
        analyzer, "Complaint filed against TLC license 1234567; driver John Smith contacted."
    )


def test_bare_confirmation_number_is_not_a_license(analyzer):
    # No license context -> the ambiguous 7-digit number must not be flagged.
    assert "TLC_LICENSE" not in _types(
        analyzer, "Confirmation number 4839271 issued for the rebooked ride."
    )


def test_plate_and_address(analyzer):
    types = _types(analyzer, "Rider reported plate ABC-1234 for an incident near 842 Sandra.")
    assert "NY_PLATE" in types
    assert "LOCATION" in types


def test_vin_and_phone(analyzer):
    types = _types(
        analyzer,
        "Lost-and-found claim for VIN 1HGCM82633A004352; rider Jane Doe at 212.555.1234.",
    )
    assert "VEHICLE_VIN" in types
    assert "PHONE_NUMBER" in types


def test_masked_card(analyzer):
    assert "CREDIT_CARD" in _types(analyzer, "Payment dispute: card ending ****1234 twice.")


@pytest.mark.parametrize("number", ["(443) 297-8143", "738 703 4191", "2125551234", "570.975.3835"])
def test_phone_formats(analyzer, number):
    assert "PHONE_NUMBER" in _types(analyzer, f"Rider reachable at {number} about a refund.")


def test_detection_meets_targets(analyzer):
    """End to end on the dev slice: overall recall >= 0.95 and precision >= 0.90."""
    from pipeline.io import readers

    if not settings.dev_slice_path.exists() or not settings.labels_path.exists():
        pytest.skip("dev slice/labels not built; run `ridecloak synth --input dev`")
    df = readers.read_parquet(settings.dev_slice_path)
    labels = readers.read_parquet(settings.labels_path)
    noted = df[df["support_note"].notna()].sort_values("trip_id")
    detections = pii_scan.scan_texts(analyzer, noted["support_note"].astype(str).tolist())
    gold = evaluate.gold_from_labels(labels, noted["trip_id"].tolist())
    overall = evaluate.evaluate(detections, gold)["overall"]
    assert overall["recall"] >= 0.95
    assert overall["precision"] >= 0.90
