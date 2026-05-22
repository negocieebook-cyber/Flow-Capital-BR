from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from app.config import CHARTS_DIR


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return value.strip("_")


def _draw_rrg(
    data: pd.DataFrame,
    label_col: str,
    title: str,
    output_path: Path,
    figsize: tuple[int, int],
) -> Path:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    plot_data = data.dropna(subset=["rs_ratio", "rs_momentum"]).copy()

    x_delta = max(abs(float(plot_data["rs_ratio"].min()) - 100), abs(float(plot_data["rs_ratio"].max()) - 100)) + 12
    y_delta = max(abs(float(plot_data["rs_momentum"].min()) - 100), abs(float(plot_data["rs_momentum"].max()) - 100)) + 12
    x_min = 100 - x_delta
    x_max = 100 + x_delta
    y_min = 100 - y_delta
    y_max = 100 + y_delta

    fig, ax = plt.subplots(figsize=figsize, dpi=180)
    y_split = (100 - y_min) / (y_max - y_min)
    ax.axvspan(100, x_max, ymin=y_split, ymax=1, color="#e8f5e9", alpha=0.65)
    ax.axvspan(x_min, 100, ymin=y_split, ymax=1, color="#e3f2fd", alpha=0.65)
    ax.axvspan(x_min, 100, ymin=0, ymax=y_split, color="#ffebee", alpha=0.65)
    ax.axvspan(100, x_max, ymin=0, ymax=y_split, color="#fff8e1", alpha=0.65)
    ax.axvline(100, color="#555", linewidth=1)
    ax.axhline(100, color="#555", linewidth=1)

    ax.text(x_max - 5, y_max - 5, "Leading", ha="right", va="top", fontsize=10, weight="bold", color="#14532d")
    ax.text(x_min + 5, y_max - 5, "Improving", ha="left", va="top", fontsize=10, weight="bold", color="#1e3a8a")
    ax.text(x_min + 5, y_min + 5, "Lagging", ha="left", va="bottom", fontsize=10, weight="bold", color="#7f1d1d")
    ax.text(x_max - 5, y_min + 5, "Weakening", ha="right", va="bottom", fontsize=10, weight="bold", color="#78350f")

    offsets = [(8, 5), (-8, 5), (8, -8), (-8, -8)]
    history = plot_data.sort_values("week_date")
    label_count = history[label_col].nunique()
    for idx, (label, group) in enumerate(history.groupby(label_col)):
        group = group.dropna(subset=["rs_ratio", "rs_momentum"]).tail(7)
        if group.empty:
            continue
        offset_x, offset_y = offsets[idx % len(offsets)]
        ax.plot(group["rs_ratio"], group["rs_momentum"], color="#78909c", linewidth=1, alpha=0.8)
        ax.scatter(group["rs_ratio"].iloc[-1], group["rs_momentum"].iloc[-1], s=50, color="#0f766e", zorder=3)
        ax.annotate(
            str(label),
            (group["rs_ratio"].iloc[-1], group["rs_momentum"].iloc[-1]),
            xytext=(offset_x, offset_y),
            textcoords="offset points",
            fontsize=7 if label_count > 8 else 8,
            ha="left" if offset_x > 0 else "right",
            bbox={"boxstyle": "round,pad=0.18", "fc": "white", "ec": "none", "alpha": 0.78},
        )

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel("RS Ratio")
    ax.set_ylabel("RS Momentum")
    ax.set_title(title)
    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    return output_path


def generate_sector_rrg(sector_history: pd.DataFrame) -> Path | None:
    if sector_history.empty:
        return None
    data = sector_history.dropna(subset=["rs_ratio", "rs_momentum"])
    if data.empty:
        return None
    return _draw_rrg(data, "sector", "Flow Map Brasil - RRG Setorial", CHARTS_DIR / "sector_rrg.png", (16, 11))


def generate_stock_rrg(asset_history: pd.DataFrame, sector: str) -> Path | None:
    data = asset_history[asset_history["sector"].eq(sector)].dropna(subset=["rs_ratio", "rs_momentum"])
    if data.empty:
        return None
    return _draw_rrg(data, "ticker", f"RRG de Ações — {sector}", CHARTS_DIR / f"rrg_{slugify(sector)}.png", (14, 9))
