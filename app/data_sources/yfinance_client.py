from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def to_yahoo_ticker(ticker: str) -> str:
    return ticker if ticker.endswith(".SA") else f"{ticker}.SA"


def fetch_history(ticker: str, lookback_weeks: int = 20) -> pd.DataFrame:
    yahoo_ticker = to_yahoo_ticker(ticker)
    data = yf.download(yahoo_ticker, period="6mo", interval="1d", auto_adjust=False, progress=False)
    if data.empty:
        raise ValueError(f"yfinance sem dados para {ticker}")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data.reset_index()
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(data["Date"]).dt.normalize(),
            "open": data["Open"],
            "high": data["High"],
            "low": data["Low"],
            "close": data["Close"],
            "volume": data["Volume"],
            "ticker": ticker,
            "source": "yfinance",
        }
    )
    logger.info("Fonte usada para %s: yfinance", ticker)
    return df.sort_values("date").reset_index(drop=True)
