"""
資料庫模組 — SQLite 存檔（PRD v2 § 3.1 / 4.1 Step 9）
Oracle VM 上以 SQLite 儲存每日分析結果，輕量免安裝，個人用量完全足夠。

資料表：daily_reports
  - date        TEXT  PRIMARY KEY（YYYY-MM-DD）
  - json_data   TEXT  完整分析 JSON
  - env         TEXT  執行環境（dev / prod）
  - model       TEXT  使用的 Claude 模型
  - created_at  TEXT  建立時間（本地時間）
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import date
from pathlib import Path

from config import CLAUDE_MODEL, DB_PATH, ENV

log = logging.getLogger(__name__)

# web/public/data/ 的固定路徑（供 Vite dev server 和 Vercel 讀取）
WEB_DATA_DIR = Path(__file__).parent / "web" / "public" / "data"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建立資料表（若不存在）。"""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_reports (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT    NOT NULL UNIQUE,
                json_data  TEXT    NOT NULL,
                env        TEXT    NOT NULL DEFAULT 'dev',
                model      TEXT    NOT NULL DEFAULT '',
                created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.commit()
    log.info("SQLite 資料庫就緒：%s", DB_PATH)


def save_report(data: dict) -> None:
    """將分析報告寫入 SQLite（同一天重複執行時以新資料覆蓋）。"""
    report_date = data.get("meta", {}).get("date", date.today().strftime("%Y-%m-%d"))
    init_db()
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO daily_reports (date, json_data, env, model)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                json_data  = excluded.json_data,
                env        = excluded.env,
                model      = excluded.model,
                created_at = datetime('now', 'localtime')
            """,
            (report_date, json.dumps(data, ensure_ascii=False), ENV, CLAUDE_MODEL),
        )
        conn.commit()
    log.info("報告已存入 SQLite：%s（env=%s, model=%s）", report_date, ENV, CLAUDE_MODEL)


def load_report(report_date: str) -> dict | None:
    """讀取指定日期的報告，不存在則回傳 None。"""
    init_db()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT json_data FROM daily_reports WHERE date = ?",
            (report_date,),
        ).fetchone()
    return json.loads(row["json_data"]) if row else None


def list_reports(limit: int = 30) -> list[dict]:
    """列出最近 N 筆報告（日期 + 環境 + 模型）。"""
    init_db()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT date, env, model, created_at FROM daily_reports ORDER BY date DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _rebuild_index(data_dir: Path) -> None:
    """
    從 SQLite 重建 index.json（文章目錄），供前端首頁列表使用。
    每次 export 後自動呼叫，確保目錄與 DB 保持同步。
    """
    init_db()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT date, json_data FROM daily_reports ORDER BY date DESC"
        ).fetchall()

    articles = []
    for row in rows:
        try:
            d = json.loads(row["json_data"])
            date_str = row["date"]
            raw_subj = (d.get("outputs") or {}).get("edm_subject", "")
            title = (
                ((d.get("article") or {}).get("title"))
                or re.sub(r"^【.*?】\s*", "", raw_subj).strip()
                or f"{date_str} 財經速報"
            )
            articles.append({
                "date":        date_str,
                "date_key":    date_str.replace("-", ""),
                "title":       title,
                "tags":        ((d.get("article") or {}).get("tags") or ["#台股", "#美股"])[:4],
                "daily_focus": (d.get("daily_focus") or "")[:100],
            })
        except Exception:
            continue

    index_path = data_dir / "index.json"
    index_path.write_text(
        json.dumps({"articles": articles}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("文章目錄已更新：%s（共 %d 篇）", index_path, len(articles))


def export_json_for_github(data: dict, output_dir: Path) -> Path:
    """
    將分析報告輸出為靜態 JSON 檔：
    - output_dir/data/YYYYMMDD.json  （git 存檔，供備份）
    - web/public/data/YYYYMMDD.json  （前端讀取）
    - web/public/data/latest.json    （前端優先讀取）
    - web/public/data/index.json     （首頁文章列表）
    """
    report_date = data.get("meta", {}).get("date", date.today().strftime("%Y-%m-%d"))
    payload = json.dumps(data, ensure_ascii=False, indent=2)

    # 1. output_dir/data/（原始備份）
    backup_dir = output_dir / "data"
    backup_dir.mkdir(parents=True, exist_ok=True)
    out_path = backup_dir / f"{report_date.replace('-', '')}.json"
    out_path.write_text(payload, encoding="utf-8")
    log.info("備份 JSON 已輸出：%s", out_path)

    # 2. web/public/data/（前端靜態資源）
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (WEB_DATA_DIR / f"{report_date.replace('-', '')}.json").write_text(payload, encoding="utf-8")
    (WEB_DATA_DIR / "latest.json").write_text(payload, encoding="utf-8")
    log.info("web/public/data/ 已更新（%s + latest.json）", report_date)

    # 3. 重建文章目錄
    _rebuild_index(WEB_DATA_DIR)

    return out_path


if __name__ == "__main__":
    init_db()
    reports = list_reports()
    if reports:
        print(f"共 {len(reports)} 筆報告：")
        for r in reports:
            print(f"  {r['date']}  env={r['env']}  model={r['model']}  at={r['created_at']}")
    else:
        print("資料庫尚無報告。")
