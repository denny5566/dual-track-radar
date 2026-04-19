"""
Step 1 — 頻道監控與音檔下載
自動從兩個 YouTube 頻道的 /streams 頁面抓取最新直播存檔，下載為 mp3。
"""

from __future__ import annotations

import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yt_dlp

from config import AUDIO_DIR, CHANNELS, FFMPEG_LOCATION, YTDLP_COOKIE_FILE, YTDLP_OPTS_AUDIO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _fetch_latest_stream_url(channel_url: str, channel_name: str, title_keyword: str = "") -> tuple[str, str] | None:
    """
    從頻道 /streams 頁面取得最新一支「已完成」的直播存檔 URL。
    跳過尚未開始的預約直播。
    若指定 title_keyword，只考慮標題含有該關鍵字的影片。
    """
    import os
    _cookie_opts = {"cookiefile": YTDLP_COOKIE_FILE} if YTDLP_COOKIE_FILE and os.path.exists(YTDLP_COOKIE_FILE) else {}
    opts = {
        "quiet": False,
        "no_warnings": False,
        "extract_flat": "in_playlist",
        "playlistend": 10,          # 多抓幾支以確保能找到符合關鍵字的影片
        "extractor_args": {
            "youtube": {"player_client": ["ios", "android", "web"]},
        },
        **_cookie_opts,
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

        # 關鍵字過濾
        if title_keyword and title_keyword not in title:
            log.info("[%s] 跳過（標題不符）：%s", channel_name, title)
            continue

        # 快速檢查是否已完成（嘗試取得影片資訊）
        check_opts = {
            "quiet": False,
            "no_warnings": False,
            "skip_download": True,
            "extractor_args": {
                "youtube": {"player_client": ["ios", "android", "web"]},
            },
            **_cookie_opts,
        }
        try:
            with yt_dlp.YoutubeDL(check_opts) as ydl:
                meta = ydl.extract_info(video_url, download=False)
            if not meta:
                log.warning("[%s] 無法取得影片資訊，跳過：%s", channel_name, title)
                continue
            # 預約直播的 live_status 是 "is_upcoming"，已完成是 "was_live" 或 None
            live_status = meta.get("live_status", "")
            if live_status in ("is_upcoming", "is_live"):
                log.info("[%s] 跳過（%s）：%s", channel_name, live_status, title)
                continue
            log.info("[%s] 找到最新存檔：%s", channel_name, title)
            return video_url, title
        except Exception as exc:
            log.warning("[%s] 檢查影片失敗，跳過：%s（%s）", channel_name, title, exc)
            continue

    log.warning("[%s] 找不到符合條件的直播存檔（關鍵字：%s）", channel_name, title_keyword)
    return None


def _ffmpeg_convert(src: Path, dst: Path) -> bool:
    """用 subprocess 直接呼叫 ffmpeg 將 src 轉成 mp3，繞過 yt-dlp postprocessor 在 Windows 的 bug。"""
    ffmpeg_bin = "ffmpeg"
    if FFMPEG_LOCATION:
        ffmpeg_bin = str(Path(FFMPEG_LOCATION) / "ffmpeg.exe")
    cmd = [ffmpeg_bin, "-y", "-i", str(src), "-vn", "-acodec", "libmp3lame", "-b:a", "128k", str(dst)]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def _download_audio(video_url: str, out_path: Path, channel_name: str) -> bool:
    """下載指定影片的音訊，存為 mp3。"""
    raw_path = out_path.with_suffix("")   # yt-dlp 下載的原始檔（無副檔名）

    # 先刪除舊檔，確保成功判斷不會誤讀上次殘留的音檔
    for old in (out_path, raw_path):
        if old.exists():
            try:
                old.unlink()
                log.info("[%s] 已刪除舊音檔：%s", channel_name, old.name)
            except Exception as e:
                log.warning("[%s] 無法刪除舊音檔 %s：%s", channel_name, old.name, e)

    opts = {
        **YTDLP_OPTS_AUDIO,
        "outtmpl": str(raw_path),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([video_url])
    except Exception as exc:
        log.error("[%s] 下載失敗：%s", channel_name, exc)

    # yt-dlp postprocessor succeeded
    if out_path.exists():
        log.info("[%s] 音檔已儲存：%s", channel_name, out_path)
        return True

    # Fallback: postprocessor failed on Windows, convert manually
    if raw_path.exists():
        log.warning("[%s] yt-dlp 後處理失敗，嘗試手動轉換...", channel_name)
        if _ffmpeg_convert(raw_path, out_path):
            log.info("[%s] 手動轉換成功：%s", channel_name, out_path)
            return True
        log.error("[%s] 手動轉換也失敗", channel_name)
    else:
        log.error("[%s] 下載後音檔不存在：%s", channel_name, raw_path)
    return False


def monitor_and_download(channel_key: str) -> dict:
    """監控單一頻道並下載最新音檔。"""
    ch = CHANNELS[channel_key]
    out_path = AUDIO_DIR / ch["audio_filename"]
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    result = _fetch_latest_stream_url(ch["url"], ch["name"], ch.get("title_keyword", ""))
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


def download_specific_url(channel_key: str, video_url: str) -> dict:
    """下載指定 URL 的音訊（跳過最新影片搜尋）。"""
    import os
    ch = CHANNELS[channel_key]
    out_path = AUDIO_DIR / ch["audio_filename"]
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # 取得影片標題
    _cookie_opts = {"cookiefile": YTDLP_COOKIE_FILE} if YTDLP_COOKIE_FILE and os.path.exists(YTDLP_COOKIE_FILE) else {}
    check_opts = {
        "quiet": False,
        "no_warnings": False,
        "skip_download": True,
        "extractor_args": {
            "youtube": {"player_client": ["ios", "android", "web"]},
        },
        **_cookie_opts,
    }
    title = video_url
    try:
        with yt_dlp.YoutubeDL(check_opts) as ydl:
            meta = ydl.extract_info(video_url, download=False)
        if meta:
            title = meta.get("title", video_url)
    except Exception:
        pass

    log.info("[%s] 指定下載：%s", ch["name"], title)
    success = _download_audio(video_url, out_path, ch["name"])
    return {
        "channel": channel_key,
        "success": success,
        "audio_path": str(out_path) if success else None,
        "video_url": video_url,
        "title": title,
    }


def run_dual_monitor(url_overrides: dict[str, str] | None = None) -> dict[str, dict]:
    """同時監控兩個頻道（ThreadPoolExecutor）。
    url_overrides: {channel_key: video_url}，有值則下載指定 URL，否則下載最新。
    """
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(
                download_specific_url if (url_overrides and key in url_overrides) else monitor_and_download,
                key,
                *([ url_overrides[key] ] if (url_overrides and key in url_overrides) else []),
            ): key
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
