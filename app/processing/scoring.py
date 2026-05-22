from __future__ import annotations

import math

import pandas as pd


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    if value is None or pd.isna(value) or math.isinf(value):
        return 0.0
    return float(max(low, min(high, value)))


def scale(value: float, low: float, high: float) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return clamp((value - low) / (high - low) * 100)


def score_individual(rs_ratio: float, rs_momentum: float, volume_relative: float, relative_return: float) -> float:
    score = (
        scale(rs_ratio, 95, 110) * 0.35
        + scale(rs_momentum, 95, 110) * 0.25
        + scale(volume_relative, 0.6, 1.8) * 0.25
        + scale(relative_return, -0.05, 0.08) * 0.15
    )
    return round(clamp(score), 2)


def score_sector(
    rs_ratio: float,
    rs_momentum: float,
    volume_relative: float,
    internal_confirmation: float,
    macro_score: float | None = None,
) -> float:
    base_weights = {"rs": 25, "momentum": 20, "volume": 25, "confirmation": 20}
    macro_weight = 10 if macro_score is not None else 0
    total = sum(base_weights.values()) + macro_weight
    if macro_score is None:
        factor = 100 / total
        weights = {key: value * factor for key, value in base_weights.items()}
    else:
        weights = base_weights
    score = (
        scale(rs_ratio, 95, 110) * weights["rs"] / 100
        + scale(rs_momentum, 95, 110) * weights["momentum"] / 100
        + scale(volume_relative, 0.6, 1.8) * weights["volume"] / 100
        + scale(internal_confirmation, 0, 1) * weights["confirmation"] / 100
    )
    if macro_score is not None:
        score += clamp(macro_score) * macro_weight / 100
    return round(clamp(score), 2)
