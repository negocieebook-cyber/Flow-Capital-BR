from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

from app.config import CHARTS_DIR


def _score_color(score: float) -> str:
    if score >= 70:
        return "#14532d"
    if score >= 60:
        return "#0f766e"
    if score >= 50:
        return "#1e40af"
    if score >= 40:
        return "#a16207"
    return "#b91c1c"


def generate_sector_ranking_chart(sector_metrics: pd.DataFrame) -> Path | None:
    if sector_metrics.empty:
        return None
    data = sector_metrics.sort_values("score").tail(10).copy()
    path = CHARTS_DIR / "sector_rankings.png"

    colors = [_score_color(float(s)) for s in data["score"]]
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#fafafa")

    bars = ax.barh(data["sector"], data["score"], color=colors, height=0.6, edgecolor="white", linewidth=0.5)

    for bar, score in zip(bars, data["score"]):
        label = f"{float(score):.1f}"
        x = bar.get_width()
        ax.text(x + 0.8, bar.get_y() + bar.get_height() / 2, label, va="center", fontsize=9, fontweight="bold", color="#374151")

    ax.axvline(60, color="#0f766e", linewidth=1.2, linestyle="--", alpha=0.6)
    ax.axvline(40, color="#b91c1c", linewidth=1.2, linestyle="--", alpha=0.6)
    ax.text(60.5, len(data) - 0.3, "Liderança", fontsize=7, color="#0f766e", alpha=0.8)
    ax.text(40.5, len(data) - 0.3, "Alerta", fontsize=7, color="#b91c1c", alpha=0.8)

    ax.set_xlim(0, 108)
    ax.set_xlabel("Score (0–100)", fontsize=9, color="#6b7280")
    ax.set_title("Ranking de Setores por Score", fontsize=12, fontweight="bold", pad=10, color="#111827")
    ax.tick_params(labelsize=9, colors="#374151")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#e5e7eb")
    ax.spines["bottom"].set_color("#e5e7eb")
    ax.xaxis.grid(True, color="#e5e7eb", linewidth=0.6, linestyle="-")
    ax.set_axisbelow(True)

    fig.tight_layout(pad=1.2)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.15, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path
