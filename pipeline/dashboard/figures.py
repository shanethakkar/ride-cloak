"""Matplotlib figures for the article and the explainer video.

Renders committed PNGs from the dashboard tables. Uses the Agg backend (no
display). Each figure is a function of a DataFrame so it is unit-testable.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from config.settings import Settings  # noqa: E402
from pipeline.dashboard import extract  # noqa: E402

# Order the uniqueness ladder from finest to coarsest QI for the headline chart.
_LADDER_ORDER = ["zone x minute", "zone x 15min", "zone x 60min", "borough x 15min"]


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_uniqueness_ladder(uniqueness: pd.DataFrame, month: str, path: Path) -> Path:
    """Bar chart: re-identification uniqueness collapses as the QI is generalized."""
    sel = uniqueness[(uniqueness["month"] == month) & (uniqueness["scope"] == "month")]
    d = sel.set_index("qi")["uniqueness"]
    labels = [q for q in _LADDER_ORDER if q in d.index]
    vals = [d[q] * 100 for q in labels]
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.barh(labels, vals, color="#b5651d")
    ax.invert_yaxis()
    ax.set_xlabel("trips unique on the quasi-identifier (%)")
    ax.set_title(f"Re-identification uniqueness by generalization ({month})")
    for b, v in zip(bars, vals, strict=True):
        ax.text(v + 1, b.get_y() + b.get_height() / 2, f"{v:.1f}%", va="center")
    ax.set_xlim(0, 100)
    return _save(fig, path)


def fig_detection(detection: pd.DataFrame, path: Path) -> Path:
    """Grouped bars: per-entity precision and recall."""
    d = detection[detection["entity"] != "overall"].sort_values("entity")
    x = range(len(d))
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar([i - 0.2 for i in x], d["precision"], width=0.4, label="precision", color="#2a6f97")
    ax.bar([i + 0.2 for i in x], d["recall"], width=0.4, label="recall", color="#89c2d9")
    ax.set_xticks(list(x))
    ax.set_xticklabels(d["entity"], rotation=30, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("score")
    ax.set_title("PII detection precision / recall by entity (synthetic ground truth)")
    ax.legend()
    return _save(fig, path)


def fig_health_trend(validation: pd.DataFrame, path: Path) -> Path:
    """Line: validation health score across months."""
    d = validation[validation["scope"] == "month"].dropna(subset=["month"])
    d = d.groupby("month")["health_score"].last()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(d.index, d.values, marker="o", color="#1b9e77")
    ax.set_ylim(min(90, d.min() - 1), 100.5)
    ax.set_ylabel("health score (0-100)")
    ax.set_title("Validation health score by month")
    return _save(fig, path)


def fig_suppression_trend(suppression: pd.DataFrame, path: Path) -> Path:
    """Line: borough-level k-suppression cost across months."""
    d = suppression[suppression["qi"].str.startswith("borough")]
    d = d[d["month"].str.match(r"\d{4}-\d{2}")].groupby("month")["suppressed"].last()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(d.index, [v * 100 for v in d.values], marker="o", color="#d95f02")
    ax.set_ylabel("rows suppressed at borough x bucket, k=5 (%)")
    ax.set_title("k-anonymity suppression cost by month (borough-level)")
    return _save(fig, path)


def render_all(settings: Settings, month: str | None = None) -> dict[str, Path]:
    """Build the tables and render every figure to ``outputs/figures/``."""
    month = month or settings.dev_source_month
    tables = extract.build_all(settings)
    out = settings.figures_dir
    figures: dict[str, Path] = {}
    if not tables["uniqueness"].empty:
        figures["uniqueness_ladder"] = fig_uniqueness_ladder(
            tables["uniqueness"], month, out / "uniqueness_ladder.png"
        )
    if not tables["detection"].empty:
        figures["detection"] = fig_detection(tables["detection"], out / "detection.png")
    if not tables["validation"].empty:
        figures["health_trend"] = fig_health_trend(tables["validation"], out / "health_trend.png")
    if not tables["suppression"].empty:
        figures["suppression_trend"] = fig_suppression_trend(
            tables["suppression"], out / "suppression_trend.png"
        )
    return figures
