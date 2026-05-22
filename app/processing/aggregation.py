from __future__ import annotations

import pandas as pd

from app.processing.quadrants import classify_quadrant
from app.processing.scoring import score_sector


def _confirmation_label(value: float) -> str:
    if pd.isna(value):
        return "dados insuficientes"
    if value >= 0.6:
        return "confirmação ampla"
    if value >= 0.4:
        return "confirmação parcial"
    return "confirmação fraca"


def _narrative_label(row: dict, previous_score: float | None = None) -> str:
    score = row["score"]
    if row["volume_relative"] >= 1.5 and row["weekly_return"] > 0 and row["relative_return"] > 0:
        return "Movimento positivo com volume acima da média."
    if row["volume_relative"] >= 1.5 and row["weekly_return"] < 0 and row["relative_return"] < 0:
        return "Pressão vendedora com volume acima da média."
    if score >= 60 and row["internal_confirmation"] >= 0.6:
        return "Setor em liderança com confirmação ampla entre as ações da cesta."
    if score >= 60 and row["internal_confirmation"] < 0.4:
        return "Setor em destaque, mas com liderança concentrada em poucas ações."
    if score < 60 and row.get("quadrant") == "Leading":
        return "O setor aparece em Leading no RRG, mas ainda sem score suficiente para liderança. A leitura é de melhora relativa, não de convicção plena."
    if score < 50 and row["volume_relative"] < 1:
        return "O setor segue sem confirmação de fluxo, com volume abaixo da média e score ainda fraco."
    if previous_score is not None and not pd.isna(previous_score):
        delta = score - previous_score
        if delta <= -10:
            return "Perda rápida de força."
        if delta >= 10:
            return "Rotação positiva acelerando."
    if score >= 70 and row["volume_relative"] >= 1.3 and row["internal_confirmation"] >= 0.6:
        return "Setor líder com confirmação ampla."
    if score >= 60 and row["rs_momentum"] >= 100 and row["rs_ratio"] < 100:
        return "Setor em melhora, ainda sem liderança completa."
    if score < 40 and row["volume_relative"] >= 1.3 and row["weekly_return"] < 0:
        return "Pressão vendedora com volume acima da média."
    if score >= 60 and row["internal_confirmation"] < 0.4:
        return "Score alto com confirmação interna limitada; leitura pode estar concentrada."
    if score >= 50:
        return "Setor em zona neutra ou de melhora, ainda dependente de confirmação por volume e participação interna."
    if score >= 40:
        return "Setor fraco, mas monitorável; falta confirmação suficiente para leitura de liderança."
    return "Setor fraco ou em alerta dentro da rotação semanal."


def _concentration_alert(group: pd.DataFrame, sector_score: float, internal_confirmation: float) -> str:
    if len(group) < 2:
        return "dados insuficientes"
    best = group.sort_values("score", ascending=False).iloc[0]
    if sector_score >= 60 and internal_confirmation < 0.6:
        return (
            f"O setor apresentou melhora, mas a confirmação interna ainda é limitada. "
            f"A leitura foi concentrada principalmente em {best['ticker']}."
        )
    if sector_score >= 60 and internal_confirmation >= 0.6:
        return "Movimento distribuído entre várias ações do setor."
    return ""


def aggregate_sectors(asset_metrics: pd.DataFrame, previous_sector_metrics: pd.DataFrame | None = None) -> pd.DataFrame:
    rows = []
    prev = {}
    if previous_sector_metrics is not None and not previous_sector_metrics.empty:
        prev = dict(zip(previous_sector_metrics["sector"], previous_sector_metrics["score"]))
    for sector, group in asset_metrics.groupby("sector"):
        valid = group.dropna(subset=["weekly_return", "relative_return", "rs_ratio", "rs_momentum", "score"])
        if len(valid) < 2:
            rows.append(
                {
                    "week_date": group["week_date"].iloc[0],
                    "sector": sector,
                    "weekly_return": None,
                    "benchmark_return": None,
                    "relative_return": None,
                    "rs_ratio": None,
                    "rs_momentum": None,
                    "volume_relative": None,
                    "internal_confirmation": None,
                    "confirmed_stocks_count": 0,
                    "neutral_stocks_count": int(len(group)),
                    "divergent_stocks_count": 0,
                    "unusual_positive_volume_count": 0,
                    "unusual_negative_volume_count": 0,
                    "valid_stocks_count": int(len(valid)),
                    "score": 0,
                    "quadrant": "Dados insuficientes",
                    "narrative_label": "dados insuficientes",
                    "confirmation_label": "dados insuficientes",
                    "concentration_alert": "Setor com menos de 2 ações válidas.",
                }
            )
            continue
        confirmed = valid[(valid["relative_return"] > 0) & (valid["score"] >= 60)]
        divergent = valid[valid["individual_reading"].eq("Diverge do setor")]
        neutral = valid[valid["individual_reading"].eq("Neutra")]
        internal_confirmation = len(confirmed) / len(valid)
        row = {
            "week_date": valid["week_date"].iloc[0],
            "sector": sector,
            "weekly_return": valid["weekly_return"].mean(),
            "benchmark_return": valid["benchmark_return"].mean(),
            "relative_return": valid["relative_return"].mean(),
            "rs_ratio": valid["rs_ratio"].mean(),
            "rs_momentum": valid["rs_momentum"].mean(),
            "volume_relative": valid["volume_relative"].mean(),
            "internal_confirmation": internal_confirmation,
            "confirmed_stocks_count": int(len(confirmed)),
            "neutral_stocks_count": int(len(neutral)),
            "divergent_stocks_count": int(len(divergent)),
            "unusual_positive_volume_count": int(valid["unusual_volume_label"].eq("Volume incomum positivo").sum()),
            "unusual_negative_volume_count": int(valid["unusual_volume_label"].eq("Volume incomum negativo").sum()),
            "valid_stocks_count": int(len(valid)),
        }
        row["score"] = score_sector(row["rs_ratio"], row["rs_momentum"], row["volume_relative"], internal_confirmation)
        row["quadrant"] = classify_quadrant(row["rs_ratio"], row["rs_momentum"])
        row["confirmation_label"] = _confirmation_label(internal_confirmation)
        row["narrative_label"] = _narrative_label(row, prev.get(sector))
        row["concentration_alert"] = _concentration_alert(valid, row["score"], internal_confirmation)
        rows.append(row)
    return pd.DataFrame(rows)
