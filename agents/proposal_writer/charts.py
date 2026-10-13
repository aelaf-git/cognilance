"""Render ChartSpec to PNG bytes with matplotlib (Agg backend)."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docs_ir import ChartSpec


def chart_to_png(chart: "ChartSpec") -> bytes:
    """Return PNG bytes for a bar, line, or pie chart. Raises ValueError if empty."""
    labels = [str(l) for l in (chart.labels or [])]
    values = [float(v) for v in (chart.values or [])]
    if not labels or not values:
        raise ValueError("chart requires labels and values")
    n = min(len(labels), len(values))
    labels, values = labels[:n], values[:n]

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=140)
    kind = (chart.chart_type or "bar").lower()
    title = (chart.title or "").strip()
    series = (chart.series_name or "").strip()

    # Quiet professional palette (avoid neon / purple glow look).
    colors = ["#1f3a4d", "#c45c26", "#4a6b5d", "#8b7355", "#3d5a80", "#6b4f3a"]

    if kind == "pie":
        ax.pie(
            values,
            labels=labels,
            autopct="%1.0f%%",
            colors=colors[:n],
            startangle=90,
            textprops={"fontsize": 9},
        )
        ax.axis("equal")
    elif kind == "line":
        ax.plot(labels, values, color=colors[0], marker="o", linewidth=2)
        ax.set_ylabel(series or "Value")
        ax.grid(True, axis="y", linestyle="--", alpha=0.35)
        for label in ax.get_xticklabels():
            label.set_rotation(25)
            label.set_ha("right")
    else:
        bars = ax.bar(labels, values, color=colors[0], width=0.65)
        ax.set_ylabel(series or "Value")
        ax.grid(True, axis="y", linestyle="--", alpha=0.35)
        for label in ax.get_xticklabels():
            label.set_rotation(25)
            label.set_ha("right")
        if max(values) > 0:
            ax.bar_label(bars, fmt="%.0f", padding=3, fontsize=8)

    if title:
        ax.set_title(title, fontsize=12, pad=10)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()
