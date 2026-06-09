"""Classification and PII detection.

Tiers every column via the versioned classification dictionary, scans the
free-text support note with Presidio plus custom recognizers, and measures
detection precision/recall/F1 against the synthetic ground-truth span labels.
"""
