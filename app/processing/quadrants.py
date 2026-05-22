from __future__ import annotations

import pandas as pd


def classify_quadrant(rs_ratio: float, rs_momentum: float) -> str:
    if pd.isna(rs_ratio) or pd.isna(rs_momentum):
        return "Dados insuficientes"
    if rs_ratio >= 100 and rs_momentum >= 100:
        return "Leading"
    if rs_ratio >= 100 and rs_momentum < 100:
        return "Weakening"
    if rs_ratio < 100 and rs_momentum < 100:
        return "Lagging"
    return "Improving"
