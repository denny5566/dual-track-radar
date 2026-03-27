"""
AI 雙軌財經情報雷達 — 全域設定
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── 專案根目錄 ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
AUDIO_DIR = OUTPUT_DIR / "audio"
TRANSCRIPT_DIR = OUTPUT_DIR / "transcripts"
ANALYSIS_DIR = OUTPUT_DIR / "analysis"
CARDS_DIR = OUTPUT_DIR / "cards"
TEMPLATES_DIR = BASE_DIR / "templates"

# ── 監控頻道 ────────────────────────────────────────────────────────────────
CHANNELS = {
    "capital_futures": {
        "name": "群益期貨觀點",
        "url": "https://www.youtube.com/@i-view6024/streams",
        "audio_filename": "capital_latest.mp3",
        "color": "#1a56db",           # 法人藍
        "title_keyword": "群益早安",
    },
    "yu_ting_hao": {
        "name": "游庭澔的財經皓角",
        "url": "https://www.youtube.com/@yutinghaofinance/streams",
        "audio_filename": "yu_latest.mp3",
        "color": "#d97706",           # 名家橘
        "title_keyword": "早晨財經速解讀",
    },
}

# ── Google Gemini / LLM ──────────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "large-v3")   # base / small / medium / large-v3

# ── Celery / Redis ──────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

# ── Email (SMTP) ────────────────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)
EMAIL_RECIPIENTS = os.getenv("EMAIL_RECIPIENTS", "").split(",")

# ── ffmpeg 路徑 ──────────────────────────────────────────────────────────────
_FFMPEG_WINGET = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Microsoft/WinGet/Packages"
    / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    / "ffmpeg-8.1-full_build/bin"
)
FFMPEG_LOCATION = str(_FFMPEG_WINGET) if _FFMPEG_WINGET.exists() else None

# 把 ffmpeg bin 加入 PATH，讓 Whisper 也能找到
if FFMPEG_LOCATION and FFMPEG_LOCATION not in os.environ.get("PATH", ""):
    os.environ["PATH"] = FFMPEG_LOCATION + os.pathsep + os.environ.get("PATH", "")

# ── yt-dlp 選項 ─────────────────────────────────────────────────────────────
YTDLP_OPTS_AUDIO = {
    "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "128",
    }],
    "postprocessor_args": {"ffmpeg": ["-y"]},   # 強制覆蓋輸出檔
    "overwrites": True,
    "quiet": True,
    "no_warnings": True,
    **({"ffmpeg_location": FFMPEG_LOCATION} if FFMPEG_LOCATION else {}),
}
