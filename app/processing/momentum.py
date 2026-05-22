from __future__ import annotations

import pandas as pd


def rs_ratio(relative_strength_value: float, moving_average_value: float) -> float:
    if moving_average_value in (0, None) or pd.isna(moving_average_value):
        return float("nan")
    return 100 * relative_strength_value / moving_average_value


def rs_momentum(rs_ratio_value: float, rs_ratio_four_weeks_ago: float) -> float:
    if rs_ratio_four_weeks_ago in (0, None) or pd.isna(rs_ratio_four_weeks_ago):
        return float("nan")
    return 100 * rs_ratio_value / rs_ratio_four_weeks_ago


def add_rrg_metrics(data: pd.DataFrame) -> pd.DataFrame:
    df = data.sort_values("week_date").copy()
    df["rs_ma_10"] = df["relative_strength"].rolling(10, min_periods=4).mean()
    df["rs_ratio"] = 100 * df["relative_strength"] / df["rs_ma_10"]
    df["rs_momentum"] = 100 * df["rs_ratio"] / df["rs_ratio"].shift(4)
    return df
