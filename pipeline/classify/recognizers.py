"""Custom Presidio pattern recognizers for formats it does not cover out of the box.

- TLC_LICENSE: a bare 6-7 digit number is ambiguous (looks like a confirmation
  number or fare), so its base pattern score sits below threshold and only crosses
  it when license context words ("TLC", "license") appear nearby. This is the
  precision lever against decoy numerics.
- NY_PLATE, VEHICLE_VIN: distinctive formats, scored above threshold on shape.
- CREDIT_CARD (masked): Presidio's built-in only matches Luhn-valid full numbers;
  riders quote masked partials, so we add a pattern for those.
"""

from __future__ import annotations

import re

from presidio_analyzer import Pattern, PatternRecognizer

# Entity types this module supplies (aligned with the synthetic label types).
TLC_LICENSE = "TLC_LICENSE"
NY_PLATE = "NY_PLATE"
VEHICLE_VIN = "VEHICLE_VIN"
CREDIT_CARD = "CREDIT_CARD"
PHONE_NUMBER = "PHONE_NUMBER"
LOCATION = "LOCATION"


def _tlc_license() -> PatternRecognizer:
    pattern = Pattern(name="tlc_license_digits", regex=r"\b\d{6,7}\b", score=0.3)
    return PatternRecognizer(
        supported_entity=TLC_LICENSE,
        patterns=[pattern],
        context=["tlc", "license", "lic", "medallion", "hack", "driver"],
        name="tlc_license_recognizer",
    )


def _ny_plate() -> PatternRecognizer:
    pattern = Pattern(name="ny_plate", regex=r"\b[A-Z]{3}-?\d{4}\b", score=0.6)
    return PatternRecognizer(
        supported_entity=NY_PLATE,
        patterns=[pattern],
        context=["plate", "license plate", "tag", "vehicle"],
        name="ny_plate_recognizer",
    )


def _vehicle_vin() -> PatternRecognizer:
    # 17 chars, excluding I/O/Q per the VIN standard.
    pattern = Pattern(name="vin17", regex=r"\b[A-HJ-NPR-Z0-9]{17}\b", score=0.7)
    return PatternRecognizer(
        supported_entity=VEHICLE_VIN,
        patterns=[pattern],
        context=["vin", "vehicle", "chassis"],
        name="vehicle_vin_recognizer",
    )


def _masked_card() -> PatternRecognizer:
    pattern = Pattern(
        name="masked_card",
        regex=r"(?:\*{4}|x{4}|(?:xxxx[- ]?){3})\d{4}",
        score=0.7,
    )
    return PatternRecognizer(
        supported_entity=CREDIT_CARD,
        patterns=[pattern],
        context=["card", "ending", "charged", "payment"],
        name="masked_card_recognizer",
    )


def _us_phone() -> PatternRecognizer:
    # Covers (NNN) NNN-NNNN and NNN[. -]NNN[. -]NNNN incl. no-separator, which
    # Presidio's phonenumbers-based recognizer misses for our generated formats.
    # Lookarounds keep it from matching inside longer digit runs (VINs, tokens).
    pattern = Pattern(
        name="us_phone",
        regex=r"(?<!\d)(?:\(\d{3}\)\s?|\d{3}[.\s-]?)\d{3}[.\s-]?\d{4}(?!\d)",
        score=0.8,
    )
    return PatternRecognizer(
        supported_entity=PHONE_NUMBER,
        patterns=[pattern],
        context=["phone", "call", "called", "reachable", "contact", "number"],
        name="us_phone_recognizer",
    )


def _street_address() -> PatternRecognizer:
    # House number + capitalized street name(s), including the no-suffix hard case
    # ("842 Sandra"). Scored above spaCy's PERSON (0.85) so deconfliction keeps the
    # LOCATION and drops the street-name-as-PERSON false positive.
    pattern = Pattern(
        name="street_address",
        regex=r"\b\d{1,5}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}",
        score=0.9,
    )
    return PatternRecognizer(
        supported_entity=LOCATION,
        patterns=[pattern],
        context=["near", "pickup", "dropoff", "address", "located", "corner", "block"],
        name="street_address_recognizer",
        # Case-sensitive: the capitalized street name is the signal. Presidio's
        # default IGNORECASE would match lowercase words ("9 minutes", "8143 about").
        global_regex_flags=re.MULTILINE | re.DOTALL,
    )


def custom_recognizers() -> list[PatternRecognizer]:
    """All custom recognizers to register on the analyzer."""
    return [
        _tlc_license(),
        _ny_plate(),
        _vehicle_vin(),
        _masked_card(),
        _us_phone(),
        _street_address(),
    ]
