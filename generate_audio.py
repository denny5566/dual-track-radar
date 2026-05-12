"""
旁白音檔生成
使用 Edge TTS（zh-TW-YunJheNeural，男聲）為影片每個場景合成語音

輸出目錄：video/public/audio/
  opening.mp3     — Opening 場景旁白
  news_01.mp3     — 第一則新聞
  ...
  news_05.mp3     — 第五則新聞
  insight.mp3     — 綜合洞察 + 投資人提醒
  ending.mp3      — 結尾

用法：
  python generate_audio.py                        # 讀 video/src/data/sample.json
  python generate_audio.py --data data/latest.json
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path

import edge_tts
from mutagen.mp3 import MP3

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

VOICE      = "zh-TW-YunJheNeural"   # 男聲（台灣繁中）
FALLBACK_VOICE = "zh-TW-HsiaoChenNeural"
AUDIO_DIR  = Path("video/public/audio")
DURATIONS_PATH = Path("video/src/data/durations.json")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def get_duration(path: Path) -> float:
    """讀取 MP3 時長（秒），不需 ffmpeg。"""
    try:
        return MP3(str(path)).info.length
    except Exception:
        return 10.0  # 讀取失敗時的安全預設值


async def speak(text: str, output_path: Path) -> None:
    """合成單段語音並儲存（含重試，降低 Edge TTS 偶發失敗）。"""
    voices = [VOICE, FALLBACK_VOICE]
    last_error: Exception | None = None
    for attempt in range(1, 4):
        voice = voices[(attempt - 1) % len(voices)]
        try:
            log.info("合成：%s（voice=%s, attempt=%d/3）", output_path.name, voice, attempt)
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))
            # Edge TTS 偶發會產出空檔，這裡補檢查
            if not output_path.exists() or output_path.stat().st_size < 1024:
                raise RuntimeError("No audio was received. Please verify that your parameters are correct.")
            log.info("已儲存：%s（%.1f 秒）", output_path, get_duration(output_path))
            return
        except Exception as e:
            last_error = e
            log.warning("語音合成失敗：%s（attempt=%d/3）", e, attempt)
            await asyncio.sleep(1.2 * attempt)
    raise RuntimeError(f"語音合成最終失敗：{last_error}")


async def generate_all(data: dict) -> None:
    daily_focus       = data.get("daily_focus", "")
    top5_news         = data.get("top5_news", [])
    clash_or_sync     = data.get("clash_or_sync", "")
    investor_reminder = data.get("investor_reminder", "")

    # 記錄（key, path）以便事後量測時長
    segments: list[tuple[str, Path]] = []

    # Opening
    opening_text = f"歡迎收看雙軌財經情報雷達。今日焦點，{daily_focus}"
    opening_path = AUDIO_DIR / "opening.mp3"
    segments.append(("opening", opening_path))
    await speak(opening_text, opening_path)

    # 5 大新聞
    for i, item in enumerate(top5_news[:5]):
        headline = item.get("headline", "")
        summary  = item.get("summary", "")
        text     = f"{headline}。{summary}"
        path     = AUDIO_DIR / f"news_{i+1:02d}.mp3"
        segments.append((f"news_{i+1:02d}", path))
        await speak(text, path)

    # 綜合洞察
    insight_text = f"{clash_or_sync}。投資人提醒，{investor_reminder}"
    insight_path = AUDIO_DIR / "insight.mp3"
    segments.append(("insight", insight_path))
    await speak(insight_text, insight_path)

    # 結尾
    ending_text = "以上是今日雙軌財經情報雷達，我們明天見。"
    ending_path = AUDIO_DIR / "ending.mp3"
    segments.append(("ending", ending_path))
    await speak(ending_text, ending_path)

    # 量測每段實際時長並寫入 durations.json
    durations = {key: round(get_duration(path), 3) for key, path in segments}
    DURATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DURATIONS_PATH.write_text(json.dumps(durations, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("已寫入時長資料：%s", DURATIONS_PATH)


def run(data: dict) -> None:
    """供 main.py 直接呼叫的同步入口。"""
    asyncio.run(generate_all(data))
    log.info("[完成] 旁白音檔已存至 %s", AUDIO_DIR)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成影片旁白音檔")
    parser.add_argument("--data", default="video/src/data/sample.json", help="輸入 JSON 路徑")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        raise SystemExit(f"找不到資料檔：{data_path}")

    data = json.loads(data_path.read_text(encoding="utf-8"))
    run(data)
    print(f"\n[完成] 音檔已存至 {AUDIO_DIR}/")
    print("  opening.mp3  / news_01–05.mp3  / insight.mp3  / ending.mp3")
