from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from app.config import CHARTS_DIR


def generate_unusual_volume_chart(asset_metrics: pd.DataFrame) -> Path | None:
    data = (
        asset_metrics[asset_metrics["volume_relative"] >= 1.5]
        .sort_values("volume_relative", ascending=False)
        .head(12)
        .copy()
    )
    if data.empty:
        return None

    path = CHARTS_DIR / "unusual_volume.png"
    colors = ["#0f766e" if v >= 0 else "#b91c1c" for v in data["weekly_return"]]

    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=150)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#fafafa")

    bars = ax.bar(data["ticker"], data["volume_relative"], color=colors, width=0.6, edgecolor="white", linewidth=0.5)

    for bar, vol in zip(bars, data["volume_relative"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.04, f"{vol:.2f}x", ha="center", va="bottom", fontsize=8, fontweight="bold", color="#374151")

    ax.axhline(1.5, color="#6b7280", linestyle="--", linewidth=1, alpha=0.7)
    ax.text(len(data) - 0.5, 1.52, "limiar 1.5×", fontsize=7.5, color="#6b7280", ha="right")

    ax.set_ylabel("Volume relativo vs. média 8 semanas", fontsize=9, color="#6b7280")
    ax.set_title("Ações com Volume Incomum (≥ 1.5×)", fontsize=12, fontweight="bold", pad=10, color="#111827")
    ax.tick_params(axis="x", labelsize=9, colors="#374151")
    ax.tick_params(axis="y", labelsize=8.5, colors="#6b7280")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#e5e7eb")
    ax.spines["bottom"].set_color("#e5e7eb")
    ax.yaxis.grid(True, color="#e5e7eb", linewidth=0.6)
    ax.set_axisbelow(True)

    from matplotlib.patches import Patch
    legend = [Patch(color="#0f766e", label="Alta na semana"), Patch(color="#b91c1c", label="Queda na semana")]
    ax.legend(handles=legend, fontsize=8, loc="upper right", framealpha=0.85)

    fig.autofmt_xdate(rotation=30, ha="right")
    fig.tight_layout(pad=1.2)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.15, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path
