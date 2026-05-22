from __future__ import annotations

import pandas as pd


def classify_individual_reading(
    weekly_return: float,
    relative_return: float,
    rs_momentum: float,
    score: float,
) -> str:
    if relative_return > 0 and rs_momentum >= 100 and score >= 60:
        return "Confirma o setor"
    if relative_return < 0 and rs_momentum < 100 and score < 50:
        return "Diverge do setor"
    if rs_momentum >= 100 and relative_return > 0 and 50 <= score <= 60:
        return "Força relativa em melhora"
    if rs_momentum < 100 and relative_return < 0 and 40 <= score <= 60:
        return "Perda de força relativa"
    return "Neutra"


def classify_unusual_volume(
    weekly_return: float,
    relative_return: float,
    volume_relative: float,
    threshold: float = 1.5,
) -> str:
    if pd.isna(volume_relative) or volume_relative < threshold:
        return ""
    if weekly_return > 0 and relative_return > 0:
        return "Volume incomum positivo"
    if weekly_return < 0 and relative_return < 0:
        return "Volume incomum negativo"
    if weekly_return > 0 and relative_return <= 0:
        return "Alta nominal, mas sem superar o benchmark"
    if weekly_return < 0 and relative_return >= 0:
        return "Queda nominal, mas desempenho relativo ainda resiliente"
    return "Volume incomum sem direção clara"
