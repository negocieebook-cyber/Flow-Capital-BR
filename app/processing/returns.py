from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd


def weekly_return(close_this_week: float, close_previous_week: float) -> float:
    if close_previous_week in (0, None) or pd.isna(close_previous_week):
        return float("nan")
    return close_this_week / close_previous_week - 1


def benchmark_return(benchmark_close_this_week: float, benchmark_close_previous_week: float) -> float:
    return weekly_return(benchmark_close_this_week, benchmark_close_previous_week)


def relative_return(asset_return: float, bench_return: float) -> float:
    return asset_return - bench_return


def get_last_completed_market_week(now: datetime | None = None, market_close_hour: int = 18) -> str:
    current = now or datetime.now()
    weekday = current.weekday()
    if weekday < 4:
        days_back = weekday + 3
    elif weekday == 4 and current.hour < market_close_hour:
        days_back = 7
    elif weekday == 4:
        days_back = 0
    else:
        days_back = weekday - 4
    return (current.date() - timedelta(days=days_back)).isoformat()


def to_weekly_ohlcv(df: pd.DataFrame, max_week_date: str | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    data = df.copy()
    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values("date").set_index("date")
    ticker = data["ticker"].iloc[0]
    source = data["source"].iloc[0]
    data["daily_financial_volume"] = data["close"] * data["volume"]
    weekly = data.resample("W-FRI").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        financial_volume=("daily_financial_volume", "sum"),
    )
    weekly = weekly.dropna(subset=["close"]).reset_index()
    weekly["week_date"] = weekly["date"].dt.date.astype(str)
    cutoff = max_week_date or get_last_completed_market_week()
    weekly = weekly[weekly["week_date"] <= cutoff]
    weekly["ticker"] = ticker
    weekly["source"] = source
    return weekly
