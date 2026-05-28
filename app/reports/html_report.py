from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import REPORTS_DIR
from app.processing.narratives import generate_strategic_reading


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def render_weekly_report(context: dict[str, Any], week_date: str) -> Path:
    css_content = (TEMPLATES_DIR / "styles.css").read_text(encoding="utf-8")

    # Achata as linhas de ações dos setores líderes, adicionando a chave "sector"
    asset_rows: list[dict] = []
    for sec in context.get("leader_sections", []):
        for row in sec.get("rows", []):
            asset_rows.append({**row, "sector": sec.get("sector", "")})

    strategic_reading = generate_strategic_reading(
        sector_metrics=context.get("sector_rows", []),
        asset_metrics=asset_rows,
        macro_context=context.get("macro_indicators", []),
        capital_flow_context=context.get("capital_flow_context", {}),
    )

    ctx = {**context, "styles_inline": css_content, "strategic_reading": strategic_reading}
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("weekly_report.html")
    html = template.render(**ctx)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output = REPORTS_DIR / f"weekly_report_{week_date}.html"
    output.write_text(html, encoding="utf-8")
    return output
