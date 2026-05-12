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


def load_records() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = bytes
    c = conn.cursor()
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    c.execute("SELECT date, json_data FROM daily_reports WHERE date >= ? ORDER BY date", (cutoff,))
    records = []
    for date_b, raw_b in c.fetchall():
        date_str = date_b.decode("utf-8")
        try:
            d = json.loads(raw_b.decode("utf-8"))
        except Exception:
            continue
        comp = d.get("comparison", {})
        cap_sent = comp.get("capital_futures", {}).get("sentiment", "")
        yu_sent = comp.get("yu_ting_hao", {}).get("sentiment", "")
        records.append({
            "date": date_str,
            "signal": combine(cap_sent, yu_sent),
        })
    conn.close()
    return records


def run() -> dict:
    records = load_records()
    if not records:
        print("radar.db 中沒有資料", file=sys.stderr)
        return {}

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
