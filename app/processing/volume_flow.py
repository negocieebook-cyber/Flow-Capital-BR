from __future__ import annotations

import pandas as pd


def financial_volume(close: float, volume: float) -> float:
    return close * volume


def volume_relative(financial_volume_this_week: float, average_financial_volume: float) -> float:
    if average_financial_volume in (0, None) or pd.isna(average_financial_volume):
        return float("nan")
    return financial_volume_this_week / average_financial_volume


def add_volume_metrics(data: pd.DataFrame, baseline_weeks: int = 8) -> pd.DataFrame:
    df = data.sort_values("week_date").copy()
    if "financial_volume" not in df.columns:
        df["financial_volume"] = df["close"] * df["volume"]
    baseline = df["financial_volume"].shift(1).rolling(baseline_weeks, min_periods=3).mean()
    df["volume_relative"] = df["financial_volume"] / baseline
    return df


def compute_udvr_ddvr(raw_daily: pd.DataFrame, week_date_str: str) -> dict[str, float]:
    """Compute UDVR and DDVR for the reference week from raw daily OHLCV data.

    UDVR = volume financeiro dos dias de alta na semana / média diária dos últimos 30 dias
    DDVR = volume financeiro dos dias de queda na semana / média diária dos últimos 30 dias
    """
    if raw_daily is None or raw_daily.empty:
        return {"udvr": float("nan"), "ddvr": float("nan")}

    df = raw_daily.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["fin_vol"] = df["close"] * df["volume"]
    df["day_change"] = df["close"] - df["close"].shift(1)

    week_end = pd.Timestamp(week_date_str)
    week_start = week_end - pd.Timedelta(days=4)
    start_30d = week_end - pd.Timedelta(days=30)

    df_30d = df[(df["date"] > start_30d) & (df["date"] <= week_end)]
    if df_30d.empty:
        return {"udvr": float("nan"), "ddvr": float("nan")}
    avg_daily_vol = df_30d["fin_vol"].mean()
    if pd.isna(avg_daily_vol) or avg_daily_vol <= 0:
        return {"udvr": float("nan"), "ddvr": float("nan")}

    df_week = df[(df["date"] >= week_start) & (df["date"] <= week_end)]
    up_vol = df_week.loc[df_week["day_change"] > 0, "fin_vol"].sum()
    down_vol = df_week.loc[df_week["day_change"] < 0, "fin_vol"].sum()

    return {
        "udvr": up_vol / avg_daily_vol,
        "ddvr": down_vol / avg_daily_vol,
    }


def classify_tape_signal(udvr: float, ddvr: float, weekly_return: float, score: float) -> str:
    """Classify the tape signal based on UDVR/DDVR, weekly return and score."""
    if pd.isna(udvr) or pd.isna(ddvr):
        return "Neutral"
    weekly_up = not pd.isna(weekly_return) and weekly_return > 0
    weekly_down = not pd.isna(weekly_return) and weekly_return < 0
    if weekly_up and udvr >= 2.0:
        return "Accumulation Confirmed"
    if weekly_up and udvr >= 1.5:
        return "Accumulation Pattern"
    if weekly_down and ddvr >= 1.5:
        return "Distribution Pattern"
    if not pd.isna(score) and score >= 60 and udvr <= 0.8:
        return "Tape Disagrees"
    return "Neutral"
