from __future__ import annotations

import logging
from datetime import date, timedelta

import requests

logger = logging.getLogger(__name__)


SGS = {
    "selic": 432,
    "dolar": 1,
    "ipca": 433,
}

CAPITAL_FLOW_SGS = {
    "foreign_flow": 2454,   # Fluxo de capital estrangeiro na B3 (R$ milhões)
    "fund_flow": 7326,      # Captação líquida de fundos de ações
    "nonresident": 4192,    # Posição de investidores não residentes
}


def _fetch_sgs(code: int, days: int = 90) -> dict | None:
    start = (date.today() - timedelta(days=days)).strftime("%d/%m/%Y")
    end = date.today().strftime("%d/%m/%Y")
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
    response = requests.get(url, params={"formato": "json", "dataInicial": start, "dataFinal": end}, timeout=20)
    response.raise_for_status()
    data = response.json()
    if not data:
        return None
    latest = data[-1]
    previous = data[-2] if len(data) > 1 else data[-1]
    return {
        "date": latest.get("data"),
        "value": float(str(latest.get("valor", "0")).replace(",", ".")),
        "previous": float(str(previous.get("valor", "0")).replace(",", ".")),
    }


def fetch_capital_flow_context() -> dict:
    """Busca séries de fluxo de capital do BCB/SGS. Retorna dict vazio em caso de falha."""
    result: dict = {}

    try:
        foreign = _fetch_sgs(CAPITAL_FLOW_SGS["foreign_flow"], days=30)
        if foreign:
            val = foreign["value"]
            result["foreign_flow"] = {"value": val, "direction": "entrada" if val >= 0 else "saída"}
    except Exception as exc:
        logger.warning("Falha ao buscar fluxo estrangeiro (SGS 2454): %s", exc)

    try:
        fund = _fetch_sgs(CAPITAL_FLOW_SGS["fund_flow"], days=60)
        if fund:
            val = fund["value"]
            result["fund_flow"] = {"value": val, "direction": "entrada" if val >= 0 else "saída"}
    except Exception as exc:
        logger.warning("Falha ao buscar captação de fundos (SGS 7326): %s", exc)

    try:
        nonres = _fetch_sgs(CAPITAL_FLOW_SGS["nonresident"], days=30)
        if nonres:
            result["nonresident_position"] = {"value": nonres["value"]}
    except Exception as exc:
        logger.warning("Falha ao buscar posição não residente (SGS 4192): %s", exc)

    if result:
        foreign_dir = result.get("foreign_flow", {}).get("direction")
        fund_dir = result.get("fund_flow", {}).get("direction")
        entrada = sum(1 for d in [foreign_dir, fund_dir] if d == "entrada")
        saida = sum(1 for d in [foreign_dir, fund_dir] if d == "saída")
        result["trend"] = "entrada de capital" if entrada > saida else ("saída de capital" if saida > entrada else "fluxo neutro")

    return result


def fetch_macro_context() -> dict:
    context: dict[str, dict | str] = {}
    for name, code in SGS.items():
        try:
            value = _fetch_sgs(code)
            if value:
                context[name] = value
        except Exception as exc:
            logger.warning("Falha ao buscar macro %s no BCB/SGS: %s", name, exc)
            context[f"{name}_warning"] = "indisponivel"
    return context
