"""
Step 3 — 每日報告圖片生成（Playwright）
產出單一 PNG，極簡 EDM 風格，檔名為 YYYYMMDD.png。
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

from config import CARDS_DIR, TEMPLATES_DIR

log = logging.getLogger(__name__)


def render_daily_report(data: dict, out_path: Path | None = None) -> Path:
    """
    將分析資料渲染成每日報告 PNG。
    檔名預設為 output/cards/YYYYMMDD.png。
    """
    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    today = data.get("meta", {}).get("date", date.today().strftime("%Y-%m-%d"))
    if out_path is None:
        filename = today.replace("-", "") + ".png"
        out_path = CARDS_DIR / filename

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("daily_report.html")
    html_content = template.render(data=data)

    log.info("渲染每日報告圖片：%s", out_path.name)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 680, "height": 900})
        page.set_content(html_content, wait_until="networkidle")
        page.screenshot(path=str(out_path), full_page=True, type="png")
        browser.close()

    log.info("圖片已儲存：%s", out_path)
    return out_path


if __name__ == "__main__":
    from analyze import load_latest_analysis

    data = load_latest_analysis()
    if not data:
        print("找不到分析報告，請先執行 analyze.py")
    else:
        path = render_daily_report(data)
        print(f"完成：{path}")
