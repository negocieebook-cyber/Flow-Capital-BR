from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)


BASE_URL = "https://brapi.dev/api"


class BrapiClientError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, response_text: str = "", endpoint: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
        self.endpoint = endpoint


def normalize_ticker(ticker: str) -> str:
    return ticker.upper().replace(".SA", "").strip()


def _request_params(range_value: str) -> dict[str, str]:
    params = {
        "range": range_value,
        "interval": "1d",
    }
    token = os.getenv("BRAPI_TOKEN")
    if token:
        params["token"] = token
    return params


def _safe_endpoint(ticker: str, range_value: str = "6mo") -> str:
    return f"{BASE_URL}/quote/{normalize_ticker(ticker)}?range={range_value}&interval=1d&token=***"


def _summarize_response(text: str, limit: int = 300) -> str:
    clean = " ".join((text or "").split())
    return clean[:limit] + ("..." if len(clean) > limit else "")


def _extract_historical(payload: dict[str, Any], ticker: str, range_value: str) -> list[dict[str, Any]]:
    results = payload.get("results") or []
    historical = (results[0] if results else {}).get("historicalDataPrice") or []
    if not historical:
        raise BrapiClientError(
            f"brapi sem dados historicos para {ticker}",
            status_code=None,
            response_text=_summarize_response(str(payload)),
            endpoint=_safe_endpoint(ticker, range_value),
        )
    return historical


def fetch_history(ticker: str, lookback_weeks: int = 20) -> pd.DataFrame:
    ticker = normalize_ticker(ticker)
    url = f"{BASE_URL}/quote/{ticker}"
    response = None
    used_range = "6mo"
    for range_value in ("6mo", "3mo"):
        used_range = range_value
        response = requests.get(url, params=_request_params(range_value), timeout=30)
        if response.ok:
            break
        if response.status_code == 400 and "INVALID_RANGE" in response.text and range_value == "6mo":
            logger.warning("brapi range 6mo indisponivel para %s; tentando 3mo", ticker)
            continue
        raise BrapiClientError(
            f"brapi falhou para {ticker}",
            status_code=response.status_code,
            response_text=_summarize_response(response.text),
            endpoint=_safe_endpoint(ticker, range_value),
        )
    if response is None:
        raise BrapiClientError(f"brapi nao executou requisicao para {ticker}", endpoint=_safe_endpoint(ticker, used_range))
    try:
        payload = response.json()
    except ValueError as exc:
        raise BrapiClientError(
            f"brapi retornou JSON invalido para {ticker}",
            status_code=response.status_code,
            response_text=_summarize_response(response.text),
            endpoint=_safe_endpoint(ticker, used_range),
        ) from exc
    historical = _extract_historical(payload, ticker, used_range)
    rows = []
    cutoff = pd.Timestamp(date.today() - timedelta(weeks=max(lookback_weeks + 8, 20)))
    for item in historical:
        ts = item.get("date")
        dt = pd.to_datetime(ts, unit="s", errors="coerce") if isinstance(ts, (int, float)) else pd.to_datetime(ts)
        if pd.isna(dt) or dt < cutoff:
            continue
        rows.append(
            {
                "date": dt.normalize(),
                "open": item.get("open"),
                "high": item.get("high"),
                "low": item.get("low"),
                "close": item.get("close"),
                "volume": item.get("volume"),
                "ticker": ticker,
                "source": "brapi",
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        raise BrapiClientError(
            f"brapi retornou dataframe vazio para {ticker}",
            status_code=response.status_code,
            response_text=_summarize_response(str(payload)),
            endpoint=_safe_endpoint(ticker, used_range),
        )
    df = df[["date", "open", "high", "low", "close", "volume", "ticker", "source"]]
    logger.info("Fonte usada para %s: brapi", ticker)
    return df.sort_values("date").reset_index(drop=True)
