"""Presidio analyzer wiring and free-text scanning.

Builds an AnalyzerEngine backed by the spaCy model with the custom recognizers
registered, and scans a sequence of support-note texts into detection records.
Only the free text is scanned; structured columns are classified by the
dictionary, not by Presidio.
"""

from __future__ import annotations

from functools import lru_cache

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from pipeline.classify.recognizers import custom_recognizers

# Entity types evaluated against the synthetic labels (the target set).
TARGET_ENTITIES = [
    "PERSON",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "LOCATION",
    "CREDIT_CARD",
    "TLC_LICENSE",
    "NY_PLATE",
    "VEHICLE_VIN",
]

DEFAULT_MODEL = "en_core_web_lg"
DEFAULT_THRESHOLD = 0.5


@lru_cache(maxsize=2)
def build_analyzer(model: str = DEFAULT_MODEL) -> AnalyzerEngine:
    """Construct (and cache) an AnalyzerEngine with custom recognizers registered."""
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": model}],
        }
    )
    analyzer = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])
    for recognizer in custom_recognizers():
        analyzer.registry.add_recognizer(recognizer)
    return analyzer


def _deconflict(records: list[dict]) -> list[dict]:
    """Resolve overlapping detections: keep the highest-scoring, drop the rest.

    Fixes the street-name-as-PERSON case (the address recognizer outscores spaCy's
    PERSON, so the spurious PERSON over the street name is dropped). Gold spans
    never overlap each other, so dropping overlaps only removes false positives.
    """
    kept: list[dict] = []
    for r in sorted(records, key=lambda x: (-x["score"], -(x["end"] - x["start"]))):
        if any(r["start"] < k["end"] and k["start"] < r["end"] for k in kept):
            continue
        kept.append(r)
    return sorted(kept, key=lambda x: x["start"])


def scan_text(
    analyzer: AnalyzerEngine,
    text: str | None,
    entities: list[str] | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[dict]:
    """Return deconflicted detection records ``{entity_type, start, end, score}``."""
    if not text:
        return []
    results = analyzer.analyze(
        text=text,
        language="en",
        entities=entities or TARGET_ENTITIES,
        score_threshold=threshold,
    )
    records = [
        {"entity_type": r.entity_type, "start": r.start, "end": r.end, "score": float(r.score)}
        for r in results
    ]
    return _deconflict(records)


def scan_texts(
    analyzer: AnalyzerEngine,
    texts: list[str | None],
    entities: list[str] | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[list[dict]]:
    """Scan many texts; element i holds the detections for ``texts[i]``."""
    return [scan_text(analyzer, t, entities, threshold) for t in texts]
