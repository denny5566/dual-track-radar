"""
Step 1 — 頻道監控與音檔下載
自動從兩個 YouTube 頻道的 /streams 頁面抓取最新直播存檔，下載為 mp3。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yt_dlp

from config import AUDIO_DIR, CHANNELS, YTDLP_OPTS_AUDIO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _fetch_latest_stream_url(channel_url: str, channel_name: str) -> tuple[str, str] | None:
    """
    從頻道 /streams 頁面取得最新一支「已完成」的直播存檔 URL。
    跳過尚未開始的預約直播。
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "playlistend": 5,           # 多抓幾支以備第一支是預約中
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    if not info or not info.get("entries"):
        log.warning("[%s] 無法取得播放清單", channel_name)
        return None

    for entry in info["entries"]:
        if not entry:
            continue
        video_id = entry.get("id") or entry.get("url", "")
        title = entry.get("title", "")
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        # 快速檢查是否已完成（嘗試取得影片資訊）
        check_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        try:
            with yt_dlp.YoutubeDL(check_opts) as ydl:
                meta = ydl.extract_info(video_url, download=False)
            # 預約直播的 live_status 是 "is_upcoming"，已完成是 "was_live" 或 None
            live_status = meta.get("live_status", "")
            if live_status == "is_upcoming" or live_status == "is_live":
                log.info("[%s] 跳過（%s）：%s", channel_name, live_status, title)
                continue
            log.info("[%s] 找到最新存檔：%s", channel_name, title)
            return video_url, title
        except Exception:
            continue

    log.warning("[%s] 找不到已完成的直播存檔", channel_name)
    return None


def _download_audio(video_url: str, out_path: Path, channel_name: str) -> bool:
    """下載指定影片的音訊，存為 mp3。"""
    opts = {
        **YTDLP_OPTS_AUDIO,
        "outtmpl": str(out_path.with_suffix("")),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([video_url])
        log.info("[%s] 音檔已儲存：%s", channel_name, out_path)
        return True
    except Exception as exc:
        log.error("[%s] 下載失敗：%s", channel_name, exc)
        return False


def monitor_and_download(channel_key: str) -> dict:
    """監控單一頻道並下載最新音檔。"""
    ch = CHANNELS[channel_key]
    out_path = AUDIO_DIR / ch["audio_filename"]
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    result = _fetch_latest_stream_url(ch["url"], ch["name"])
    if not result:
        return {"channel": channel_key, "success": False, "audio_path": None}

    video_url, title = result
    success = _download_audio(video_url, out_path, ch["name"])
    return {
        "channel": channel_key,
        "success": success,
        "audio_path": str(out_path) if success else None,
        "video_url": video_url,
        "title": title,
    }


def run_dual_monitor() -> dict[str, dict]:
    """同時監控兩個頻道（ThreadPoolExecutor）。"""
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(monitor_and_download, key): key
            for key in CHANNELS
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as exc:
                log.error("[%s] 執行緒例外：%s", key, exc)
                results[key] = {"channel": key, "success": False, "audio_path": None}
    return results


if __name__ == "__main__":
    results = run_dual_monitor()
    for key, res in results.items():
        status = "OK" if res["success"] else "FAIL"
        print(f"[{status}] {CHANNELS[key]['name']}: {res.get('title', '')} → {res.get('audio_path', '無')}")
