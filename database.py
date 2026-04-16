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
import sqlite3
from datetime import date
from pathlib import Path

from config import CLAUDE_MODEL, DB_PATH, ENV

log = logging.getLogger(__name__)


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


def export_json_for_github(data: dict, output_dir: Path) -> Path:
    """
    將分析報告輸出為靜態 JSON 檔（供 Vercel 網站讀取）。
    檔案命名：YYYYMMDD.json，存放於 output_dir / data / 下。
    """
    report_date = data.get("meta", {}).get("date", date.today().strftime("%Y-%m-%d"))
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / f"{report_date.replace('-', '')}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("GitHub 靜態 JSON 已輸出：%s", out_path)
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
