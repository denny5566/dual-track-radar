"""
圖片素材生成

支援兩種 backend：
  pexels  （預設，免費）  → 申請 Key：https://www.pexels.com/api/
  gemini  （需開 Billing）→ 使用 gemini-3.1-flash-image-preview（Nano Banana 2）

每次執行會用 Claude Haiku 將中文內容轉換成 Pexels 英文搜尋詞，確保圖片與當日文字相關。

用法：
  python generate_assets.py --type all                    # Pexels（預設）
  python generate_assets.py --type all --backend gemini   # Nano Banana（需 Billing）
"""

import argparse
import logging
import os
import shutil
import time
from pathlib import Path

import requests
import anthropic
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ASSETS_DIR = Path("video/public")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

REQUEST_INTERVAL = 1  # Pexels 200 req/hr，1 秒足夠


# ── Claude Haiku：中文 → Pexels 英文搜尋詞 ──────────────────────────────────

def _to_pexels_query(text: str) -> str:
    """用 Claude Haiku 把中文財經文字轉成 4–5 個英文 Pexels 搜尋詞。"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY 未設定，改用原文搜尋")
        return text[:80]
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=30,
            messages=[{
                "role": "user",
                "content": (
                    "Convert this Chinese financial text to a 4-5 word English Pexels image search query. "
                    "Focus on visual concepts (e.g. 'stock market bull run', 'federal reserve building'). "
                    "Return ONLY the query, no explanation, no quotes.\n\n"
                    f"Text: {text[:120]}"
                ),
            }],
        )
        query = msg.content[0].text.strip().strip('"').strip("'")
        log.info("搜尋詞：%s → %s", text[:30], query)
        return query
    except Exception as e:
        log.warning("Haiku 轉換失敗（%s），改用原文", e)
        return text[:80]


# ── Pexels backend ───────────────────────────────────────────────────────────

def _pexels_download(query: str, output_path: Path) -> bool:
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        raise SystemExit("錯誤：PEXELS_API_KEY 未設定，請至 https://www.pexels.com/api/ 申請")
    try:
        log.info("[Pexels] 搜尋：%s → %s", query, output_path.name)
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key},
            params={"query": query, "orientation": "landscape", "per_page": 1},
            timeout=15,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            log.warning("[Pexels] 無結果：%s", query)
            return False
        img_resp = requests.get(photos[0]["src"]["large2x"], timeout=30)
        img_resp.raise_for_status()
        jpg_path = output_path.with_suffix(".jpg")
        jpg_path.write_bytes(img_resp.content)
        log.info("[Pexels] 已儲存：%s", jpg_path)
        return True
    except requests.RequestException as e:
        log.error("[Pexels] 下載失敗（%s）：%s", query, e)
        return False


# ── Gemini backend（Nano Banana 2）──────────────────────────────────────────

def _gemini_generate(prompt: str, output_path: Path) -> bool:
    from google import genai

    api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
    if not api_key:
        raise SystemExit("錯誤：GOOGLE_AI_STUDIO_API_KEY 未設定")

    client = genai.Client(api_key=api_key)
    try:
        log.info("[Gemini] 生成圖片：%s", output_path.name)
        response = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=[prompt],
        )
        for part in response.parts:
            if part.inline_data is not None:
                image = part.as_image()
                png_path = output_path.with_suffix(".png")
                image.save(str(png_path))
                log.info("[Gemini] 已儲存：%s", png_path)
                return True
        log.warning("[Gemini] 回應中無圖片")
        return False
    except Exception as e:
        log.error("[Gemini] 生成失敗：%s", e)
        return False


# ── 統一下載介面 ──────────────────────────────────────────────────────────────

def _fetch(query: str, output_path: Path, backend: str) -> bool:
    if backend == "gemini":
        prompt = (
            f"A professional broadcast news background image for: {query}. "
            "Dark cinematic style, deep navy and black tones, subtle financial data visualization. "
            "Clean, minimal, no text. Ultra high definition."
        )
        ok = _gemini_generate(prompt, output_path)
        time.sleep(5)
    else:
        ok = _pexels_download(query, output_path)
        time.sleep(REQUEST_INTERVAL)
    return ok


# ── 各場景圖片生成 ────────────────────────────────────────────────────────────

def generate_opening_bg(backend: str) -> None:
    query = "financial news broadcast studio dark background"
    out   = ASSETS_DIR / "opening_bg"
    ok    = _fetch(query, out, backend)
    print(f"[{'OK' if ok else 'FAIL'}] Opening 背景")


def generate_news_images(news_items: list[dict], backend: str) -> None:
    """news_items: top5_news 列表，每項含 headline + summary。"""
    for i, item in enumerate(news_items[:5]):
        headline = item.get("headline", "")
        summary  = item.get("summary", "")
        query    = _to_pexels_query(f"{headline}。{summary}")
        out      = ASSETS_DIR / f"news_{i+1:02d}"
        ok       = _fetch(query, out, backend)
        print(f"[{'OK' if ok else 'FAIL'}] 新聞 {i+1}（{headline[:20]}）")


def generate_insight_bg(clash_or_sync: str, backend: str) -> None:
    query = _to_pexels_query(clash_or_sync)
    out   = ASSETS_DIR / "insight_bg"
    ok    = _fetch(query, out, backend)
    print(f"[{'OK' if ok else 'FAIL'}] 綜合洞察背景")


def generate_ending_bg(backend: str) -> None:
    query = "financial future investment growth success city"
    out   = ASSETS_DIR / "ending_bg"
    ok    = _fetch(query, out, backend)
    print(f"[{'OK' if ok else 'FAIL'}] 結尾背景")


# ── 對外介面（供 main.py 呼叫）───────────────────────────────────────────────

def run(data: dict, backend: str = "pexels") -> None:
    """根據當日分析資料生成全部場景圖片。"""
    generate_opening_bg(backend)
    generate_news_images(data.get("top5_news", []), backend)
    generate_insight_bg(data.get("clash_or_sync", "stock market analysis"), backend)
    generate_ending_bg(backend)

    # 將 insight_bg.jpg 複製到 web/public/images/{dateKey}.jpg，供文章頁封面使用
    date_key = (data.get("meta") or {}).get("date", "").replace("-", "")
    if date_key:
        insight_jpg = ASSETS_DIR / "insight_bg.jpg"
        web_img_dir = Path(__file__).parent / "web" / "public" / "images"
        web_img_dir.mkdir(parents=True, exist_ok=True)
        if insight_jpg.exists():
            shutil.copy2(str(insight_jpg), str(web_img_dir / f"{date_key}.jpg"))
            log.info("封面圖已複製至 web/public/images/%s.jpg", date_key)


if __name__ == "__main__":
    import json

    parser = argparse.ArgumentParser(description="生成影片素材")
    parser.add_argument("--type", choices=["opening", "news", "insight", "ending", "all"], default="all")
    parser.add_argument("--data", default="video/src/data/sample.json", help="分析資料 JSON 路徑")
    parser.add_argument("--backend", choices=["pexels", "gemini"], default="pexels")
    args = parser.parse_args()

    data_path = Path(args.data)
    data = json.loads(data_path.read_text(encoding="utf-8")) if data_path.exists() else {}

    log.info("使用 backend：%s", args.backend)

    if args.type in ("opening", "all"):
        generate_opening_bg(args.backend)
    if args.type in ("news", "all"):
        generate_news_images(data.get("top5_news", []), args.backend)
    if args.type in ("insight", "all"):
        generate_insight_bg(data.get("clash_or_sync", "stock market analysis"), args.backend)
    if args.type in ("ending", "all"):
        generate_ending_bg(args.backend)
