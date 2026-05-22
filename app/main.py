from __future__ import annotations

import argparse
import logging
import os
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.charts.rrg import generate_sector_rrg, generate_stock_rrg
from app.charts.sector_rankings import generate_sector_ranking_chart
from app.charts.unusual_volume import generate_unusual_volume_chart
from app.config import (
    BASE_DIR,
    REPORTS_DIR,
    ensure_directories,
    load_environment,
    load_sectors,
    load_user_settings,
    setup_logging,
)
from app.data_sources import brapi_client, yfinance_client
from app.data_sources.b3_client import fetch_bdi_volume
from app.data_sources.bcb_client import fetch_capital_flow_context, fetch_macro_context
from app.delivery.telegram import send_telegram_document, test_telegram_connection
from app.processing.aggregation import aggregate_sectors
from app.processing.individual_readings import classify_individual_reading, classify_unusual_volume
from app.processing.momentum import add_rrg_metrics
from app.processing.narratives import (
    generate_executive_summary,
    generate_sector_narrative,
    generate_unusual_volume_reading,
    generate_watchlist,
)
from app.processing.quadrants import classify_quadrant
from app.processing.returns import get_last_completed_market_week, to_weekly_ohlcv
from app.processing.scoring import score_individual
from app.processing.volume_flow import add_volume_metrics, classify_tape_signal, compute_udvr_ddvr
from app.reports.html_report import render_weekly_report
from app.reports.pdf_report import html_to_pdf
from app.storage.database import (
    get_asset_history,
    get_previous_sector_metrics,
    get_sector_history,
    init_db,
    insert_asset_metrics_weekly,
    insert_asset_prices_weekly,
    insert_sector_metrics_weekly,
    mark_telegram_sent,
    register_report_error,
    register_report_run,
)

logger = logging.getLogger(__name__)


def run_brapi_test() -> None:
    load_environment()
    token = os.getenv("BRAPI_TOKEN")
    print("Flow Map Brasil - teste brapi")
    print(f"BRAPI_TOKEN: {'configurado' if token else 'nao configurado'}")
    if not token:
        logger.warning("BRAPI_TOKEN nao configurado no .env")
    tickers = ["BOVA11", "PETR4", "VALE3", "ITUB4"]
    for ticker in tickers:
        print("")
        print(f"Ticker: {ticker}")
        try:
            df = brapi_client.fetch_history(ticker, lookback_weeks=20)
            first_date = df["date"].min()
            last_date = df["date"].max()
            print("Status: sucesso")
            print(f"Linhas retornadas: {len(df)}")
            print(f"Primeira data disponivel: {first_date.date() if hasattr(first_date, 'date') else first_date}")
            print(f"Ultima data disponivel: {last_date.date() if hasattr(last_date, 'date') else last_date}")
            print(f"Colunas retornadas: {', '.join(df.columns)}")
        except brapi_client.BrapiClientError as exc:
            print("Status: falha")
            print(f"Status code: {exc.status_code if exc.status_code is not None else 'n/d'}")
            print(f"Resposta resumida da API: {exc.response_text or str(exc)}")
            print(f"Endpoint chamado: {exc.endpoint}")
            logger.warning("Teste brapi falhou para %s: status_code=%s endpoint=%s", ticker, exc.status_code, exc.endpoint)
        except Exception as exc:
            print("Status: falha")
            print("Status code: n/d")
            print(f"Resposta resumida da API: {str(exc)[:300]}")
            print(f"Endpoint chamado: {brapi_client.BASE_URL}/quote/{brapi_client.normalize_ticker(ticker)}?range=6mo&interval=1d&token=***")
            logger.warning("Teste brapi falhou para %s: %s", ticker, exc)


def _fetch_with_fallback(ticker: str, lookback_weeks: int, warnings: list[str], data_quality: dict | None = None) -> pd.DataFrame | None:
    try:
        df = brapi_client.fetch_history(ticker, lookback_weeks)
        if data_quality is not None:
            data_quality["brapi_count"] += 1
        return df
    except Exception as exc:
        logger.warning("Falha brapi para %s: %s", ticker, exc)
        warnings.append(f"{ticker}: falha na brapi, tentando yfinance.")
    try:
        df = yfinance_client.fetch_history(ticker, lookback_weeks)
        if data_quality is not None:
            data_quality["yfinance_count"] += 1
        return df
    except Exception as exc:
        logger.warning("Falha yfinance para %s: %s", ticker, exc)
        warnings.append(f"{ticker}: sem dados nas fontes brapi e yfinance.")
        if data_quality is not None:
            data_quality["missing_count"] += 1
            data_quality["missing_tickers"].append(ticker)
        return None


def _prepare_asset_metrics(asset_weekly: pd.DataFrame, benchmark_weekly: pd.DataFrame, baseline_weeks: int, threshold: float) -> pd.DataFrame:
    bench = benchmark_weekly[["week_date", "close"]].rename(columns={"close": "benchmark_close"})
    df = asset_weekly.merge(bench, on="week_date", how="inner").sort_values("week_date")
    df["weekly_return"] = df["close"].pct_change()
    df["benchmark_return"] = df["benchmark_close"].pct_change()
    df["relative_return"] = df["weekly_return"] - df["benchmark_return"]
    df["relative_strength"] = df["close"] / df["benchmark_close"]
    df = add_rrg_metrics(df)
    df = add_volume_metrics(df, baseline_weeks)
    df["score"] = df.apply(lambda row: score_individual(row["rs_ratio"], row["rs_momentum"], row["volume_relative"], row["relative_return"]), axis=1)
    df["quadrant"] = df.apply(lambda row: classify_quadrant(row["rs_ratio"], row["rs_momentum"]), axis=1)
    df["individual_reading"] = df.apply(
        lambda row: classify_individual_reading(row["weekly_return"], row["relative_return"], row["rs_momentum"], row["score"]),
        axis=1,
    )
    df["unusual_volume_label"] = df.apply(
        lambda row: classify_unusual_volume(row["weekly_return"], row["relative_return"], row["volume_relative"], threshold),
        axis=1,
    )
    return df


def _fmt_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/d"
    return f"{value:.2%}"


def _fmt_num(value: float | None, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "n/d"
    return f"{value:.2f}{suffix}"


def _score_status(score: float | None) -> str:
    if score is None or pd.isna(score):
        return "dados insuficientes"
    if score >= 70:
        return "liderança forte"
    if score >= 60:
        return "liderança moderada"
    if score >= 50:
        return "neutro/melhorando"
    if score >= 40:
        return "fraco, mas monitorável"
    return "fraco/alerta"


def _score_class(score: float | None) -> str:
    if score is None or pd.isna(score):
        return "weak"
    if score >= 70:
        return "strong"
    if score >= 60:
        return "moderate"
    if score >= 50:
        return "neutral"
    if score >= 40:
        return "watchable"
    return "weak"


def _quadrant_class(quadrant: str) -> str:
    return {
        "Leading": "leading",
        "Improving": "improving",
        "Weakening": "weakening",
        "Lagging": "lagging",
    }.get(quadrant, "other")


def _tape_signal_class(signal: str) -> str:
    return {
        "Accumulation Confirmed": "tape-acc-confirmed",
        "Accumulation Pattern": "tape-acc-pattern",
        "Distribution Pattern": "tape-dist-pattern",
        "Tape Disagrees": "tape-disagrees",
    }.get(signal, "tape-neutral")


def _sign_class(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "text-neutral"
    return "text-positive" if value >= 0 else "text-negative"


def _build_macro_indicators(macro: dict) -> list[dict]:
    indicators = []
    if "selic" in macro:
        indicators.append({
            "label": "Selic",
            "value": f"{macro['selic']['value']:.2f}%",
            "direction_class": "",
            "note": "taxa básica de juros",
        })
    if "dolar" in macro:
        d = macro["dolar"]
        up = d["value"] > d["previous"]
        indicators.append({
            "label": "Dólar (USD/BRL)",
            "value": f"R$ {d['value']:.2f}",
            "direction_class": "macro-up" if up else "macro-down",
            "note": "▲ subiu vs anterior" if up else "▼ caiu vs anterior",
        })
    if "ipca" in macro:
        indicators.append({
            "label": "IPCA",
            "value": f"{macro['ipca']['value']:.2f}%",
            "direction_class": "",
            "note": "inflação mensal (BCB)",
        })
    return indicators


def _table_html(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p>Sem ocorrências nesta semana.</p>"
    data = df[["ticker", "sector", "weekly_return", "relative_return", "volume_relative", "score", "unusual_volume_label"]].copy()
    data["weekly_return"] = data["weekly_return"].map(_fmt_pct)
    data["relative_return"] = data["relative_return"].map(_fmt_pct)
    data["volume_relative"] = data["volume_relative"].map(lambda x: _fmt_num(x, "x"))
    data["score"] = data["score"].map(_fmt_num)
    data = data.rename(columns={"unusual_volume_label": "leitura"})
    return data.to_html(index=False, border=0, classes="data-table")


def _macro_text(macro: dict) -> str:
    if not macro:
        return "Dados macro indisponíveis nas fontes gratuitas no momento da geração."
    pieces = []
    if "selic" in macro:
        pieces.append(f"Selic: {macro['selic']['value']:.2f}% no dado mais recente do BCB.")
    if "dolar" in macro:
        dolar = macro["dolar"]
        direction = "subiu" if dolar["value"] > dolar["previous"] else "caiu"
        pieces.append(f"Dólar: {dolar['value']:.2f}, com movimento recente de {direction}; isso pode afetar exportadoras, commodities e inflação.")
    if "ipca" in macro:
        pieces.append(f"IPCA: {macro['ipca']['value']:.2f}% no dado mais recente disponível.")
    return " ".join(pieces)


def _build_context(
    week_date: str,
    settings: dict,
    sector_metrics: pd.DataFrame,
    asset_metrics: pd.DataFrame,
    previous_sector_metrics: pd.DataFrame,
    macro_context: dict,
    sector_rrg_path: Path | None,
    stock_rrg_paths: list[Path],
    warnings: list[str],
    data_quality: dict,
    sector_ranking_chart_path: Path | None = None,
    unusual_volume_chart_path: Path | None = None,
    capital_flow_context: dict | None = None,
) -> dict:
    sector_sorted = sector_metrics.sort_values("score", ascending=False).reset_index(drop=True)
    prev_rank = {}
    prev_score = {}
    if not previous_sector_metrics.empty:
        prev_sorted = previous_sector_metrics.sort_values("score", ascending=False).reset_index(drop=True)
        prev_rank = {row["sector"]: idx + 1 for idx, row in prev_sorted.iterrows()}
        prev_score = dict(zip(previous_sector_metrics["sector"], previous_sector_metrics["score"]))
    rows = []
    for idx, row in sector_sorted.iterrows():
        old_score = prev_score.get(row["sector"])
        score_val = row["score"]
        delta_val = (score_val - old_score) if old_score is not None else None
        rows.append(
            {
                "rank": idx + 1,
                "previous_rank": prev_rank.get(row["sector"], "n/d"),
                "sector": row["sector"],
                "score": _fmt_num(score_val),
                "score_class": _score_class(score_val),
                "score_status": _score_status(score_val),
                "score_delta": (f"{delta_val:+.1f}" if delta_val is not None else "n/d"),
                "weekly_return": _fmt_pct(row["weekly_return"]),
                "relative_return": _fmt_pct(row["relative_return"]),
                "rel_return_class": _sign_class(row["relative_return"]),
                "rs_ratio": _fmt_num(row["rs_ratio"]),
                "rs_momentum": _fmt_num(row["rs_momentum"]),
                "volume_relative": _fmt_num(row["volume_relative"], "x"),
                "internal_confirmation": _fmt_pct(row["internal_confirmation"]),
                "confirmation_label": row["confirmation_label"],
                "quadrant": row["quadrant"],
                "quadrant_class": _quadrant_class(row["quadrant"]),
                "narrative_label": row["narrative_label"],
            }
        )
    deltas = []
    for _, row in sector_metrics.iterrows():
        old = prev_score.get(row["sector"])
        if old is not None:
            deltas.append((row["sector"], row["score"] - old))
    gainers = [f"{sector}: {delta:+.1f} pontos" for sector, delta in sorted(deltas, key=lambda item: item[1], reverse=True)[:3]]
    losers = [f"{sector}: {delta:+.1f} pontos" for sector, delta in sorted(deltas, key=lambda item: item[1])[:3]]
    executive = generate_executive_summary(sector_metrics, asset_metrics, macro_context)
    best = sector_sorted.iloc[0] if not sector_sorted.empty else {}
    worst = sector_sorted.iloc[-1] if not sector_sorted.empty else {}
    unusual = generate_unusual_volume_reading(asset_metrics)
    leaders = sector_sorted[sector_sorted["score"] >= settings["report"]["leader_score_threshold"]]
    leadership_note = ""
    if leaders.empty:
        leadership_note = "Nenhum setor atingiu critério de liderança por score nesta semana."
        leaders = sector_sorted.head(3)
    leader_sections = []
    for _, sector_row in leaders.iterrows():
        stocks = asset_metrics[asset_metrics["sector"].eq(sector_row["sector"])].sort_values("score", ascending=False)
        display = stocks.head(5).copy()
        formatted_rows = []
        for _, stock in display.iterrows():
            formatted_rows.append(
                {
                    "ticker": stock["ticker"],
                    "weekly_return": _fmt_pct(stock["weekly_return"]),
                    "weekly_return_class": _sign_class(stock["weekly_return"]),
                    "relative_return": _fmt_pct(stock["relative_return"]),
                    "rel_return_class": _sign_class(stock["relative_return"]),
                    "rs_ratio": _fmt_num(stock["rs_ratio"]),
                    "rs_momentum": _fmt_num(stock["rs_momentum"]),
                    "volume_relative": _fmt_num(stock["volume_relative"], "x"),
                    "score": _fmt_num(stock["score"]),
                    "score_class": _score_class(stock["score"]),
                    "individual_reading": stock["individual_reading"],
                    "tape_signal": stock.get("tape_signal", "Neutral"),
                    "tape_signal_class": _tape_signal_class(stock.get("tape_signal", "Neutral")),
                    "udvr": _fmt_num(stock.get("udvr"), "x"),
                }
            )
        sector_score = sector_row["score"]
        leader_sections.append(
            {
                "sector": sector_row["sector"],
                "is_leader": bool(sector_score >= settings["report"]["leader_score_threshold"]),
                "score_status": _score_status(sector_score),
                "score_class": _score_class(sector_score),
                "narrative": generate_sector_narrative(sector_row.to_dict(), stocks, macro_context),
                "rows": formatted_rows,
            }
        )
    score_leaders_count = int((sector_metrics["score"] >= 60).sum())
    no_strong_narrative = ""
    if score_leaders_count == 0 and unusual["all"].empty:
        no_strong_narrative = (
            "Não houve narrativa forte confirmada por score e volume nesta semana. "
            "O relatório deve ser lido como mapa de monitoramento, não como indicação de rotação consolidada."
        )
    if score_leaders_count == 0:
        main_narrative = (
            "Semana sem liderança setorial robusta por score. Alguns setores aparecem bem posicionados no RRG, "
            "mas sem confirmação suficiente de volume, score e participação interna."
        )
    else:
        main_narrative = best.get("narrative_label", "Sem narrativa principal.") if isinstance(best, pd.Series) else "Sem narrativa principal."

    bova11_ret_series = asset_metrics["benchmark_return"].dropna()
    bova11_ret = float(bova11_ret_series.iloc[-1]) if not bova11_ret_series.empty else None
    dolar_val = macro_context.get("dolar", {}).get("value") if macro_context else None
    gauge_cards = [
        {"label": "BOVA11 na semana", "value": _fmt_pct(bova11_ret), "accent": "positive" if (bova11_ret or 0) >= 0 else "negative"},
        {"label": "Dólar (USD/BRL)", "value": _fmt_num(dolar_val), "accent": ""},
        {"label": "Setores líderes (score ≥ 60)", "value": score_leaders_count, "accent": "positive" if score_leaders_count > 0 else "negative"},
        {"label": "Liderança forte (≥ 70)", "value": int((sector_metrics["score"] >= 70).sum()), "accent": ""},
        {"label": "Setores em Leading no RRG", "value": int(sector_metrics["quadrant"].eq("Leading").sum()), "accent": ""},
        {"label": "Setores abaixo de 40", "value": int((sector_metrics["score"] < 40).sum()), "accent": "negative" if int((sector_metrics["score"] < 40).sum()) > 5 else ""},
        {"label": "Ações vol. > 1.5x", "value": int((asset_metrics["volume_relative"] >= 1.5).sum()), "accent": ""},
        {"label": "Melhor setor", "value": best.get("sector", "n/d") if isinstance(best, pd.Series) else "n/d", "accent": ""},
        {"label": "Pior setor", "value": worst.get("sector", "n/d") if isinstance(worst, pd.Series) else "n/d", "accent": ""},
        {"label": "Melhor score (ação)", "value": asset_metrics.sort_values("score", ascending=False).iloc[0]["ticker"] if not asset_metrics.empty else "n/d", "accent": ""},
    ]
    quality_rows = [
        {"label": "Tickers via brapi", "value": data_quality.get("brapi_count", 0)},
        {"label": "Tickers via yfinance", "value": data_quality.get("yfinance_count", 0)},
        {"label": "Tickers sem dados", "value": data_quality.get("missing_count", 0)},
        {"label": "Tickers sem dados listados", "value": ", ".join(data_quality.get("missing_tickers", [])) or "nenhum"},
        {"label": "BRAPI_TOKEN", "value": "configurado" if data_quality.get("brapi_token_configured") else "não configurado"},
        {"label": "Semana de referência usada", "value": week_date},
        {"label": "Completude da semana", "value": data_quality.get("week_completeness", "n/d")},
    ]
    return {
        "week_date": week_date,
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "benchmark": settings["market"]["benchmark"],
        "executive_summary": executive,
        "gauge_cards": gauge_cards,
        "sector_rrg_path": sector_rrg_path.resolve().as_uri() if sector_rrg_path else None,
        "sector_ranking_chart_path": sector_ranking_chart_path.resolve().as_uri() if sector_ranking_chart_path else None,
        "unusual_volume_chart_path": unusual_volume_chart_path.resolve().as_uri() if unusual_volume_chart_path else None,
        "sector_rows": rows,
        "top_score_gainers": gainers or ["Sem histórico anterior para comparação."],
        "top_score_losers": losers or ["Sem histórico anterior para comparação."],
        "main_narrative": main_narrative,
        "has_score_leaders": score_leaders_count > 0,
        "leadership_note": leadership_note,
        "no_strong_narrative": no_strong_narrative,
        "leader_sections": leader_sections,
        "stock_rrg_paths": [path.resolve().as_uri() for path in stock_rrg_paths],
        "has_stock_rrg": bool(stock_rrg_paths),
        "has_unusual_volume": not unusual["all"].empty,
        "unusual_positive_table": _table_html(unusual["positive"]),
        "unusual_negative_table": _table_html(unusual["negative"]),
        "macro_indicators": _build_macro_indicators(macro_context),
        "macro_text": _macro_text(macro_context),
        "watchlist": generate_watchlist(sector_metrics, asset_metrics),
        "data_warnings": warnings or ["Nenhum aviso relevante de dados."],
        "quality_rows": quality_rows,
        "capital_flow_context": capital_flow_context or {},
    }


def run_weekly() -> Path:
    load_environment()
    ensure_directories()
    init_db()
    settings = load_user_settings()
    sectors = load_sectors()
    report_settings = settings["report"]
    lookback = int(report_settings["lookback_weeks"])
    baseline = int(report_settings["volume_baseline_weeks"])
    threshold = float(report_settings["unusual_volume_threshold"])
    warnings: list[str] = []
    reference_week = get_last_completed_market_week()
    data_quality = {
        "brapi_count": 0,
        "yfinance_count": 0,
        "missing_count": 0,
        "missing_tickers": [],
        "brapi_token_configured": bool(os.getenv("BRAPI_TOKEN")),
        "week_completeness": "semana fechada",
    }
    logger.info("Início da execução semanal")
    logger.info("Tickers carregados: %s", sum(len(tickers) for tickers in sectors.values()))
    logger.info("Semana de referência fechada: %s", reference_week)

    benchmark = settings["market"]["benchmark"]
    benchmark_raw = _fetch_with_fallback(benchmark, lookback, warnings, data_quality)
    if benchmark_raw is None:
        raise RuntimeError("Benchmark sem dados; não é possível calcular força relativa.")
    benchmark_weekly = to_weekly_ohlcv(benchmark_raw, reference_week)
    if benchmark_weekly.empty:
        raise RuntimeError(f"Benchmark sem dados até a semana fechada {reference_week}.")
    all_weekly = []
    all_metrics_history = []
    udvr_rows: list[dict] = []
    for sector, tickers in sectors.items():
        for ticker in tickers:
            raw = _fetch_with_fallback(ticker, lookback, warnings, data_quality)
            if raw is None:
                continue
            weekly = to_weekly_ohlcv(raw, reference_week)
            if weekly.empty:
                warnings.append(f"{ticker}: sem dados semanais até {reference_week}.")
                data_quality["missing_count"] += 1
                data_quality["missing_tickers"].append(ticker)
                continue
            weekly["sector"] = sector
            if len(weekly) < max(lookback, 10):
                warnings.append(f"{ticker}: histórico inferior ao ideal para {lookback} semanas.")
            all_weekly.append(weekly)
            metrics = _prepare_asset_metrics(weekly, benchmark_weekly, baseline, threshold)
            metrics["sector"] = sector
            all_metrics_history.append(metrics)
            uv = compute_udvr_ddvr(raw, reference_week)
            udvr_rows.append({"ticker": ticker, "udvr": uv["udvr"], "ddvr": uv["ddvr"]})

    if not all_metrics_history:
        raise RuntimeError("Nenhum ativo com dados suficientes.")

    prices = pd.concat(all_weekly, ignore_index=True)
    insert_asset_prices_weekly(prices[["week_date", "ticker", "sector", "open", "high", "low", "close", "volume", "financial_volume", "source"]])

    metrics_history = pd.concat(all_metrics_history, ignore_index=True)
    latest_week = metrics_history["week_date"].max()
    asset_metrics = metrics_history[metrics_history["week_date"].eq(latest_week)].dropna(subset=["weekly_return", "rs_ratio", "rs_momentum"]).copy()
    if udvr_rows:
        udvr_df = pd.DataFrame(udvr_rows).drop_duplicates(subset=["ticker"])
        asset_metrics = asset_metrics.merge(udvr_df, on="ticker", how="left")
    else:
        asset_metrics["udvr"] = float("nan")
        asset_metrics["ddvr"] = float("nan")
    asset_metrics["tape_signal"] = asset_metrics.apply(
        lambda r: classify_tape_signal(r["udvr"], r["ddvr"], r["weekly_return"], r["score"]),
        axis=1,
    )
    logger.info("Quantidade de ativos válidos: %s", len(asset_metrics))
    insert_asset_metrics_weekly(asset_metrics)

    previous_sector = get_previous_sector_metrics(latest_week)
    sector_metrics = aggregate_sectors(asset_metrics, previous_sector)
    logger.info("Setores válidos: %s", int((sector_metrics["valid_stocks_count"] >= 2).sum()))
    insert_sector_metrics_weekly(sector_metrics)

    macro_context = fetch_macro_context() if settings["features"].get("include_macro_context", True) else {}

    capital_flow_context: dict = {}
    try:
        capital_flow_context = fetch_capital_flow_context()
        if capital_flow_context:
            logger.info("Fluxo de capital: trend=%s", capital_flow_context.get("trend", "n/d"))
    except Exception as exc:
        logger.warning("Falha ao buscar fluxo de capital BCB: %s", exc)

    bdi_volumes: dict[str, float] = {}
    try:
        bdi_volumes = fetch_bdi_volume()
        if bdi_volumes:
            logger.info("BDI: %d tickers carregados", len(bdi_volumes))
            for ticker, bdi_vol in bdi_volumes.items():
                row = asset_metrics[asset_metrics["ticker"].eq(ticker)]
                if row.empty:
                    continue
                existing = float(row["financial_volume"].iloc[0] or 0)
                if existing > 0 and bdi_vol > 0:
                    divergence = abs(bdi_vol - existing) / existing
                    if divergence > 0.20:
                        warnings.append(f"{ticker}: divergência de volume BDI vs calculado: {divergence:.1%}")
    except Exception as exc:
        logger.warning("Falha ao processar BDI da B3: %s", exc)
    asset_history_db = get_asset_history()
    sector_history_db = get_sector_history()
    sector_history_for_chart = sector_history_db
    asset_history_for_chart = asset_history_db
    sector_rrg_path = generate_sector_rrg(sector_history_for_chart) if settings["features"].get("include_sector_rrg", True) else None
    sector_ranking_chart_path = generate_sector_ranking_chart(sector_metrics)
    unusual_volume_chart_path = generate_unusual_volume_chart(asset_metrics)
    stock_rrg_paths = []
    if settings["features"].get("include_stock_rrg_for_leaders", True):
        for sector in sector_metrics.loc[sector_metrics["score"] >= report_settings["leader_score_threshold"], "sector"]:
            path = generate_stock_rrg(asset_history_for_chart, sector)
            if path:
                stock_rrg_paths.append(path)

    data_quality["week_completeness"] = "semana fechada" if latest_week <= reference_week else "parcial"
    context = _build_context(
        latest_week, settings, sector_metrics, asset_metrics, previous_sector,
        macro_context, sector_rrg_path, stock_rrg_paths, warnings, data_quality,
        sector_ranking_chart_path, unusual_volume_chart_path, capital_flow_context,
    )
    html_path = render_weekly_report(context, latest_week)
    pdf_path = html_to_pdf(html_path, latest_week)
    logger.info("PDF gerado: %s", pdf_path)
    run_id = register_report_run(latest_week, "success", str(pdf_path), 0)

    if settings["telegram"].get("enabled", True) and settings["features"].get("include_telegram_delivery", True):
        unusual_count = int((asset_metrics["volume_relative"] >= threshold).sum())
        caption = (
            "📊 Flow Map Brasil — Relatório semanal\n\n"
            f"Semana: {latest_week}\n\n"
            "Resumo rápido:\n"
            f"• Melhor setor por score: {sector_metrics.sort_values('score', ascending=False).iloc[0]['sector']}\n"
            f"• Pior setor: {sector_metrics.sort_values('score').iloc[0]['sector']}\n"
            f"• Narrativa principal: {sector_metrics.sort_values('score', ascending=False).iloc[0]['narrative_label']}\n"
            f"• Setores líderes por score: {int((sector_metrics['score'] >= 60).sum())}\n"
            f"• Setores em Leading no RRG: {int(sector_metrics['quadrant'].eq('Leading').sum())}\n"
            f"• Ações com volume incomum: {unusual_count}\n\n"
            "PDF informativo em anexo.\n\n"
            "Este relatório é educacional e não constitui recomendação de investimento."
        )
        send_telegram_document(str(pdf_path), caption)
        mark_telegram_sent(run_id)
        logger.info("Envio Telegram concluído")
    return pdf_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Flow Map Brasil")
    parser.add_argument("--mode", choices=["init-db", "test-telegram", "test-brapi", "weekly"], required=True)
    args = parser.parse_args()
    setup_logging()
    try:
        if args.mode == "init-db":
            load_environment()
            ensure_directories()
            init_db()
            logger.info("Banco inicializado em %s", BASE_DIR / "data" / "flow_map_brasil.db")
            return
        if args.mode == "test-telegram":
            load_environment()
            test_telegram_connection()
            logger.info("Teste Telegram enviado")
            return
        if args.mode == "test-brapi":
            run_brapi_test()
            logger.info("Teste brapi concluido")
            return
        if args.mode == "weekly":
            run_weekly()
            return
    except Exception as exc:
        logger.error("Erro na execução: %s\n%s", exc, traceback.format_exc())
        try:
            register_report_error(datetime.now().date().isoformat(), str(exc))
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
