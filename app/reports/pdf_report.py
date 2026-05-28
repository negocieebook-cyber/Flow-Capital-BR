from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import REPORTS_DIR


async def _convert(html_path: Path, pdf_path: Path) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        await page.pdf(path=str(pdf_path), format="A4", print_background=True, margin={"top": "12mm", "right": "10mm", "bottom": "12mm", "left": "10mm"})
        await browser.close()


def html_to_pdf(html_path: Path, week_date: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = REPORTS_DIR / f"flow_map_brasil_{week_date}.pdf"
    asyncio.run(_convert(html_path, pdf_path))
    return pdf_path
