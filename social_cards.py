"""
Step 4 — 產出物生成（Playwright）
  - EDM banner：600×300 PNG，嵌入 Email 本文
  - PDF 報告：完整分析報告，作為 Email 附件
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

from config import CARDS_DIR, TEMPLATES_DIR

log = logging.getLogger(__name__)


def _render_html(template_name: str, data: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    return env.get_template(template_name).render(data=data)


def render_edm_banner(data: dict, out_path: Path | None = None) -> Path:
    """渲染 600×300 EDM banner PNG。"""
    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    today = data.get("meta", {}).get("date", date.today().strftime("%Y-%m-%d"))
    if out_path is None:
        out_path = CARDS_DIR / (today.replace("-", "") + "_banner.png")

    html = _render_html("edm_banner.html", data)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 600, "height": 300})
        page.set_content(html, wait_until="networkidle")
        page.screenshot(
            path=str(out_path),
            clip={"x": 0, "y": 0, "width": 600, "height": 300},
            type="png",
        )
        browser.close()

    log.info("EDM banner 已儲存：%s", out_path)
    return out_path


def render_pdf_report(data: dict, out_path: Path | None = None) -> Path:
    """渲染完整分析 PDF 報告。"""
    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    today = data.get("meta", {}).get("date", date.today().strftime("%Y-%m-%d"))
    if out_path is None:
        out_path = CARDS_DIR / (today.replace("-", "") + "_report.pdf")

    html = _render_html("daily_report.html", data)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(out_path),
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()

    log.info("PDF 報告已儲存：%s", out_path)
    return out_path


def render_daily_report(data: dict) -> tuple[Path, Path]:
    """產出 EDM banner 與 PDF 報告，回傳 (banner_path, pdf_path)。"""
    banner = render_edm_banner(data)
    pdf = render_pdf_report(data)
    return banner, pdf


if __name__ == "__main__":
    from analyze import load_latest_analysis

    data = load_latest_analysis()
    if not data:
        print("找不到分析報告，請先執行 analyze.py")
    else:
        banner, pdf = render_daily_report(data)
        print(f"Banner：{banner}")
        print(f"PDF：{pdf}")
