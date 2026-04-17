"""
Step 3.5 — 每日新聞文章生成
使用 Claude，根據「晨間財經直播的逐字稿」重組撰寫成適合發布在網頁上的盤前/盤中速報。
包含台股、美股摘要與綜合分析。
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from typing import Any

import anthropic

from config import CLAUDE_MODEL, CLAUDE_SONNET_MODEL, ENV

log = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


SYSTEM_PROMPT = """你是一位資深的財經新聞編輯。現在我會提供一段（或兩段）「晨間財經直播的逐字稿」，請幫我將其重組並撰寫成一篇適合發布在網頁上的盤前/盤中速報。

【轉換任務】
1. 結構化重整： 剔除直播中的口語（如：那個、然後、大家早安、聽得到嗎等），將碎片化的資訊整理成邏輯通順的段落。
2. 時效性提煉： 重點提取「美股昨晚關鍵數據」、「台股開盤點數」、「盤面強勢族群」三大核心資訊。
3. 專業化修飾： 將口語化的敘述轉化為專業財經用語（例如：將「這支漲很快」改為「該標的獲資金湧入，股價強勢上揚」）。

【文案結構限制】
- 新聞標題： 需吸睛且客觀（例如：美股全數收紅，台股開盤跳空站上萬 X 點）。
- 重點精華 (TL;DR)： 在開頭提供 3 個 Bullet Points 摘要。
- 國際盤勢觀察： 整理美股、ADR、以及影響台股的外部因素。
- 台股現況與亮點： 描述開盤概況及當前資金集中的板塊。
- 雙軌觀點： 整合這兩份逐字稿的不同觀點，分析市場分歧或共識。

【輸出限制】
1. 禁止保留原講者的個人觀點或情緒化發言。
2. 禁止給出任何具體的「買進/賣出/目標價」建議。
3. 禁止在文章任何位置出現特定財經主播姓名、直播頻道名稱、節目名稱或任何可識別的創作者身份。觀點應以「市場分析人士」、「技術面觀察」、「宏觀視角」等中性措辭呈現。
4. 必須嚴格輸出 JSON 格式，不得有多餘文字或 Markdown 代碼區塊。

輸出格式（純 JSON）:
{
  "article": {
    "title": "新聞標題（需吸睛且客觀）",
    "tldr": [
      "重點精華摘錄1",
      "重點精華摘錄2",
      "重點精華摘錄3"
    ],
    "sections": [
      {
        "heading": "國際盤勢觀察",
        "content": "整理美股、ADR、以及影響台股的外部因素..."
      },
      {
        "heading": "台股現況與亮點",
        "content": "描述開盤概況及當前資金集中的板塊..."
      },
      {
        "heading": "雙軌觀點統整",
        "content": "整合不同頻道之觀點..."
      }
    ],
    "tags": ["#台股", "#美股", "#tag3", "#tag4"]
  }
}"""


def generate_article(transcript_a: str, transcript_b: str, today: str | None = None) -> dict[str, Any]:
    """
    送入住字稿，呼叫 Claude 生成新聞風格文章，回傳 dict 包含 'article'。
    """
    today = today or date.today().strftime("%Y-%m-%d")
    user_msg = (
        f"今日日期：{today}\n\n"
        f"【逐字稿來源 A】\n{transcript_a}\n\n"
        f"【逐字稿來源 B】\n{transcript_b}"
    )

    is_prod = (ENV == "prod" or CLAUDE_MODEL == CLAUDE_SONNET_MODEL)
    log.info(
        "送出文章生成請求至 %s（環境：%s，thinking：%s）...",
        CLAUDE_MODEL, ENV, "啟用" if is_prod else "停用",
    )

    for attempt in range(1, 6):
        try:
            if is_prod:
                # Sonnet：啟用 extended thinking
                with _get_client().messages.stream(
                    model=CLAUDE_MODEL,
                    max_tokens=8192,
                    thinking={"type": "adaptive"},
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_msg}],
                ) as stream:
                    final = stream.get_final_message()
            else:
                # Haiku：標準串流
                with _get_client().messages.stream(
                    model=CLAUDE_MODEL,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_msg}],
                ) as stream:
                    final = stream.get_final_message()
            break
        except anthropic.OverloadedError:
            if attempt == 5:
                raise
            wait = 15 * attempt
            log.warning("API 過載（529），%d 秒後重試（第 %d/5 次）...", wait, attempt)
            time.sleep(wait)

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

    try:
        data = json.loads(raw)
        return data
    except json.JSONDecodeError:
        log.error("無法將 Claude 輸出轉換為 JSON: %s", raw)
        return {"article": None}

if __name__ == "__main__":
    from transcribe import load_cleaned_transcript, load_transcript

    # 優先使用前處理後的清洗版本
    ta = load_cleaned_transcript("capital_futures") or load_transcript("capital_futures")
    tb = load_cleaned_transcript("yu_ting_hao") or load_transcript("yu_ting_hao")

    if not ta or not tb:
        print("[FAIL] 逐字稿不存在，請先執行 transcribe.py 與 preprocess.py")
    else:
        # test integration
        from dotenv import load_dotenv
        load_dotenv()
        res = generate_article(ta, tb)
        print(json.dumps(res, ensure_ascii=False, indent=2))
