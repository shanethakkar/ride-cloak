"""Held-out, unseen-format PII evaluation (format-split, not row-split).

The Phase-2 recognizers were tuned to the formats in pipeline/synth/templates.py and
identifiers.py, so the in-distribution precision/recall measures fit, not generalization.
This module generates notes using PII formats the recognizers were NOT built for, then
scores the *unmodified* recognizers on them, to estimate how detection holds up across
format variation.

Two probe kinds:
- format generalization: the value's shape does not match the recognizer regex (phone with
  slashes, numbered-street addresses, place names, masked cards grouped differently, spaced
  plates/VINs). Built-in components (spaCy PERSON, Presidio EMAIL) are included for contrast.
- context generalization: TLC_LICENSE keeps the same 6-7 digit shape but appears without any
  of the recognizer's trigger words.

Caveat: this is synthetic-to-synthetic. It measures generalization across format variation we
imagined, not real-world performance. Do not read it as a real-world generalization figure.
"""

from __future__ import annotations

import numpy as np
from faker import Faker

PHONE = "PHONE_NUMBER"
EMAIL = "EMAIL_ADDRESS"
PERSON = "PERSON"
LOCATION = "LOCATION"
CREDIT_CARD = "CREDIT_CARD"
TLC_LICENSE = "TLC_LICENSE"
NY_PLATE = "NY_PLATE"
VEHICLE_VIN = "VEHICLE_VIN"

# A part is a literal str, or a labelled span tuple (entity_type, value).
_Part = str | tuple[str, str]

_VIN_CHARS = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
_ORDINALS = ("3rd", "5th", "7th", "8th", "23rd", "42nd", "57th")
_STREET_KINDS = ("Avenue", "Street", "Boulevard")
_NEIGHBORHOODS = (
    "Astoria",
    "Williamsburg",
    "Flushing",
    "Harlem",
    "Chelsea",
    "Tribeca",
    "Bushwick",
    "Bensonhurst",
)
_NAME_SUFFIXES = ("Jr.", "III", "Sr.")


# --- held-out value generators (format generalization) -----------------------


def ho_phone_slash(rng: np.random.Generator) -> str:
    """Slash-separated phone: the recognizer's separators are only [.\\s-]."""
    return f"{rng.integers(200, 989)}/{rng.integers(200, 989)}/{rng.integers(0, 9999):04d}"


def ho_phone_grouped(rng: np.random.Generator) -> str:
    """Trailing block grouped 2-2 ('212 555 12 34'); breaks the final \\d{4}."""
    a, p, last = rng.integers(200, 989), rng.integers(200, 989), int(rng.integers(0, 9999))
    return f"{a} {p} {last // 100:02d} {last % 100:02d}"


def ho_address_numbered(rng: np.random.Generator) -> str:
    """Numbered street ('200 5th Avenue'): the ordinal after the house number is not a
    capitalized word, so the address recognizer never starts a match."""
    n = int(rng.integers(1, 999))
    return f"{n} {rng.choice(_ORDINALS)} {rng.choice(_STREET_KINDS)}"


def ho_place(rng: np.random.Generator) -> str:
    """A neighborhood name with no house number (not an address shape at all)."""
    return str(rng.choice(_NEIGHBORHOODS))


def ho_card_last4(rng: np.random.Generator) -> str:
    """Just the last four digits, the way riders say 'ending in 1234'."""
    return f"{rng.integers(0, 9999):04d}"


def ho_card_bullet(rng: np.random.Generator) -> str:
    """Bullet-masked card; the recognizer only knows '*' and 'x' masks."""
    return f"•••• {rng.integers(0, 9999):04d}"


def ho_card_stars_grouped(rng: np.random.Generator) -> str:
    """Star groups with separators; the recognizer's star branch needs the digits adjacent."""
    return f"****-****-****-{rng.integers(0, 9999):04d}"


def ho_plate_spaced(rng: np.random.Generator) -> str:
    """Plate written with a space; the recognizer allows only an optional hyphen."""
    letters = "".join(rng.choice(list("ABCDEFGHJKLMNPRSTUVWXYZ"), size=3))
    return f"{letters} {int(rng.integers(1000, 10000))}"


def ho_vin_spaced(rng: np.random.Generator) -> str:
    """VIN written in spaced groups; the recognizer needs 17 contiguous chars."""
    v = "".join(rng.choice(list(_VIN_CHARS), size=17))
    return f"{v[:5]} {v[5:11]} {v[11:]}"


def ho_email_plus(faker: Faker) -> str:
    return f"{faker.user_name()}+receipts@example.com"


def ho_email_subdomain(faker: Faker) -> str:
    return f"{faker.user_name()}@mail.example.co.uk"


def ho_person(faker: Faker, rng: np.random.Generator) -> str:
    """A name with a generational suffix or an all-caps rendering."""
    name = faker.name()
    roll = rng.random()
    if roll < 0.4:
        return f"{name} {rng.choice(_NAME_SUFFIXES)}"
    if roll < 0.7:
        return name.upper()
    return name


def ho_tlc_nocontext(rng: np.random.Generator) -> str:
    """Same 6-7 digit shape as a TLC license; the template places it without trigger words."""
    return str(int(rng.integers(100_000, 10_000_000)))


# --- templates ---------------------------------------------------------------


def _t_phone_slash(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return [
        (PERSON, ho_person(faker, rng)),
        " called from ",
        (PHONE, ho_phone_slash(rng)),
        " about a refund.",
    ]


def _t_phone_grouped(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return ["Rider is reachable at ", (PHONE, ho_phone_grouped(rng)), " after 6pm."]


def _t_address_numbered(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return ["Pickup was at ", (LOCATION, ho_address_numbered(rng)), " per the rider."]


def _t_place(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return ["Driver waited near ", (LOCATION, ho_place(rng)), " for ten minutes."]


def _t_email_plus(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return [
        (PERSON, ho_person(faker, rng)),
        " emailed ",
        (EMAIL, ho_email_plus(faker)),
        " about the receipt.",
    ]


def _t_email_subdomain(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return ["Follow up with the rider at ", (EMAIL, ho_email_subdomain(faker)), "."]


def _t_card_last4(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return [
        "Rider says the card ending in ",
        (CREDIT_CARD, ho_card_last4(rng)),
        " was charged twice.",
    ]


def _t_card_bullet(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return ["Statement shows ", (CREDIT_CARD, ho_card_bullet(rng)), " for the disputed ride."]


def _t_card_stars(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return ["Receipt lists ", (CREDIT_CARD, ho_card_stars_grouped(rng)), " as the payment method."]


def _t_tlc_nocontext(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    # No trigger words (tlc/license/lic/medallion/hack/driver/number) anywhere in this note.
    return ["Operator badge ", (TLC_LICENSE, ho_tlc_nocontext(rng)), " was flagged at the depot."]


def _t_plate_spaced(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return ["Rider photographed plate ", (NY_PLATE, ho_plate_spaced(rng)), " at dropoff."]


def _t_vin_spaced(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return ["Lost-item claim references VIN ", (VEHICLE_VIN, ho_vin_spaced(rng)), " on file."]


def _d_fare(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return [f"Rider disputed the fare of ${rng.integers(500, 9999) / 100:.2f}; no action taken."]


def _d_wait(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return [f"Driver waited {rng.integers(2, 20)} minutes at the curb; informational only."]


def _d_confirmation(faker: Faker, rng: np.random.Generator) -> list[_Part]:
    return [f"Confirmation {rng.integers(1_000_000, 9_999_999)} issued for the rebooked ride."]


PII_TEMPLATES = [
    _t_phone_slash,
    _t_phone_grouped,
    _t_address_numbered,
    _t_place,
    _t_email_plus,
    _t_email_subdomain,
    _t_card_last4,
    _t_card_bullet,
    _t_card_stars,
    _t_tlc_nocontext,
    _t_plate_spaced,
    _t_vin_spaced,
]

DECOY_TEMPLATES = [_d_fare, _d_wait, _d_confirmation]

PII_NOTE_SHARE = 0.7


def _render(parts: list[_Part]) -> tuple[str, list[dict]]:
    text = ""
    spans: list[dict] = []
    for part in parts:
        if isinstance(part, tuple):
            entity_type, value = part
            start = len(text)
            text += value
            spans.append({"entity_type": entity_type, "start": start, "end": len(text)})
        else:
            text += part
    return text, spans


def generate_heldout(n: int, seed: int) -> tuple[list[str], list[list[dict]]]:
    """Deterministically generate ``n`` held-out notes and their gold spans."""
    rng = np.random.default_rng(seed)
    faker = Faker("en_US")
    faker.seed_instance(seed)
    texts: list[str] = []
    gold: list[list[dict]] = []
    for _ in range(n):
        pool = PII_TEMPLATES if rng.random() < PII_NOTE_SHARE else DECOY_TEMPLATES
        template = pool[int(rng.integers(len(pool)))]
        text, spans = _render(template(faker, rng))
        texts.append(text)
        gold.append(spans)
    return texts, gold
