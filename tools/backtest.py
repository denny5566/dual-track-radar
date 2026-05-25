"""
情緒分布腳本：從 radar.db 讀取近 30 天情緒，統計技術面/基本面各自偏多/中立/偏空比例。
輸出 web/public/data/accuracy.json 供首頁 widget 使用。

用法：
  python tools/backtest.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "radar.db"
OUT_PATH = ROOT / "web" / "public" / "data" / "accuracy.json"
PUBLIC_DATA_DIR = ROOT / "web" / "public" / "data"

BULLISH_KEYWORDS = ["偏多", "樂觀", "看多", "積極", "多頭", "上漲"]
BEARISH_KEYWORDS = ["偏空", "看空", "悲觀", "空頭", "下跌", "賣出"]


def classify(sentiment: str) -> str:
    s = sentiment.strip()
    for kw in BULLISH_KEYWORDS:
        if kw in s:
            for bkw in BEARISH_KEYWORDS:
                if bkw in s:
                    return "neutral"
            return "bullish"
    for kw in BEARISH_KEYWORDS:
        if kw in s:
            return "bearish"
    return "neutral"


def combine(cap: str, yu: str) -> str:
    s1, s2 = classify(cap), classify(yu)
    if s1 == s2:
        return s1
    if "neutral" in (s1, s2):
        return s1 if s2 == "neutral" else s2
    return "neutral"


def record_from_report(date_str: str, report: dict) -> dict | None:
    comp = report.get("comparison", {})
    cap_sent = comp.get("capital_futures", {}).get("sentiment", "")
    yu_sent = comp.get("yu_ting_hao", {}).get("sentiment", "")
    if not (cap_sent or yu_sent):
        return None
    technical = classify(cap_sent)
    macro = classify(yu_sent)
    return {
        "date": date_str,
        "signal": combine(cap_sent, yu_sent),
        "technical": technical,
        "macro": macro,
    }


def load_db_records(cutoff: str) -> list[dict]:
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = bytes
    c = conn.cursor()
    c.execute("SELECT date, json_data FROM daily_reports WHERE date >= ? ORDER BY date", (cutoff,))
    records = []
    for date_value, raw_value in c.fetchall():
        date_str = date_value.decode("utf-8") if isinstance(date_value, bytes) else str(date_value)
        raw = raw_value.decode("utf-8") if isinstance(raw_value, bytes) else str(raw_value)
        try:
            d = json.loads(raw)
        except Exception:
            continue
        record = record_from_report(date_str, d)
        if record:
            records.append(record)
    conn.close()
    return records


def load_json_records(cutoff: str) -> list[dict]:
    records = []
    if not PUBLIC_DATA_DIR.exists():
        return records

    for path in sorted(PUBLIC_DATA_DIR.glob("20*.json")):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        date_str = d.get("meta", {}).get("date")
        if not date_str:
            stem = path.stem
            date_str = f"{stem[:4]}-{stem[4:6]}-{stem[6:8]}" if len(stem) == 8 else ""
        if not date_str or date_str < cutoff:
            continue

        record = record_from_report(date_str, d)
        if record:
            records.append(record)
    return records


def load_records() -> list[dict]:
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    by_date = {}
    for record in load_db_records(cutoff) + load_json_records(cutoff):
        by_date[record["date"]] = record
    return [by_date[d] for d in sorted(by_date)]


def run() -> dict:
    records = load_records()
    if not records:
        print("radar.db 中沒有資料", file=sys.stderr)
        return {}

    def summarize(key: str) -> dict:
        total = len(records)
        bull = sum(1 for r in records if r[key] == "bullish")
        bear = sum(1 for r in records if r[key] == "bearish")
        neut = total - bull - bear
        return {
            "bullish": bull,
            "neutral": neut,
            "bearish": bear,
            "bullish_pct": round(bull / total * 100) if total else 0,
            "neutral_pct": round(neut / total * 100) if total else 0,
            "bearish_pct": round(bear / total * 100) if total else 0,
        }

    total = len(records)
    bull = sum(1 for r in records if r["signal"] == "bullish")
    bear = sum(1 for r in records if r["signal"] == "bearish")
    neut = total - bull - bear

    output = {
        "last_updated": max(r["date"] for r in records),
        "record_count": total,
        "bullish": bull,
        "neutral": neut,
        "bearish": bear,
        "bullish_pct": round(bull / total * 100) if total else 0,
        "neutral_pct": round(neut / total * 100) if total else 0,
        "bearish_pct": round(bear / total * 100) if total else 0,
        "technical": summarize("technical"),
        "macro": summarize("macro"),
    }
    return output


def main():
    print("[backtest] 統計近 30 天 AI 市場觀點…")
    output = run()
    if not output:
        sys.exit(1)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[backtest] 偏多 {output['bullish_pct']}% / 中立 {output['neutral_pct']}% / 偏空 {output['bearish_pct']}%（{output['record_count']} 筆）")
    print(f"[backtest] 輸出 → {OUT_PATH}")


if __name__ == "__main__":
    main()
