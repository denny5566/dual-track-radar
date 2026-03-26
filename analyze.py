"""
Step 2 — LLM 雙軌觀點分析
將兩段逐字稿送入 Claude（claude-opus-4-6），輸出符合專案 JSON Schema 的結構化分析報告。
"""

from __future__ import annotations

import json
import logging
from datetime import date

import anthropic

from config import ANALYSIS_DIR

log = logging.getLogger(__name__)

ANTHROPIC_MODEL = "claude-opus-4-6"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()   # 自動讀取 ANTHROPIC_API_KEY 環境變數
    return _client


SYSTEM_PROMPT = """你是一位精通台股期權與全球總經的資深研究員。

Task: 我會提供兩段逐字稿。請進行「觀點交叉分析」並輸出指定的 JSON。

Analysis Guidelines:
- 處理「群益期貨」時，專注於技術面、盤勢壓力、短線期貨邏輯。
- 處理「財經皓角」時，專注於總體經濟、產業循環、長線趨勢邏輯。
- 找出「共識」與「分歧」：如果群益看空短線但庭澔看好長線，請在 clash_or_sync 中特別標註。
- 數據提取：嚴格提取雙方提到的所有關鍵數字與點位。

Constraint:
- 嚴格遵守下方 JSON 格式，不得有多餘文字或 markdown 代碼區塊。
- 使用台灣繁體中文財經術語。
- 所有文字欄位必須非空。

輸出格式（純 JSON）:
{
  "meta": { "date": "YYYY-MM-DD", "channels": ["群益期貨", "財經皓角"] },
  "daily_focus": "今日市場核心主題",
  "comparison": {
    "capital_futures": {
      "title": "群益法人觀點",
      "sentiment": "偏多/中性/偏空",
      "key_levels": "支撐點位/壓力點位",
      "main_points": ["重點1", "重點2", "重點3"],
      "strategy": "期權佈局建議"
    },
    "yu_ting_hao": {
      "title": "庭澔總經觀點",
      "sentiment": "樂觀/保守/中性",
      "macro_indicators": ["指標1", "指標2"],
      "main_points": ["觀點1", "觀點2", "觀點3"],
      "strategy": "長線配置建議"
    }
  },
  "clash_or_sync": "兩者觀點的衝突點或共識點（最精華部分）",
  "outputs": {
    "edm_subject": "【雙軌雷達】EDM 主旨",
    "social_media_cards": [
      { "type": "cover", "text": "封面標題文字" },
      { "type": "side_by_side", "left": "群益重點摘要", "right": "庭澔重點摘要" },
      { "type": "conclusion", "text": "最終決策建議" }
    ]
  }
}"""


def analyze(transcript_a: str, transcript_b: str, today: str | None = None) -> dict:
    """
    送入雙軌逐字稿，以串流方式呼叫 Claude Opus，回傳結構化 dict。
    """
    today = today or date.today().strftime("%Y-%m-%d")
    user_msg = (
        f"今日日期：{today}\n\n"
        f"逐字稿 A（群益期貨）：\n{transcript_a}\n\n"
        f"逐字稿 B（游庭澔財經皓角）：\n{transcript_b}"
    )

    log.info("送出分析請求至 %s（串流模式）...", ANTHROPIC_MODEL)

    with _get_client().messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        final = stream.get_final_message()

    raw = next(
        (block.text for block in final.content if block.type == "text"),
        "{}",
    )

    # 清除可能殘留的 markdown 代碼圍欄
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    data = json.loads(raw)

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ANALYSIS_DIR / f"analysis_{today.replace('-', '')}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("分析報告已儲存：%s", out_path)

    return data


def load_latest_analysis() -> dict | None:
    """讀取最新一份分析報告（按檔名排序）。"""
    files = sorted(ANALYSIS_DIR.glob("analysis_*.json"), reverse=True)
    if not files:
        return None
    return json.loads(files[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    from transcribe import load_transcript

    ta = load_transcript("capital_futures")
    tb = load_transcript("yu_ting_hao")

    if not ta or not tb:
        print("❌ 逐字稿不存在，請先執行 transcribe.py")
    else:
        data = analyze(ta, tb)
        print(json.dumps(data, ensure_ascii=False, indent=2))
