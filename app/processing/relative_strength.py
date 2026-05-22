from __future__ import annotations

import pandas as pd


def relative_strength(asset_close: float, benchmark_close: float) -> float:
    if benchmark_close in (0, None) or pd.isna(benchmark_close):
        return float("nan")
    return asset_close / benchmark_close


def add_relative_strength(asset_weekly: pd.DataFrame, benchmark_weekly: pd.DataFrame) -> pd.DataFrame:
    bench = benchmark_weekly[["week_date", "close"]].rename(columns={"close": "benchmark_close"})
    data = asset_weekly.merge(bench, on="week_date", how="inner")
    data["relative_strength"] = data["close"] / data["benchmark_close"]
    return data
