"""Classification-dictionary tests + a skippable end-to-end detection check."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from config.settings import get_settings
from pipeline.classify import dictionary
from pipeline.classify.dictionary import Tier
from pipeline.synth.generator import SYNTH_COLUMNS
from pipeline.validate.contract import REAL_COLUMNS

settings = get_settings()


def _load():
    return dictionary.load(settings.classification_yaml_path)


def test_every_dev_slice_column_is_classified():
    """SPEC acceptance: no column present in the dev slice is left unclassified."""
    cls = _load()
    present = REAL_COLUMNS + SYNTH_COLUMNS
    assert cls.unclassified(present) == []


def test_tiers_are_assigned_as_expected():
    cls = _load()
    assert cls.tier_of("driver_name") == Tier.DIRECT
    assert cls.tier_of("pickup_datetime") == Tier.QUASI
    assert cls.tier_of("access_a_ride_flag") == Tier.SENSITIVE  # D-0007
    assert cls.tier_of("wav_match_flag") == Tier.SENSITIVE
    assert cls.tier_of("base_passenger_fare") == Tier.SAFE


def test_direct_identifiers_cover_the_synth_pii_columns():
    cls = _load()
    direct = set(cls.columns_in_tier(Tier.DIRECT))
    for col in ("rider_phone", "rider_email", "vehicle_vin", "driver_license_num", "trip_id"):
        assert col in direct


def test_parse_rejects_invalid_tier():
    with pytest.raises(ValidationError):
        dictionary.parse({"version": 1, "columns": {"x": {"tier": "bogus", "rationale": "n/a"}}})
