"""
Step 2.5 — 逐字稿前處理
財經直播逐字稿的清洗與標準化（PRD v2 § 2.2.5）：
  步驟一：Regex 清除語助詞、填充詞、重複片段
  步驟二：術語標準化（財經數字格式統一）
  步驟三（可選）：用 Claude Haiku 做語意層面整理後再送 Sonnet
"""

from __future__ import annotations

import logging
import re
import time

import anthropic

from config import CLAUDE_HAIKU_MODEL, TRANSCRIPT_DIR

log = logging.getLogger(__name__)

# ── 語助詞與填充詞正則 ───────────────────────────────────────────────────────
_FILLER_PATTERNS = [
    r"啊+",
    r"欸+",
    r"那個嘛?",
    r"就是說",
    r"就是啊?",
    r"然後呢",
    r"對對對+",
    r"對對+",
    r"嗯+",
    r"唉+",
    r"這個嘛",
    r"這個啊?",
    r"是吧",
    r"好吧",
    r"所以說",
    r"你知道嗎?",
    r"講真的",
]
_FILLER_RE = re.compile("|".join(_FILLER_PATTERNS))

# ── 財經術語標準化對照表 ─────────────────────────────────────────────────────
_TERM_MAP: list[tuple[str, str]] = [
    (r"S[&＆]P\s*500|SP\s*500|標普500|標準普爾500", "S&P 500"),
    (r"那斯達克|納斯達克|NASDAQ|Nasdaq", "那斯達克"),
    (r"道瓊[斯]?工業|道瓊[斯]?|Dow\s*Jones", "道瓊工業"),
    (r"費城半導體|SOX指數|PHLX半導體", "費城半導體指數"),
    (r"台積電|TSMC(?!\()", "台積電(TSMC)"),
    (r"聯準會|美聯儲|Fed(?!\s*funds)", "Fed（聯準會）"),
    (r"升息|加息", "升息"),
    (r"降息|減息", "降息"),
    (r"殖利率|利率|收益率", "殖利率"),
]

# ── 中文數字轉阿拉伯數字 ─────────────────────────────────────────────────────
_CN_DIGIT: dict[str, int] = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
_CN_UNIT: dict[str, int] = {
    "十": 10, "百": 100, "千": 1000, "萬": 10000, "億": 100_000_000,
}


def _cn_to_int(s: str) -> int | None:
    """將簡單中文數字轉換為整數（例：三萬七千 → 37000）。"""
    result = 0
    current = 0
    for ch in s:
        if ch in _CN_DIGIT:
            current = _CN_DIGIT[ch]
        elif ch in _CN_UNIT:
            unit = _CN_UNIT[ch]
            if unit >= 10000:
                result = (result + (current or 1)) * unit
                current = 0
            else:
                current = max(current, 1) * unit
                result += current
                current = 0
    result += current
    return result if result > 9 else None


def _normalize_cn_numbers(text: str) -> str:
    """把財經逐字稿中的中文數字轉為阿拉伯數字（加千分位逗號）。"""
    cn_pattern = re.compile(r"[零一二三四五六七八九十百千萬億]+")

    def replace(m: re.Match) -> str:
        val = _cn_to_int(m.group())
        return f"{val:,}" if val is not None else m.group()

    return cn_pattern.sub(replace, text)


def clean_transcript(text: str) -> str:
    """
    步驟一 + 步驟二：regex 清洗。
    - 移除語助詞與填充詞
    - 財經術語標準化
    - 中文數字轉阿拉伯數字
    - 清理多餘標點與空白
    """
    # 移除語助詞
    text = _FILLER_RE.sub("", text)

    # 術語標準化
    for pattern, replacement in _TERM_MAP:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 中文數字標準化
    text = _normalize_cn_numbers(text)

    # 清理多餘標點
    text = re.sub(r"[，,]{2,}", "，", text)
    text = re.sub(r"[。.]{2,}", "。", text)
    text = re.sub(r"[？?]{2,}", "？", text)
    text = re.sub(r"[！!]{2,}", "！", text)

    # 清理多餘空白
    text = re.sub(r"\s+", " ", text).strip()

    return text


def preprocess_with_haiku(text: str) -> str:
    """
    步驟三：呼叫 Claude Haiku 做語意層面整理。
    成本低（約 Sonnet 的 1/10），適合大量逐字稿前處理。
    """
    client = anthropic.Anthropic()
    prompt = (
        "以下是財經直播的逐字稿（已初步清洗）。\n"
        "請整理成條理清晰的財經重點段落，保留所有數字、點位與關鍵術語，"
        "移除語意重複與無意義的過渡語，但不要補充或推斷原文沒有的資訊。\n"
        "直接輸出整理後的文字，無需標題或說明。\n\n"
        f"逐字稿：\n{text}"
    )

    for attempt in range(1, 4):
        try:
            msg = client.messages.create(
                model=CLAUDE_HAIKU_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except anthropic.OverloadedError:
            if attempt == 3:
                raise
            wait = 10 * attempt
            log.warning("Haiku API 過載，%d 秒後重試（第 %d/3 次）...", wait, attempt)
            time.sleep(wait)

    return text  # 不應到達此行


def preprocess(text: str, channel_key: str, use_haiku: bool = True) -> str:
    """
    完整前處理流程：
      1. regex 清洗（必做）
      2. Claude Haiku 語意整理（可選，use_haiku=False 跳過）

    回傳清洗後文字，同時寫入 output/transcripts/<channel_key>_cleaned.txt。
    """
    log.info("[%s] 前處理 Step 1：regex 清洗（原始 %d 字）...", channel_key, len(text))
    cleaned = clean_transcript(text)
    log.info("[%s] 前處理 Step 1 完成（%d 字）", channel_key, len(cleaned))

    if use_haiku:
        log.info("[%s] 前處理 Step 2：呼叫 Claude Haiku 語意整理...", channel_key)
        cleaned = preprocess_with_haiku(cleaned)
        log.info("[%s] 前處理 Step 2 完成（%d 字）", channel_key, len(cleaned))

    # 寫入清洗後逐字稿
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TRANSCRIPT_DIR / f"{channel_key}_cleaned.txt"
    out_path.write_text(cleaned, encoding="utf-8")
    log.info("[%s] 清洗後逐字稿已儲存：%s", channel_key, out_path)

    return cleaned


def preprocess_both(
    transcripts: dict[str, str | None],
    use_haiku: bool = True,
) -> dict[str, str | None]:
    """對雙頻道逐字稿分別進行前處理，回傳清洗後的 dict。"""
    result: dict[str, str | None] = {}
    for key, text in transcripts.items():
        if text:
            result[key] = preprocess(text, channel_key=key, use_haiku=use_haiku)
        else:
            result[key] = None
    return result


if __name__ == "__main__":
    from transcribe import load_transcript

    for ch_key in ("capital_futures", "yu_ting_hao"):
        raw = load_transcript(ch_key)
        if raw:
            cleaned = preprocess(raw, channel_key=ch_key, use_haiku=True)
            print(f"\n{'='*60}")
            print(f"[{ch_key}] 清洗後（前 500 字）：")
            print(cleaned[:500])
        else:
            print(f"[{ch_key}] 逐字稿不存在，請先執行 transcribe.py")
