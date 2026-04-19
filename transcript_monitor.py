"""
transcript_monitor.py — 自動取得逐字稿（字幕 API 優先，完全不需下載音檔）

背景說明：
  Oracle Cloud VM 的 datacenter IP 被 YouTube 封鎖，yt-dlp 無法下載影片。
  但 YouTube 字幕 API 使用不同端點，不受此限制。

流程：
  1. YouTube Data API v3 的 playlistItems 取得最新影片 ID（官方 API，無 bot 偵測）
  2. youtube-transcript-api 直接取得中文字幕（字幕端點，VM 可用）
  3. 字幕存入 TRANSCRIPT_DIR，讓後續 step_analyze 直接使用

API 配額：
  - channels.list: 1 unit（只在 process 中執行一次，之後快取）
  - playlistItems.list: 1 unit/次
  - youtube-transcript-api: 不佔 Data API 配額（免費字幕端點）
  每日總使用：約 4 units（免費配額 10,000 units/day）
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import CHANNELS, TRANSCRIPT_DIR, YOUTUBE_API_KEY

log = logging.getLogger(__name__)

YT_API_BASE = "https://www.googleapis.com/youtube/v3"

# handle → channel_id 快取（同一 process 不重複 API 呼叫）
_CHANNEL_ID_CACHE: dict[str, str] = {}


# ── YouTube Data API 工具 ─────────────────────────────────────────────────────

def _yt_api_get(endpoint: str, params: dict) -> dict:
    """呼叫 YouTube Data API v3，回傳解析後的 JSON dict。"""
    if not YOUTUBE_API_KEY:
        log.error("YOUTUBE_API_KEY 未設定，無法呼叫 YouTube API")
        return {}
    all_params = {**params, "key": YOUTUBE_API_KEY}
    query = "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='')}"
        for k, v in all_params.items()
    )
    url = f"{YT_API_BASE}/{endpoint}?{query}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log.error("YouTube API 呼叫失敗 [%s]：%s", endpoint, e)
        return {}


def _get_channel_id(handle: str) -> str | None:
    """
    將 YouTube @handle 解析成 channel_id。
    結果快取在 _CHANNEL_ID_CACHE，同一 process 只呼叫一次 API。
    """
    clean = handle.lstrip("@").lower()
    if clean in _CHANNEL_ID_CACHE:
        return _CHANNEL_ID_CACHE[clean]

    data = _yt_api_get("channels", {"part": "id", "forHandle": clean})
    items = data.get("items", [])
    if items:
        channel_id = items[0]["id"]
        _CHANNEL_ID_CACHE[clean] = channel_id
        log.info("channel_id 快取：@%s → %s", clean, channel_id)
        return channel_id

    log.warning("找不到 channel_id（handle=@%s）", clean)
    return None


def _get_latest_videos(channel_id: str, max_results: int = 15) -> list[tuple[str, str, str]]:
    """
    透過頻道的 uploads 播放清單取得最新影片列表。
    回傳 [(video_id, title, date_YYYY-MM-DD), ...]。

    使用 playlistItems（1 unit）而非 search.list（100 units），節省大量配額。
    uploads 播放清單 ID = "UU" + channel_id[2:]（固定規則）。
    """
    playlist_id = "UU" + channel_id[2:]
    data = _yt_api_get("playlistItems", {
        "part": "snippet",
        "playlistId": playlist_id,
        "maxResults": max_results,
    })

    results = []
    for item in data.get("items", []):
        snippet = item.get("snippet", {})
        video_id = snippet.get("resourceId", {}).get("videoId", "")
        title = snippet.get("title", "")
        published_at = snippet.get("publishedAt", "")
        if not video_id:
            continue
        date_str = published_at[:10] if published_at else ""
        results.append((video_id, title, date_str))

    return results


# ── youtube-transcript-api ────────────────────────────────────────────────────

def _fetch_youtube_transcript(video_id: str, channel_name: str) -> str | None:
    """
    用 youtube-transcript-api v1.x 取得影片中文字幕。
    v1.x API：fetch()（直接取特定語言）、list()（列出所有可用字幕）。

    字幕端點（timedtext API）和影片下載端點不同，
    在 Oracle Cloud VM 等 datacenter IP 通常不受 bot 偵測封鎖。
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        log.error("缺少 youtube-transcript-api，請執行：pip install youtube-transcript-api")
        return None

    def _items_to_text(items) -> str:
        """相容 dict（舊版）和 object（新版）兩種格式。"""
        parts = []
        for t in items:
            text = t["text"] if isinstance(t, dict) else getattr(t, "text", "")
            if text:
                parts.append(text.strip())
        return " ".join(parts)

    # ── 方法 1：直接 fetch 指定語言（v1.x 推薦方式）──────────────────────────
    for langs in [["zh-TW"], ["zh-Hant"], ["zh-Hans"], ["zh"],
                  ["zh-TW", "zh-Hant", "zh-Hans", "zh"]]:
        try:
            items = YouTubeTranscriptApi.fetch(video_id, languages=langs)
            text = _items_to_text(items)
            if text:
                log.info("[%s] 字幕取得成功（語言：%s）：%d 字", channel_name, langs, len(text))
                return text
        except Exception as e:
            log.debug("[%s] fetch langs=%s 失敗：%s", channel_name, langs, e)
            continue

    # ── 方法 2：列出所有字幕，找中文（含自動生成）────────────────────────────
    try:
        transcript_list = YouTubeTranscriptApi.list(video_id)
        available = []
        for t in transcript_list:
            lang_code = t.language_code if hasattr(t, "language_code") else str(t)
            available.append(lang_code)
            if any(lc in lang_code for lc in ["zh", "zh-TW", "zh-Hans", "zh-Hant"]):
                fetched = t.fetch() if hasattr(t, "fetch") else t
                text = _items_to_text(fetched)
                if text:
                    log.info("[%s] 找到中文字幕（%s）：%d 字", channel_name, lang_code, len(text))
                    return text
        log.warning("[%s] 無中文字幕，可用語言：%s", channel_name, available)
    except Exception as e:
        log.warning("[%s] 字幕列表取得失敗（video_id=%s）：%s", channel_name, video_id, e)

    return None


# ── 主入口 ────────────────────────────────────────────────────────────────────

def monitor_and_fetch_transcript(
    channel_key: str,
    video_url_override: str | None = None,
) -> dict:
    """
    對單一頻道執行字幕監控。
    回傳格式與 monitor.py 的 monitor_and_download() 完全相容，
    額外包含 transcript（逐字稿文字）與 transcript_source 欄位。
    """
    ch = CHANNELS[channel_key]
    ch_name = ch["name"]

    video_id: str | None = None
    title: str = ""
    video_date: str | None = None

    if video_url_override:
        # 從 URL 解析 video_id
        m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", video_url_override)
        if not m:
            m = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", video_url_override)
        if m:
            video_id = m.group(1)
            log.info("[%s] 使用指定影片 ID：%s", ch_name, video_id)

    if not video_id:
        # 從頻道 URL 解析 handle：https://www.youtube.com/@handle/streams
        m = re.search(r"@([^/]+)", ch["url"])
        if not m:
            log.error("[%s] 無法從 URL 解析 handle：%s", ch_name, ch["url"])
            return _fail_result(channel_key)

        handle = m.group(1)
        channel_id = _get_channel_id(handle)
        if not channel_id:
            return _fail_result(channel_key)

        videos = _get_latest_videos(channel_id)
        if not videos:
            log.warning("[%s] 無法取得影片列表", ch_name)
            return _fail_result(channel_key)

        keyword = ch.get("title_keyword", "")
        matched = [(vid, t, d) for vid, t, d in videos if keyword and keyword in t]

        if not matched:
            log.warning("[%s] 找不到含關鍵字「%s」的影片，取最新一支", ch_name, keyword)
            matched = videos[:1]

        video_id, title, video_date = matched[0]

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    log.info("[%s] 目標影片：%s（%s）", ch_name, title or video_id, video_date or "日期未知")

    # 取得字幕
    transcript = _fetch_youtube_transcript(video_id, ch_name)

    if not transcript:
        log.warning("[%s] 字幕不可用（video_id=%s），需要音檔 fallback", ch_name, video_id)
        return {
            "channel": channel_key,
            "success": False,
            "transcript": None,
            "audio_path": None,
            "video_url": video_url,
            "title": title,
            "video_date": video_date,
        }

    # 儲存逐字稿，讓 step_analyze 的 load_transcript() 可以直接讀取
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = TRANSCRIPT_DIR / f"{channel_key}.txt"
    out_path.write_text(transcript, encoding="utf-8")
    log.info("[%s] 逐字稿已儲存：%s（%d 字）", ch_name, out_path, len(transcript))

    return {
        "channel": channel_key,
        "success": True,
        "transcript": transcript,
        "audio_path": None,          # 無需音檔
        "video_url": video_url,
        "title": title,
        "video_date": video_date,
        "transcript_source": "youtube_captions",
    }


def _fail_result(channel_key: str) -> dict:
    return {
        "channel": channel_key,
        "success": False,
        "transcript": None,
        "audio_path": None,
        "video_url": None,
        "title": None,
        "video_date": None,
    }


def run_dual_transcript_monitor(
    url_overrides: dict[str, str] | None = None,
) -> dict[str, dict]:
    """同時對兩個頻道執行字幕監控（ThreadPoolExecutor）。"""
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(
                monitor_and_fetch_transcript,
                key,
                url_overrides.get(key) if url_overrides else None,
            ): key
            for key in CHANNELS
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as exc:
                log.error("[%s] 執行緒例外：%s", key, exc)
                results[key] = _fail_result(key)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    results = run_dual_transcript_monitor()
    for key, res in results.items():
        status = "[OK]" if res["success"] else "[FAIL]"
        chars = len(res.get("transcript") or "")
        print(f"{status} {CHANNELS[key]['name']}：{chars} 字 → {res.get('title', '')}")
