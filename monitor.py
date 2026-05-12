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

from config import (
    AUDIO_DIR,
    CHANNELS,
    FFMPEG_LOCATION,
    YTDLP_COOKIE_FILE,
    YTDLP_EXTRACTOR_ARGS,
    YTDLP_OPTS_AUDIO,
    YTDLP_USE_OAUTH2,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _drop_cookiefile(opts: dict) -> dict:
    """回傳移除 cookiefile 後的 yt-dlp 選項，用於舊影片 fallback。"""
    return {k: v for k, v in opts.items() if k != "cookiefile"}


def _fetch_latest_stream_url(
    channel_url: str,
    channel_name: str,
    title_keyword: str = "",
    target_date: str | None = None,
) -> tuple[str, str, str | None] | None:
    """
    從頻道 /streams 頁面取得最新一支「已完成」的直播存檔 URL。
    只發一次 flat extract 請求，避免多次請求觸發 YouTube bot 偵測。
    若指定 title_keyword，優先取標題含有該關鍵字的影片；找不到時 fallback 取最新一支。
    """
    import os
    _cookie_opts = {"cookiefile": YTDLP_COOKIE_FILE} if YTDLP_COOKIE_FILE and os.path.exists(YTDLP_COOKIE_FILE) else {}
    _oauth2_opts = {"username": "oauth2", "password": ""} if YTDLP_USE_OAUTH2 else {}
    opts = {
        "quiet": False,
        "no_warnings": False,
        "extract_flat": "in_playlist",
        "playlistend": 15,
        **_cookie_opts,
        **_oauth2_opts,
        **({"extractor_args": YTDLP_EXTRACTOR_ARGS} if YTDLP_EXTRACTOR_ARGS else {}),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
    except Exception as exc:
        log.error("[%s] 頻道播放清單抓取失敗：%s", channel_name, exc)
        return None

    if not info or not info.get("entries"):
        log.warning("[%s] 無法取得播放清單", channel_name)
        return None

    def _pick(entries: list, keyword: str, expected_date: str | None) -> tuple[str, str, str | None] | None:
        """從 entries 挑選第一支符合條件的已完成影片（只用 flat extract 資料，不額外發請求）。"""
        import re as _re
        month_map = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12",
        }
        for entry in entries:
            if not entry:
                continue
            video_id = entry.get("id") or ""
            title    = entry.get("title", "")
            if not video_id:
                continue
            # flat extract 裡 live_status 有時已填入，可直接判斷
            live_status = entry.get("live_status", "")
            if live_status in ("is_upcoming", "is_live"):
                log.info("[%s] 跳過（%s）：%s", channel_name, live_status, title)
                continue
            if keyword and keyword not in title:
                log.info("[%s] 跳過（標題不符）：%s", channel_name, title)
                continue
            # 取得影片日期：優先用 yt-dlp 的 upload_date（YYYYMMDD），否則從標題解析
            video_date: str | None = None
            raw_date = entry.get("upload_date", "") or ""
            if len(raw_date) == 8 and raw_date.isdigit():
                video_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            else:
                m = _re.search(r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', title)
                if m:
                    video_date = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
                else:
                    m2 = _re.search(r'([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})', title)
                    if m2:
                        month = month_map.get(m2.group(1).lower())
                        if month:
                            video_date = f"{m2.group(3)}-{month}-{m2.group(2).zfill(2)}"
            if expected_date and video_date != expected_date:
                log.info("[%s] 跳過（日期不符 %s）：%s", channel_name, expected_date, title)
                continue
            log.info("[%s] 找到最新存檔：%s（影片日期：%s）", channel_name, title, video_date or "未知")
            return f"https://www.youtube.com/watch?v={video_id}", title, video_date
        return None

    result = _pick(info["entries"], title_keyword, target_date)

    # 關鍵字無匹配時 fallback：取最新一支已完成的存檔
    if result is None and title_keyword:
        if target_date:
            log.warning("[%s] 日期 %s 下找不到含關鍵字「%s」的影片，改以同日期最新影片回退",
                        channel_name, target_date, title_keyword)
        else:
            log.warning("[%s] 關鍵字「%s」無匹配，改取最新一支存檔", channel_name, title_keyword)
        result = _pick(info["entries"], "", target_date)

    if result is None:
        if target_date:
            log.warning("[%s] 找不到 %s 的可下載直播存檔", channel_name, target_date)
        else:
            log.warning("[%s] 找不到可下載的直播存檔", channel_name)

    return result


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

    attempts = [("預設", opts)]
    if opts.get("cookiefile"):
        attempts.append(("不帶 cookies fallback", _drop_cookiefile(opts)))

    for attempt_name, attempt_opts in attempts:
        try:
            with yt_dlp.YoutubeDL(attempt_opts) as ydl:
                ydl.download([video_url])
        except Exception as exc:
            log.error("[%s] %s 下載失敗：%s", channel_name, attempt_name, exc)
            # PostProcessingError：yt-dlp postprocessor 在 Windows 常拋例外
            # 但原始音訊可能已下載成功，嘗試手動轉換
            if out_path.exists():
                log.info("[%s] 例外後發現 mp3 已存在，視為成功（%s）", channel_name, attempt_name)
                return True
            if raw_path.exists():
                log.warning("[%s] 後處理拋出例外，嘗試手動轉換（%s）...", channel_name, attempt_name)
                if _ffmpeg_convert(raw_path, out_path):
                    log.info("[%s] 手動轉換成功：%s（%s）", channel_name, out_path, attempt_name)
                    return True
                log.error("[%s] 手動轉換也失敗（%s）", channel_name, attempt_name)
        else:
            if out_path.exists():
                log.info("[%s] 音檔已儲存：%s（%s）", channel_name, out_path, attempt_name)
                return True
            if raw_path.exists():
                log.warning("[%s] %s 後處理失敗，嘗試手動轉換...", channel_name, attempt_name)
                if _ffmpeg_convert(raw_path, out_path):
                    log.info("[%s] 手動轉換成功：%s（%s）", channel_name, out_path, attempt_name)
                    return True
                log.error("[%s] 手動轉換也失敗（%s）", channel_name, attempt_name)

    log.error("[%s] 下載後音檔不存在：%s", channel_name, raw_path)
    return False


def monitor_and_download(channel_key: str, target_date: str | None = None) -> dict:
    """監控單一頻道並下載最新音檔。"""
    ch = CHANNELS[channel_key]
    out_path = AUDIO_DIR / ch["audio_filename"]
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    result = _fetch_latest_stream_url(ch["url"], ch["name"], ch.get("title_keyword", ""), target_date=target_date)
    if not result:
        return {"channel": channel_key, "success": False, "audio_path": None}

    video_url, title, video_date = result
    success = _download_audio(video_url, out_path, ch["name"])
    return {
        "channel": channel_key,
        "success": success,
        "audio_path": str(out_path) if success else None,
        "video_url": video_url,
        "title": title,
        "video_date": video_date,
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
        **_cookie_opts,
        **({"extractor_args": YTDLP_EXTRACTOR_ARGS} if YTDLP_EXTRACTOR_ARGS else {}),
    }
    import re as _re
    title = video_url
    video_date: str | None = None
    for meta_opts in [check_opts, _drop_cookiefile(check_opts) if check_opts.get("cookiefile") else None]:
        if not meta_opts:
            continue
        try:
            with yt_dlp.YoutubeDL(meta_opts) as ydl:
                meta = ydl.extract_info(video_url, download=False)
            if meta:
                title = meta.get("title", video_url)
                raw_date = meta.get("upload_date", "") or ""
                if len(raw_date) == 8 and raw_date.isdigit():
                    video_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
                else:
                    m = _re.search(r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', title)
                    if m:
                        video_date = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
                break
        except Exception:
            continue

    log.info("[%s] 指定下載：%s（影片日期：%s）", ch["name"], title, video_date or "未知")
    success = _download_audio(video_url, out_path, ch["name"])
    return {
        "channel": channel_key,
        "success": success,
        "audio_path": str(out_path) if success else None,
        "video_url": video_url,
        "title": title,
        "video_date": video_date,
    }


def run_dual_monitor(
    url_overrides: dict[str, str] | None = None,
    target_date: str | None = None,
) -> dict[str, dict]:
    """同時監控兩個頻道（ThreadPoolExecutor）。
    url_overrides: {channel_key: video_url}，有值則下載指定 URL，否則下載最新。
    """
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(
                download_specific_url if (url_overrides and key in url_overrides) else monitor_and_download,
                key,
                *([url_overrides[key]] if (url_overrides and key in url_overrides) else [target_date]),
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
