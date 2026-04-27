"""
publish_video.py — 影片發布至 YouTube 和 Instagram Reels

YouTube 上傳（OAuth2）：
  需設定環境變數：
    YOUTUBE_CLIENT_ID     — Google Cloud Console OAuth2 用戶端 ID
    YOUTUBE_CLIENT_SECRET — Google Cloud Console OAuth2 用戶端密鑰
    YOUTUBE_REFRESH_TOKEN — 初次授權後取得的 refresh_token

  首次取得 refresh_token（本機執行，需開啟瀏覽器）：
    python publish_video.py --auth

Instagram Reels 上傳：
  需設定環境變數：
    IG_ACCESS_TOKEN   — Instagram Graph API 長效存取權杖
    IG_USER_ID        — Instagram 用戶 ID
    IG_VIDEO_BASE_URL — 影片可公開存取的基礎 URL（例：http://129.150.39.175）
                        影片將放在此 URL 下的 /videos/ 路徑
                        Oracle VM 需已掛載 web/public/videos/ 並由 web service 提供服務

函式：
  upload_to_youtube(video_path, title, description, privacy) → video_id | None
  upload_to_instagram(video_path, caption)                   → media_id | None
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from typing import Callable, TypeVar
from pathlib import Path

import requests

from config import (
    BASE_DIR,
    IG_ACCESS_TOKEN,
    IG_USER_ID,
    IG_VIDEO_BASE_URL,
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_REFRESH_TOKEN,
)

log = logging.getLogger(__name__)

# Instagram Graph API 版本
IG_API_VERSION = "v22.0"
# YouTube OAuth2 端點
YT_TOKEN_URI = "https://oauth2.googleapis.com/token"
YT_SCOPES    = ["https://www.googleapis.com/auth/youtube.upload"]
IG_PROCESS_TIMEOUT_SEC = int(os.getenv("IG_PROCESS_TIMEOUT_SEC", "900"))  # 預設最多等 15 分鐘
IG_POLL_INTERVAL_SEC   = int(os.getenv("IG_POLL_INTERVAL_SEC", "10"))     # 預設每 10 秒輪詢

T = TypeVar("T")


def _run_with_retry(
    action: str,
    fn: Callable[[], T],
    attempts: int = 3,
    base_wait: float = 5.0,
) -> T:
    """
    通用重試封裝：失敗後等待並重試，最後一次失敗才拋出例外。
    """
    last_exc: Exception | None = None
    for idx in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if idx >= attempts:
                break
            wait_s = base_wait * (2 ** (idx - 1))
            log.warning("%s 失敗（第 %d/%d 次）：%s；%.1f 秒後重試", action, idx, attempts, exc, wait_s)
            time.sleep(wait_s)
    assert last_exc is not None
    raise last_exc


# ── YouTube ───────────────────────────────────────────────────────────────────

def _get_youtube_credentials():
    """
    使用 refresh_token 取得 Google OAuth2 憑證物件。
    不需要瀏覽器互動（headless 伺服器可用）。
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    if not all([YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN]):
        raise RuntimeError(
            "YouTube OAuth2 憑證未完整設定。"
            "請在 .env 補上 YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN。\n"
            "首次取得 refresh_token 請在本機執行：python publish_video.py --auth"
        )

    creds = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri=YT_TOKEN_URI,
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=YT_SCOPES,
    )
    creds.refresh(Request())
    return creds


def upload_to_youtube(
    video_path: Path,
    title: str,
    description: str = "",
    category: str = "22",   # 22 = People & Blogs；25 = News & Politics
    privacy: str = "public",
) -> str | None:
    """
    上傳影片至 YouTube，回傳 video_id；失敗回傳 None。

    Args:
        video_path: 影片檔案路徑（本地，.mp4）
        title:      影片標題
        description:影片說明
        category:   YouTube 分類 ID（預設 22 = People & Blogs）
        privacy:    "public" / "private" / "unlisted"

    Returns:
        video_id（例 "dQw4w9WgXcQ"）或 None
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        log.error("缺少套件，請執行：pip install google-api-python-client google-auth")
        return None

    if not video_path.exists():
        log.error("[YouTube] 影片檔案不存在：%s", video_path)
        return None

    log.info("[YouTube] 開始上傳：%s（%s）", title, video_path)

    try:
        creds = _get_youtube_credentials()
    except RuntimeError as e:
        log.error("[YouTube] %s", e)
        return None

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title":       title[:100],
            "description": description,
            "categoryId":  category,
            "tags":        ["財經", "台股", "雙軌財經雷達", "StockRadar"],
        },
        "status": {
            "privacyStatus": privacy,
        },
    }

    def _upload_once() -> str:
        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=5 * 1024 * 1024,  # 5 MB per chunk
        )
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                log.info("[YouTube] 上傳進度：%d%%", pct)
        video_id = response.get("id", "")
        if not video_id:
            raise RuntimeError("YouTube API 未回傳 video_id")
        return video_id

    try:
        video_id = _run_with_retry("[YouTube] 上傳", _upload_once, attempts=3, base_wait=8.0)
        url = f"https://www.youtube.com/watch?v={video_id}"
        log.info("[YouTube] 上傳完成：%s", url)
        return video_id
    except Exception as e:
        log.error("[YouTube] 上傳失敗：%s", e)
        return None


# ── Instagram Reels ───────────────────────────────────────────────────────────

def _copy_video_to_web_public(video_path: Path) -> str | None:
    """
    將影片複製到 web/public/videos/，使其可透過 web service 公開存取。
    回傳公開 URL，失敗回傳 None。
    """
    if not IG_VIDEO_BASE_URL:
        log.error(
            "[Instagram] IG_VIDEO_BASE_URL 未設定。"
            "請在 .env 填入 Oracle VM 的公開 IP（例：http://129.150.39.175）"
        )
        return None

    dest_dir = BASE_DIR / "web" / "public" / "videos"
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_file = dest_dir / video_path.name
    shutil.copy2(video_path, dest_file)
    log.info("[Instagram] 影片已複製至：%s", dest_file)

    base = IG_VIDEO_BASE_URL.rstrip("/")
    public_url = f"{base}/videos/{video_path.name}"
    log.info("[Instagram] 公開 URL：%s", public_url)
    return public_url


def upload_to_instagram(
    video_path: Path,
    caption: str = "",
) -> str | None:
    """
    上傳影片至 Instagram Reels，回傳 media_id；失敗回傳 None。

    流程：
      1. 複製影片至 web/public/videos/ → 取得公開 URL
      2. POST /me/media（建立容器）
      3. 輪詢容器狀態，等待 FINISHED
      4. POST /me/media_publish（發布）

    Args:
        video_path: 影片檔案路徑（本地，.mp4，直式 1080×1920）
        caption:    Instagram 貼文說明文字（含 hashtag）

    Returns:
        media_id 或 None
    """
    if not IG_ACCESS_TOKEN or not IG_USER_ID:
        log.error("[Instagram] 憑證未設定（IG_ACCESS_TOKEN / IG_USER_ID）")
        return None

    if not video_path.exists():
        log.error("[Instagram] 影片檔案不存在：%s", video_path)
        return None

    # Step 1：取得公開 URL
    video_url = _copy_video_to_web_public(video_path)
    if not video_url:
        return None

    base_api = f"https://graph.facebook.com/{IG_API_VERSION}/{IG_USER_ID}"

    # Step 2：建立 Reels 容器
    log.info("[Instagram] 建立 Reels 容器...")
    def _create_container_once() -> str:
        r = requests.post(
            f"{base_api}/media",
            params={
                "media_type":   "REELS",
                "video_url":    video_url,
                "caption":      caption,
                "access_token": IG_ACCESS_TOKEN,
            },
            timeout=30,
        )
        if not r.ok:
            log.error("[Instagram] 建立容器失敗（HTTP %s）：%s", r.status_code, r.text[:500])
            r.raise_for_status()
        container_id = r.json().get("id")
        if not container_id:
            raise RuntimeError("Instagram API 未回傳容器 ID")
        return container_id

    try:
        container_id = _run_with_retry("[Instagram] 建立容器", _create_container_once, attempts=3, base_wait=6.0)
        log.info("[Instagram] 容器 ID：%s", container_id)
    except Exception as e:
        log.error("[Instagram] 建立容器失敗：%s", e)
        return None

    # Step 3：輪詢容器狀態（預設最多等 15 分鐘，可由環境變數調整）
    log.info("[Instagram] 等待影片處理...")
    max_attempts = max(1, IG_PROCESS_TIMEOUT_SEC // max(1, IG_POLL_INTERVAL_SEC))
    status_error_count = 0
    for attempt in range(max_attempts):
        time.sleep(max(1, IG_POLL_INTERVAL_SEC))
        try:
            r = requests.get(
                f"https://graph.facebook.com/{IG_API_VERSION}/{container_id}",
                params={
                    "fields":       "status_code,status",
                    "access_token": IG_ACCESS_TOKEN,
                },
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            status_code = data.get("status_code", "")
            log.info("[Instagram] 處理狀態（%d/%d）：%s", attempt + 1, max_attempts, status_code)
            status_error_count = 0

            if status_code == "FINISHED":
                break
            if status_code == "ERROR":
                log.error("[Instagram] 影片處理失敗：%s", data.get("status", ""))
                return None
        except Exception as e:
            status_error_count += 1
            log.warning("[Instagram] 狀態查詢失敗（%d/%d）：%s", attempt + 1, max_attempts, e)
            if status_error_count >= 6:
                log.error("[Instagram] 連續狀態查詢失敗過多，停止等待")
                return None
    else:
        log.error("[Instagram] 影片處理逾時（%d 秒）", IG_PROCESS_TIMEOUT_SEC)
        return None

    # Step 4：發布
    log.info("[Instagram] 發布 Reels...")
    def _publish_once() -> str:
        r = requests.post(
            f"{base_api}/media_publish",
            params={
                "creation_id":  container_id,
                "access_token": IG_ACCESS_TOKEN,
            },
            timeout=30,
        )
        if not r.ok:
            log.error("[Instagram] 發布失敗（HTTP %s）：%s", r.status_code, r.text[:500])
            r.raise_for_status()
        media_id = r.json().get("id")
        if not media_id:
            raise RuntimeError("Instagram API 未回傳 media_id")
        return media_id

    try:
        media_id = _run_with_retry("[Instagram] 發布", _publish_once, attempts=3, base_wait=6.0)
        log.info("[Instagram] 發布完成：media_id=%s", media_id)
        return media_id
    except Exception as e:
        log.error("[Instagram] 發布失敗：%s", e)
        return None


# ── 首次 YouTube 授權（本機執行）─────────────────────────────────────────────

def run_youtube_auth() -> None:
    """
    引導使用者完成 YouTube OAuth2 授權，輸出 refresh_token。
    只需在本機執行一次；之後將 refresh_token 填入 .env 即可。

    使用方式：
        python publish_video.py --auth
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("缺少套件，請執行：pip install google-auth-oauthlib")
        return

    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET:
        print(
            "錯誤：請先在 .env 設定 YOUTUBE_CLIENT_ID 和 YOUTUBE_CLIENT_SECRET\n"
            "取得方式：Google Cloud Console → API 和服務 → 憑證 → 建立 OAuth 2.0 用戶端 ID"
        )
        return

    client_config = {
        "installed": {
            "client_id":     YOUTUBE_CLIENT_ID,
            "client_secret": YOUTUBE_CLIENT_SECRET,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     YT_TOKEN_URI,
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=YT_SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n=== YouTube 授權完成 ===")
    print(f"請將以下 refresh_token 填入 .env：\n")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}\n")


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="影片發布工具")
    parser.add_argument("--auth", action="store_true", help="進行 YouTube OAuth2 首次授權")
    parser.add_argument("--youtube", metavar="FILE", help="上傳指定影片至 YouTube")
    parser.add_argument("--instagram", metavar="FILE", help="上傳指定影片至 Instagram Reels")
    parser.add_argument("--title", default="【財經雷達】今日盤前分析", help="影片標題")
    parser.add_argument("--caption", default="#財經雷達 #台股 #StockRadar", help="IG 說明文字")
    args = parser.parse_args()

    if args.auth:
        run_youtube_auth()
    elif args.youtube:
        vid = upload_to_youtube(Path(args.youtube), title=args.title)
        print(f"YouTube video_id: {vid}" if vid else "上傳失敗")
    elif args.instagram:
        mid = upload_to_instagram(Path(args.instagram), caption=args.caption)
        print(f"Instagram media_id: {mid}" if mid else "上傳失敗")
    else:
        parser.print_help()
