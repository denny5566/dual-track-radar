"""
回測腳本：從 radar.db 讀取每日情緒訊號，對比 T+1 大盤漲跌，計算正確率。
輸出 web/public/data/accuracy.json 供首頁 widget 使用。

用法：
  python tools/backtest.py
  python tools/backtest.py --symbol ^GSPC   # 改用 S&P500
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "radar.db"
OUT_PATH = ROOT / "web" / "public" / "data" / "accuracy.json"

# 情緒關鍵字 → 方向
BULLISH_KEYWORDS = ["偏多", "樂觀", "看多", "積極", "多頭", "上漲"]
BEARISH_KEYWORDS = ["偏空", "看空", "悲觀", "空頭", "下跌", "賣出"]
# 保守／謹慎 是「觀望」而非明確看空，歸入 neutral


def classify(sentiment: str) -> str:
    """Return 'bullish', 'bearish', or 'neutral'."""
    s = sentiment.strip()
    for kw in BULLISH_KEYWORDS:
        if kw in s:
            # bearish keywords take priority when both appear (e.g. "偏多但謹慎")
            for bkw in BEARISH_KEYWORDS:
                if bkw in s:
                    return "neutral"
            return "bullish"
    for kw in BEARISH_KEYWORDS:
        if kw in s:
            return "bearish"
    return "neutral"


def combine_signals(cap: str, yu: str) -> str:
    """Combine two channel sentiments into one signal."""
    s1, s2 = classify(cap), classify(yu)
    if s1 == s2:
        return s1
    if "neutral" in (s1, s2):
        return s1 if s2 == "neutral" else s2
    # one bullish, one bearish → mixed
    return "neutral"


def load_records() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = bytes
    c = conn.cursor()
    c.execute("SELECT date, json_data FROM daily_reports ORDER BY date")
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
        signal = combine_signals(cap_sent, yu_sent)
        records.append({
            "date": date_str,
            "cap_sentiment": cap_sent,
            "yu_sentiment": yu_sent,
            "signal": signal,
        })
    conn.close()
    return records


def fetch_prices(symbol: str, dates: list[str]) -> dict[str, float]:
    """Return {date_str: close_price} for each date and its T+1."""
    if not dates:
        return {}
    start = min(dates)
    # fetch up to T+5 after last date
    end_dt = date.fromisoformat(max(dates)) + timedelta(days=10)
    end = end_dt.isoformat()
    df = yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        return {}
    # flatten multi-index if present
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)
    prices = {}
    for ts, row in df.iterrows():
        prices[ts.strftime("%Y-%m-%d")] = float(row["Close"])
    return prices


def next_trading_day(prices: dict[str, float], from_date: str, offset: int = 1) -> str | None:
    """Return the date string of the Nth next trading day available in prices."""
    sorted_dates = sorted(prices.keys())
    try:
        idx = sorted_dates.index(from_date)
    except ValueError:
        # find first date >= from_date
        candidates = [d for d in sorted_dates if d >= from_date]
        if not candidates:
            return None
        idx = sorted_dates.index(candidates[0])
    target = idx + offset
    if target < len(sorted_dates):
        return sorted_dates[target]
    return None


def run(symbol: str = "^TWII") -> dict:
    records = load_records()
    if not records:
        print("radar.db 中沒有資料", file=sys.stderr)
        return {}

    tradable = [r for r in records if r["signal"] != "neutral"]
    dates = [r["date"] for r in records]
    prices = fetch_prices(symbol, dates)

    results = []
    for r in tradable:
        d = r["date"]
        if d not in prices:
            continue
        t1 = next_trading_day(prices, d, 1)
        if t1 is None:
            continue
        p0, p1 = prices[d], prices[t1]
        chg = (p1 - p0) / p0 * 100
        market_up = p1 > p0
        correct = (r["signal"] == "bullish" and market_up) or \
                  (r["signal"] == "bearish" and not market_up)
        results.append({
            "date": d,
            "signal": r["signal"],
            "cap_sentiment": r["cap_sentiment"],
            "yu_sentiment": r["yu_sentiment"],
            "t1_date": t1,
            "t1_chg_pct": round(chg, 2),
            "correct": correct,
        })

    total = len(results)
    correct_count = sum(1 for r in results if r["correct"])
    accuracy_pct = round(correct_count / total * 100) if total else 0

    bullish_rows = [r for r in results if r["signal"] == "bullish"]
    bearish_rows = [r for r in results if r["signal"] == "bearish"]

    def win_rate(rows):
        if not rows:
            return None
        return round(sum(1 for r in rows if r["correct"]) / len(rows) * 100)

    output = {
        "symbol": symbol,
        "accuracy_pct": accuracy_pct,
        "total": total,
        "correct": correct_count,
        "bullish_total": len(bullish_rows),
        "bullish_win_rate": win_rate(bullish_rows),
        "bearish_total": len(bearish_rows),
        "bearish_win_rate": win_rate(bearish_rows),
        "last_updated": max(dates) if dates else "",
        "recent": list(reversed(results[-10:])),
    }
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="^TWII", help="Yahoo Finance ticker (default: ^TWII)")
    args = parser.parse_args()

    print(f"[backtest] 抓取 {args.symbol} 收盤價並計算正確率…")
    output = run(args.symbol)
    if not output:
        sys.exit(1)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[backtest] 完成：正確率 {output['accuracy_pct']}%（{output['correct']}/{output['total']} 筆）")
    print(f"[backtest] 輸出 → {OUT_PATH}")


if __name__ == "__main__":
    main()
