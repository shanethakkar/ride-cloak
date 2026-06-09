"""Validation gate: Tier-1 Pandera contract, Tier-2 quality checks, 0-100 health score.

Pure core. ``contract`` and ``checks`` take a DataFrame and return structured audit
records; ``health`` assembles the score. No file or DB I/O lives here.
"""
