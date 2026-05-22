from __future__ import annotations

import io
import logging
import zipfile
from datetime import date, timedelta

import requests

logger = logging.getLogger(__name__)

COTAHIST_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_S{year}{week:02d}.ZIP"


def _last_completed_friday() -> date:
    """Returns the most recent Friday (the day market weeks close)."""
    today = date.today()
    days_since_friday = (today.weekday() - 4) % 7
    return today - timedelta(days=days_since_friday)


def fetch_bdi_volume(year: int | None = None, week: int | None = None) -> dict[str, float]:
    """
    Downloads and parses the B3 weekly BDI file (COTAHIST fixed-width format).
    Returns {ticker: total_financial_volume_brl} for spot-market equities (CODBDI="02").
    Returns empty dict on any failure so the main report continues normally.
    """
    if year is None or week is None:
        last_friday = _last_completed_friday()
        iso = last_friday.isocalendar()
        year, week = iso.year, iso.week

    url = COTAHIST_URL.format(year=year, week=week)
    logger.info("Baixando arquivo BDI: %s", url)

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Falha ao baixar BDI da B3 (%s): %s", url, exc)
        return {}

    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            txt_name = next((n for n in zf.namelist() if n.upper().endswith(".TXT")), None)
            if not txt_name:
                logger.warning("Arquivo TXT não encontrado no ZIP do BDI")
                return {}
            content = zf.read(txt_name).decode("latin-1")
    except Exception as exc:
        logger.warning("Falha ao extrair ZIP do BDI: %s", exc)
        return {}

    volumes: dict[str, float] = {}
    for line in content.splitlines():
        if len(line) < 188:
            continue
        # COTAHIST fixed-width positions (0-indexed):
        # 0-1: TIPREG  2-9: DATPRE  10-11: CODBDI  12-23: CODNEG  170-187: VOLTOT (cents)
        if line[0:2] != "01":
            continue
        if line[10:12].strip() != "02":  # only spot market
            continue
        ticker = line[12:24].strip()
        if not ticker:
            continue
        try:
            voltot = float(line[170:188].strip()) / 100.0  # centavos → reais
        except ValueError:
            continue
        volumes[ticker] = volumes.get(ticker, 0.0) + voltot

    logger.info("BDI: %d tickers com volume parseados (semana %d/%02d)", len(volumes), year, week)
    return volumes
