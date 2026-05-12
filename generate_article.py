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


SYSTEM_PROMPT = """你是一位專業金融市場分析師，負責將晨間財經直播逐字稿重組為深度財經評論。

【角色定位】
文章風格定位為「盤勢觀察＋產業分析＋策略建議」的專業金融研究報告，讀者為具備基礎財經知識的投資人。

【寫作風格】
- 語氣：專業、冷靜、帶有分析判斷，不過度情緒化
- 文字：新聞體＋研究報告混合風格
- 節奏：數據 → 解讀 → 延伸觀察
- 禁止口語化（如：那個、然後、超爽、爆賺、大家早安、聽得到嗎）
- 多用分析詞彙：「反映」、「顯示」、「意味著」、「預期」、「估算」、「推升」
- 以「市場共識」、「資金流向」、「結構性成長」為核心敘事框架
- 強調 AI 產業鏈與半導體邏輯
- 適度使用估值推算（本益比區間、EPS 推估、目標市值）
- 每段須有「數據＋解讀」，段落間須有邏輯銜接

【資料整理規則】
- 剔除直播口語贅詞
- 禁止保留講者個人情緒性發言
- 禁止出現財經主播姓名、頻道名稱、節目名稱；以「市場分析人士」、「技術面觀察」、「宏觀視角」等中性措辭替代
- 禁止給出具體「買進 / 賣出 / 目標價」建議

【文章架構（sections heading 固定，順序不變）】

1. heading: "國際盤勢觀察"
   ‧ 美股三大指數漲跌幅與收盤點位
   ‧ 科技股、半導體、費半（SOX）補充
   ‧ 成交量、技術面、資金情緒（選擇權、VIX）
   ‧ 亞股或歐股延伸
   ‧ 地緣政治 / 宏觀事件（如有）

2. heading: "台股現況與亮點"
   ‧ 大盤點位、漲跌幅、是否創高
   ‧ 權值股或主流族群表現
   ‧ 財報重點（營收、EPS、毛利率、YoY）
   ‧ 產業結構變化（AI 占比、技術領先度）
   ‧ 未來展望（公司指引、資本支出、產能規劃）

3. heading: "資金與籌碼面"
   ‧ 外資、自營商、投信三大法人動向
   ‧ 台幣匯率升貶
   ‧ 散戶指標（多空比、融資融券）
   ‧ 本益比 / 估值水位分析

4. heading: "策略層面建議"
   ‧ 以 points 陣列輸出 3-5 點條列
   ‧ 包含操作策略、風險提醒、進出場邏輯

5. heading: "產業展望"
   ‧ AI、半導體或當期主流趨勢
   ‧ 以數據支持（市場規模、成長率、出貨量）

6. heading: "市場提醒"
   ‧ 短線 vs 中長線觀察
   ‧ 技術面 vs 基本面可能背離
   ‧ 風險控管具體建議

【篇幅要求】
全文 sections 合計 800–1500 字；標題需吸睛且客觀；TL;DR 3 點精準摘要。

【輸出規則】
必須嚴格輸出純 JSON，不得有多餘文字或 Markdown 代碼區塊。
"策略層面建議" 使用 points 陣列（字串列表），其餘 sections 使用 content 字串（段落間以雙換行分隔）。

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
        "content": "..."
      },
      {
        "heading": "台股現況與亮點",
        "content": "..."
      },
      {
        "heading": "資金與籌碼面",
        "content": "..."
      },
      {
        "heading": "策略層面建議",
        "points": [
          "策略建議第一點...",
          "策略建議第二點...",
          "風險提醒第一點...",
          "風險提醒第二點..."
        ]
      },
      {
        "heading": "產業展望",
        "content": "..."
      },
      {
        "heading": "市場提醒",
        "content": "..."
      }
    ],
    "tags": ["#台股", "#美股", "#AI", "#半導體", "#tag5"]
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
                    max_tokens=8192,
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
