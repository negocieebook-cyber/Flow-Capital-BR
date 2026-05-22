from __future__ import annotations

import pandas as pd


def _pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/d"
    return f"{value:.2%}"


def generate_sector_narrative(sector_metrics: dict, top_stocks: pd.DataFrame, macro_context: dict | None = None) -> str:
    sector = sector_metrics.get("sector")
    label = sector_metrics.get("narrative_label", "")
    confirmation = sector_metrics.get("confirmation_label", "")
    score = sector_metrics.get("score", 0) or 0
    names = top_stocks["ticker"].head(3).tolist() if not top_stocks.empty else []
    if score >= 70:
        status = "liderança forte por score"
    elif score >= 60:
        status = "liderança moderada por score"
    elif score >= 50:
        status = "zona neutra ou de melhora"
    elif score >= 40:
        status = "fraco, mas monitorável"
    else:
        status = "fraco ou em alerta"
    text = f"No setor de {sector}, a leitura semanal foi: {label} O status por score é {status}, com confirmação interna em {confirmation}."
    if names:
        confirming = top_stocks[top_stocks["individual_reading"].eq("Confirma o setor")]["ticker"].head(2).tolist()
        divergent = top_stocks[top_stocks["individual_reading"].eq("Diverge do setor")]["ticker"].head(1).tolist()
        if confirming:
            text += f" {', '.join(confirming)} confirmaram a narrativa com retorno relativo positivo e momentum favorável."
        if divergent:
            text += f" {divergent[0]} divergiu do movimento, ponto de atenção para a homogeneidade do setor."
    alert = sector_metrics.get("concentration_alert")
    if alert:
        text += f" {alert}"
    return text


def generate_executive_summary(sector_metrics: pd.DataFrame, asset_metrics: pd.DataFrame, macro_context: dict | None = None) -> str:
    valid_sectors = sector_metrics[sector_metrics["valid_stocks_count"] >= 2].copy()
    if valid_sectors.empty or asset_metrics.empty:
        return "Não houve dados suficientes para formar uma leitura setorial robusta nesta semana."
    best_sector = valid_sectors.sort_values("score", ascending=False).iloc[0]
    worst_sector = valid_sectors.sort_values("score").iloc[0]
    leading_count = int(valid_sectors["quadrant"].eq("Leading").sum())
    score_leaders = int((valid_sectors["score"] >= 60).sum())
    weak_count = int((valid_sectors["score"] < 40).sum())
    best_confirmation = valid_sectors.sort_values("internal_confirmation", ascending=False).iloc[0]
    concentrated = valid_sectors.sort_values(["internal_confirmation", "score"], ascending=[True, False]).iloc[0]
    unusual_positive = int(asset_metrics["unusual_volume_label"].eq("Volume incomum positivo").sum())
    unusual_negative = int(asset_metrics["unusual_volume_label"].eq("Volume incomum negativo").sum())
    top_score = asset_metrics.sort_values("score", ascending=False).iloc[0]
    flow_phrase = "Houve confirmação de fluxo por volume incomum." if unusual_positive or unusual_negative else "Não houve confirmação relevante de fluxo por volume incomum."
    macro_phrase = ""
    if macro_context:
        if "dolar" in macro_context:
            dolar = macro_context["dolar"]
            direction = "subiu" if dolar["value"] > dolar["previous"] else "caiu"
            macro_phrase += f" No macro, o dólar {direction} no dado mais recente do BCB, ponto relevante para exportadoras, commodities e inflação."
        if "selic" in macro_context:
            macro_phrase += " A Selic permanece como referência central para setores sensíveis a juros."
    if best_sector["score"] < 60:
        opening = (
            f"A semana não apresentou liderança setorial robusta por score. O melhor setor foi {best_sector['sector']}, "
            f"com score {best_sector['score']:.1f}, ainda abaixo do critério mínimo de liderança."
        )
    else:
        opening = (
            f"A semana mostrou liderança em {best_sector['sector']}, com score {best_sector['score']:.1f} e "
            f"{best_sector['confirmation_label']}."
        )
    no_strong = ""
    if score_leaders == 0 and unusual_positive == 0 and unusual_negative == 0:
        no_strong = " Não houve narrativa forte confirmada por score e volume nesta semana. O relatório deve ser lido como mapa de monitoramento, não como indicação de rotação consolidada."
    return (
        f"{opening} {worst_sector['sector']} ficou em alerta relativo, com score de {worst_sector['score']:.1f}. "
        f"{score_leaders} setores terminaram em Leading e {weak_count} ficaram abaixo de 40 pontos. "
        f"A maior confirmação interna apareceu em {best_confirmation['sector']}, enquanto {concentrated['sector']} teve a liderança mais concentrada. "
        f"Entre as ações, {top_score['ticker']} apresentou o maior score individual. "
        f"A narrativa principal foi: {best_sector['narrative_label']} "
        f"O relatório usa as ações para explicar a rotação setorial, sem recomendação de compra ou venda de ativos.{no_strong}{macro_phrase}"
    )


def generate_watchlist(sector_metrics: pd.DataFrame, asset_metrics: pd.DataFrame) -> list[str]:
    items: list[str] = []
    valid = sector_metrics[sector_metrics["valid_stocks_count"] >= 2].copy()

    leaders = valid[(valid["quadrant"].eq("Leading")) & (valid["score"] >= 60)].sort_values("score", ascending=False)
    for _, row in leaders.iterrows():
        volume_floor = max(1.0, float(row["volume_relative"]) * 0.8)
        items.append(
            f"{row['sector']}: setor líder confirmado. Observar se volume relativo se mantém acima de {volume_floor:.2f}x "
            f"e retorno relativo permanece positivo para manter a narrativa de liderança."
        )

    near_leaders = valid[
        valid["quadrant"].isin(["Leading", "Improving"])
        & (valid["score"] >= 30)
        & (valid["score"] < 60)
    ].sort_values("score", ascending=False)
    for _, row in near_leaders.iterrows():
        if len(items) >= 4:
            break
        items.append(
            f"{row['sector']}: posicionado em {row['quadrant']} no RRG com score de {row['score']:.0f}. "
            f"Se o volume relativo superar 1.0x e o retorno relativo se mantiver positivo, pode avançar para liderança."
        )

    unusual_sectors = valid[
        (valid["unusual_positive_volume_count"] > 0) | (valid["unusual_negative_volume_count"] > 0)
    ].sort_values("volume_relative", ascending=False)
    for _, row in unusual_sectors.iterrows():
        if len(items) >= 5:
            break
        if row["unusual_negative_volume_count"] > row["unusual_positive_volume_count"]:
            items.append(
                f"{row['sector']}: pressão de volume incomum negativo. Melhora exigiria volume mais distribuído e retorno relativo acima do benchmark."
            )
        else:
            items.append(
                f"{row['sector']}: volume incomum positivo — acompanhar se confirmação interna se mantém acima de {_pct(row['internal_confirmation'])}."
            )

    alerts = valid[valid["score"] < 40].sort_values("score")
    for _, row in alerts.iterrows():
        if len(items) >= 6:
            break
        items.append(
            f"{row['sector']}: segue em alerta (score {row['score']:.0f}). Precisaria combinar volume acima da média com retorno relativo positivo para melhorar a leitura."
        )

    if not items:
        items.append("Semana sem gatilhos claros de observação. Priorizar setores que combinarem retorno relativo positivo com volume acima da média.")

    notable = asset_metrics[
        asset_metrics["individual_reading"].eq("Diverge do setor")
        | (asset_metrics["volume_relative"] >= 1.2)
    ].sort_values("volume_relative", ascending=False).head(3)
    for _, stock in notable.iterrows():
        if len(items) >= 7:
            break
        items.append(
            f"Observar {stock['ticker']} ({stock['sector']}): volume relativo de {stock['volume_relative']:.2f}x, leitura: {stock['individual_reading']}."
        )

    return items[:8]


def _parse_float_str(value: str | None, default: float = 0.0) -> float:
    """Converte strings formatadas como '47.37', '-5.18%', '0.48x' para float."""
    if not value or value == "n/d":
        return default
    s = str(value).strip()
    try:
        if s.endswith("%"):
            return float(s[:-1]) / 100.0
        if s.endswith("x"):
            return float(s[:-1])
        return float(s)
    except ValueError:
        return default


def generate_strategic_reading(
    sector_metrics: list[dict],
    asset_metrics: list[dict],
    macro_context: list[dict],
    capital_flow_context: dict | None = None,
) -> dict[str, str]:
    """
    Gera a leitura estratégica da semana em três partes.

    sector_metrics:       context["sector_rows"] — dicts com valores formatados em string.
    asset_metrics:        rows de ações dos setores líderes (com chave "sector" adicionada).
    macro_context:        context["macro_indicators"] — lista de dicts {label, value, direction_class, note}.
    capital_flow_context: resultado de fetch_capital_flow_context() — pode ser None ou vazio.
    """

    def _score(s: dict) -> float:
        return _parse_float_str(s.get("score"))

    def _vol(s: dict) -> float:
        return _parse_float_str(s.get("volume_relative"))

    def _rel(s: dict) -> float:
        return _parse_float_str(s.get("relative_return"))

    def _conf(s: dict) -> float:
        return _parse_float_str(s.get("internal_confirmation"))

    def _rsmom(s: dict) -> float:
        return _parse_float_str(s.get("rs_momentum"))

    def _quad(s: dict) -> str:
        return s.get("quadrant", "")

    # Mapa setor → quadrante para lookup eficiente nas ações
    sector_quadrant_map = {s.get("sector", ""): _quad(s) for s in sector_metrics}

    # ── Contexto macro ──────────────────────────────────────────────────────
    dolar_up: bool | None = None
    for ind in macro_context:
        dc = ind.get("direction_class", "")
        if dc == "macro-up":
            dolar_up = True
        elif dc == "macro-down":
            dolar_up = False

    # ── Fluxo de capital ────────────────────────────────────────────────────
    cap = capital_flow_context or {}
    foreign_dir: str | None = cap.get("foreign_flow", {}).get("direction")
    cap_trend: str = cap.get("trend", "")

    # ── PARTE 1 — ACIONÁVEL ─────────────────────────────────────────────────
    acionavel_sectors = sorted(
        [s for s in sector_metrics if _score(s) >= 60 and _conf(s) >= 0.5 and _vol(s) >= 1.2 and _rel(s) > 0],
        key=_score,
        reverse=True,
    )

    acionavel_stocks = sorted(
        [
            a for a in asset_metrics
            if _parse_float_str(a.get("volume_relative")) >= 1.5
            and _parse_float_str(a.get("relative_return")) > 0
            and a.get("individual_reading") == "Confirma o setor"
            and _parse_float_str(a.get("score")) >= 60
        ],
        key=lambda a: _parse_float_str(a.get("volume_relative")),
        reverse=True,
    )

    if not acionavel_sectors:
        acionavel = (
            "Nenhum setor apresentou combinação completa de score, confirmação e volume nesta semana. "
            "O relatório deve ser lido como mapa de monitoramento."
        )
    else:
        parts = []
        for sec in acionavel_sectors[:2]:
            sec_name = sec.get("sector", "")
            sc = _score(sec)
            cf = _conf(sec)
            vl = _vol(sec)
            sec_stocks = [a for a in acionavel_stocks if a.get("sector") == sec_name]
            part = (
                f"{sec_name} apresentou a leitura mais robusta da semana: score {sc:.1f}, "
                f"confirmação interna em {cf:.0%} das ações e volume relativo de {vl:.2f}x acima da média."
            )
            if sec_stocks:
                stock_parts = [
                    f"{a.get('ticker', '')} com volume {_parse_float_str(a.get('volume_relative')):.2f}x "
                    f"e retorno relativo de {_parse_float_str(a.get('relative_return')):+.2%}"
                    for a in sec_stocks[:2]
                ]
                part += f" {' e '.join(stock_parts)}. Movimento distribuído e com fluxo confirmado."
            else:
                part += " Movimento consistente com confirmação de fluxo no setor."
            if dolar_up is True and sec_name in ("Mineração e Siderurgia", "Petróleo e Gás", "Agro e Alimentos", "Papel e Celulose"):
                part += " O dólar em alta reforça o retorno relativo de exportadoras."
            if foreign_dir == "entrada" and _quad(sec) == "Leading":
                part += " Fluxo estrangeiro confirmando o movimento."
            parts.append(part)
        acionavel = " ".join(parts)

    # ── PARTE 2 — RADAR ─────────────────────────────────────────────────────
    radar_sectors: list[tuple[dict, str]] = []
    for s in sector_metrics:
        q = _quad(s)
        sc = _score(s)
        rv = _rel(s)
        vl = _vol(s)
        rm = _rsmom(s)
        if q == "Leading" and sc < 60:
            radar_sectors.append((s, "leading_below"))
        elif rv > 0.03 and vl < 1.0:
            radar_sectors.append((s, "retorno_sem_volume"))
        elif q == "Improving" and sc >= 35 and rm > 100:
            radar_sectors.append((s, "improving_com_momentum"))

    radar_stocks = sorted(
        [
            a for a in asset_metrics
            if _parse_float_str(a.get("volume_relative")) >= 1.5
            and sector_quadrant_map.get(a.get("sector", ""), "") in ("Leading", "Improving")
            and a.get("individual_reading") != "Diverge do setor"
            and _parse_float_str(a.get("score")) >= 40
        ],
        key=lambda a: _parse_float_str(a.get("volume_relative")),
        reverse=True,
    )

    if not radar_sectors and not radar_stocks:
        radar = (
            "Sem setores com sinal parcial claro para monitoramento próximo. "
            "Acompanhar o comportamento geral de volume e retorno relativo na semana seguinte."
        )
    else:
        radar_parts: list[str] = []
        for s, reason in radar_sectors[:3]:
            sec_name = s.get("sector", "")
            sc = _score(s)
            vl = _vol(s)
            rv = _rel(s)
            rm = _rsmom(s)
            if reason == "leading_below":
                radar_parts.append(
                    f"{sec_name} está em Leading no RRG com score de {sc:.0f}, ainda abaixo do critério de liderança. "
                    f"Se o volume superar 1.0x com retorno relativo positivo, o setor avança no ranking."
                )
            elif reason == "retorno_sem_volume":
                radar_parts.append(
                    f"{sec_name} registrou retorno relativo de {rv:+.2%} mas com volume relativo de apenas {vl:.2f}x, abaixo da média. "
                    f"O movimento de preço existe mas sem confirmação de fluxo. Monitorar se o volume confirma na próxima semana."
                )
            elif reason == "improving_com_momentum":
                radar_parts.append(
                    f"{sec_name} aparece em Improving com RS Momentum de {rm:.2f} e score {sc:.0f}. "
                    f"Ponto de atenção se o setor aproximar RS Ratio de 100 com volume acima da média."
                )
        for a in radar_stocks[:2]:
            t = a.get("ticker", "")
            sec = a.get("sector", "")
            sv = _parse_float_str(a.get("volume_relative"))
            sr = _parse_float_str(a.get("relative_return"))
            leitura = a.get("individual_reading", "")
            radar_parts.append(
                f"{t} ({sec}) registrou volume {sv:.2f}x com retorno relativo de {sr:+.2%} e leitura: {leitura}. "
                f"Acompanhar se o setor começa a confirmar o movimento."
            )
        radar = " ".join(radar_parts)

    # ── PARTE 3 — EVITAR ────────────────────────────────────────────────────
    evitar_sectors = sorted(
        [
            s for s in sector_metrics
            if _score(s) < 25
            and _quad(s) in ("Lagging", "Weakening")
            and _vol(s) < 1.0
            and _rel(s) < 0
        ],
        key=_score,
    )

    if not evitar_sectors:
        evitar = (
            "Nenhum setor apresentou combinação de fraqueza extrema nesta semana. "
            "Acompanhar setores com score abaixo de 40 e retorno relativo negativo."
        )
    else:
        names_scores = [f"{s.get('sector', '')} (score {_score(s):.0f})" for s in evitar_sectors[:4]]
        if len(names_scores) == 1:
            evitar = (
                f"{names_scores[0]} segue em {_quad(evitar_sectors[0])} sem sinal de reversão: "
                f"volume abaixo da média e retorno relativo negativo."
            )
        else:
            listed = ", ".join(names_scores[:-1]) + " e " + names_scores[-1]
            evitar = (
                f"{listed} seguem sem sinal de reversão: volume abaixo da média e retorno relativo negativo. "
                f"Fluxo ausente. Evitar exposição até confirmação de melhora por volume e retorno relativo positivo."
            )
        evitar_names = {s.get("sector") for s in evitar_sectors}
        divergentes = [a for a in asset_metrics if a.get("sector") in evitar_names and a.get("individual_reading") == "Diverge do setor"]
        if divergentes:
            tickers = ", ".join(a.get("ticker", "") for a in divergentes[:3])
            evitar += f" {tickers} divergiram internamente, reforçando a leitura de fraqueza no setor."
        if foreign_dir == "saída":
            evitar += " Ambiente de saída de capital estrangeiro, favorecendo setores defensivos e exportadoras."

    return {"acionavel": acionavel, "radar": radar, "evitar": evitar}


def generate_unusual_volume_reading(asset_metrics: pd.DataFrame) -> dict[str, pd.DataFrame]:
    unusual = asset_metrics[asset_metrics["volume_relative"] >= 1.5].copy()
    positive = unusual[unusual["unusual_volume_label"].eq("Volume incomum positivo")]
    negative = unusual[unusual["unusual_volume_label"].eq("Volume incomum negativo")]
    return {"positive": positive, "negative": negative, "all": unusual}
