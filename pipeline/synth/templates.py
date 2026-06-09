"""Support-note templates for the synthetic free-text field.

A template returns an ordered list of *parts*. Each part is either a literal
string or a PII token ``(PII, entity_type, value)``. The generator concatenates
parts and records exact character offsets for every PII token, which becomes the
ground truth for measuring Presidio precision/recall in Phase 2.

The set deliberately includes hard cases (names mid-sentence, phone numbers with
dot/space separators, addresses without a St/Ave suffix) and decoy notes whose
numerics (trip ids, fare amounts) must NOT be flagged, so precision is a real
test rather than a formality.
"""

from __future__ import annotations

from collections.abc import Callable

from faker import Faker
from numpy.random import Generator

# A part is a literal str, or a PII tuple: ("PII", entity_type, value).
PiiPart = tuple[str, str, str]
Part = str | PiiPart
PartList = list[Part]

PII = "PII"

# Presidio-aligned entity types so Phase 2 evaluation maps cleanly.
PERSON = "PERSON"
PHONE = "PHONE_NUMBER"
EMAIL = "EMAIL_ADDRESS"
LOCATION = "LOCATION"
CREDIT_CARD = "CREDIT_CARD"


# --- value generators --------------------------------------------------------


def _phone(rng: Generator) -> str:
    """US 10-digit phone in a separator format chosen to stress detection."""
    area = rng.integers(200, 989)
    pre = rng.integers(200, 989)
    line = rng.integers(0, 9999)
    sep = rng.choice([".", " ", "-", ""])
    paren = bool(rng.integers(0, 2))
    if paren:
        return f"({area}) {pre}-{line:04d}"
    return f"{area}{sep}{pre}{sep}{line:04d}"


def _address_no_suffix(faker: Faker, rng: Generator) -> str:
    """Street address with the St/Ave suffix omitted (a known hard case)."""
    number = rng.integers(10, 2999)
    # Faker street names usually carry a suffix; drop the last token.
    name = faker.street_name().rsplit(" ", 1)[0]
    return f"{number} {name}"


def _partial_card(rng: Generator) -> str:
    """A partial card number as riders quote it in support chats."""
    last4 = rng.integers(0, 9999)
    masked = rng.choice([f"****{last4:04d}", f"xxxx-xxxx-xxxx-{last4:04d}"])
    return str(masked)


# --- PII templates (each yields at least one labeled span) -------------------


def _t_name_phone(faker: Faker, rng: Generator) -> PartList:
    return [
        "Spoke with ",
        (PII, PERSON, faker.name()),
        " who called from ",
        (PII, PHONE, _phone(rng)),
        " about a lost item.",
    ]


def _t_email_followup(faker: Faker, rng: Generator) -> PartList:
    return [
        "Rider asked us to follow up at ",
        (PII, EMAIL, faker.email()),
        " regarding the fare adjustment.",
    ]


def _t_name_midsentence(faker: Faker, rng: Generator) -> PartList:
    return [
        "Driver reported that ",
        (PII, PERSON, faker.name()),
        " left a phone in the back seat near ",
        (PII, LOCATION, _address_no_suffix(faker, rng)),
        ".",
    ]


def _t_card_dispute(faker: Faker, rng: Generator) -> PartList:
    return [
        "Payment dispute: card ending ",
        (PII, CREDIT_CARD, _partial_card(rng)),
        " was charged twice. Caller ",
        (PII, PERSON, faker.name()),
        " requests a callback.",
    ]


def _t_pickup_correction(faker: Faker, rng: Generator) -> PartList:
    return [
        "Pickup correction requested for ",
        (PII, LOCATION, _address_no_suffix(faker, rng)),
        "; rider reachable at ",
        (PII, PHONE, _phone(rng)),
        ".",
    ]


def _t_multi(faker: Faker, rng: Generator) -> PartList:
    return [
        (PII, PERSON, faker.name()),
        " (",
        (PII, EMAIL, faker.email()),
        ", ",
        (PII, PHONE, _phone(rng)),
        ") reported a billing error.",
    ]


# --- decoy templates (zero labeled spans; numerics must not be flagged) ------


def _d_fare_dispute(faker: Faker, rng: Generator) -> PartList:
    fare = rng.integers(500, 9999) / 100
    return [f"Rider disputed the fare amount of ${fare:.2f}; reviewed and upheld, no action."]


def _d_trip_ref(faker: Faker, rng: Generator) -> PartList:
    ref = "".join(rng.choice(list("0123456789abcdef"), size=12))
    return [f"Trip reference {ref} flagged for a routing anomaly; auto-resolved by the system."]


def _d_generic(faker: Faker, rng: Generator) -> PartList:
    waited = rng.integers(2, 20)
    return [f"Rider noted the driver waited {waited} minutes at the curb. Marked informational."]


PII_TEMPLATES: list[Callable[[Faker, Generator], PartList]] = [
    _t_name_phone,
    _t_email_followup,
    _t_name_midsentence,
    _t_card_dispute,
    _t_pickup_correction,
    _t_multi,
]

DECOY_TEMPLATES: list[Callable[[Faker, Generator], PartList]] = [
    _d_fare_dispute,
    _d_trip_ref,
    _d_generic,
]
