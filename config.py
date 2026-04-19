"""
AI 雙軌財經情報雷達 — 全域設定
"""

import os
import shutil
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

# ── 資料庫 ──────────────────────────────────────────────────────────────────
DB_PATH = BASE_DIR / "data" / "radar.db"

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

# ── 環境 / 模型切換 ──────────────────────────────────────────────────────────
# ENV=dev  → 使用 Claude Haiku（低成本，適合開發測試）
# ENV=prod → 使用 Claude Sonnet（高品質，正式環境）
ENV = os.getenv("ENV", "dev")
CLAUDE_HAIKU_MODEL  = "claude-haiku-4-5-20251001"
CLAUDE_SONNET_MODEL = "claude-sonnet-4-6"
CLAUDE_MODEL = CLAUDE_HAIKU_MODEL if ENV == "dev" else CLAUDE_SONNET_MODEL

# ── Groq Whisper API ────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# auto   → 優先嘗試 Groq，失敗時 fallback 到 faster-whisper
# groq   → 強制使用 Groq API
# local  → 強制使用 faster-whisper（本地）
WHISPER_BACKEND = os.getenv("WHISPER_BACKEND", "auto")

# ── faster-whisper（本地）────────────────────────────────────────────────────
# 模型尺寸：tiny / base / small / medium / large-v3
WHISPER_MODEL     = os.getenv("WHISPER_MODEL", "base")
WHISPER_DEVICE    = os.getenv("WHISPER_DEVICE", "cpu")    # cpu / cuda
WHISPER_COMPUTE   = os.getenv("WHISPER_COMPUTE", "int8")  # int8 / float16 / float32
# 音訊切片長度（毫秒），超過此長度的音檔會先切片再轉錄
CHUNK_DURATION_MS = int(os.getenv("CHUNK_DURATION_MS", 10 * 60 * 1000))  # 預設 10 分鐘

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

# ── YouTube 上傳（OAuth2）───────────────────────────────────────────────────
# 首次取得 refresh_token：python publish_video.py --auth
YOUTUBE_API_KEY       = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_CLIENT_ID     = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

# ── Instagram / Threads ──────────────────────────────────────────────────────
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
IG_USER_ID      = os.getenv("IG_USER_ID", "")
# 影片對外公開 URL 基礎（供 Instagram Reels 上傳，例：http://129.150.39.175）
IG_VIDEO_BASE_URL = os.getenv("IG_VIDEO_BASE_URL", "")

# ── yt-dlp 選項 ─────────────────────────────────────────────────────────────
# cookies.txt 路徑（從瀏覽器匯出的 Netscape 格式，解決 YouTube bot 偵測）
def _resolve_cookie_file() -> str | None:
    """優先使用環境變數，其次自動偵測專案內 cookies.txt 與容器路徑。"""
    candidates = [
        os.getenv("YTDLP_COOKIE_FILE", "").strip(),
        str(BASE_DIR / "cookies.txt"),
        "/app/cookies.txt",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


YTDLP_COOKIE_FILE = _resolve_cookie_file()

# OAuth2 Device Code flow（yt-dlp-youtube-oauth2 插件）
# 設 YTDLP_USE_OAUTH2=true 後，需在 VM 上執行一次互動式授權：
#   docker exec -it <discord-bot容器> yt-dlp --username oauth2 --password '' https://www.youtube.com/watch?v=jNQXAC9IVRw
#   按提示在手機/電腦完成 Google 帳號授權，token 存於 /root/.cache/yt-dlp/
YTDLP_USE_OAUTH2 = os.getenv("YTDLP_USE_OAUTH2", "false").lower() == "true"
YTDLP_PLAYER_CLIENTS = [
    client.strip()
    for client in os.getenv("YTDLP_PLAYER_CLIENTS", "").split(",")
    if client.strip()
]
YTDLP_EXTRACTOR_ARGS = (
    {"youtube": {"player_client": YTDLP_PLAYER_CLIENTS}}
    if YTDLP_PLAYER_CLIENTS
    else {}
)
_NODE_PATH = shutil.which("node")
YTDLP_JS_RUNTIMES = {"node": {"path": _NODE_PATH}} if _NODE_PATH else {}

YTDLP_OPTS_AUDIO = {
    "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "128",
    }],
    "postprocessor_args": {"ffmpeg": ["-y"]},   # 強制覆蓋輸出檔
    "overwrites": True,
    "quiet": False,                             # 顯示 yt-dlp 錯誤訊息，方便診斷
    "no_warnings": False,
    "retries": 3,                               # 失敗時快速回報，不無限重試
    "fragment_retries": 3,
    "socket_timeout": 30,                       # socket 超時（秒）
    # OAuth2：啟用時以「智慧電視」身份認證，有機會繞過 datacenter IP 封鎖
    **({"username": "oauth2", "password": ""} if YTDLP_USE_OAUTH2 else {}),
    **({"cookiefile": YTDLP_COOKIE_FILE} if YTDLP_COOKIE_FILE else {}),
    **({"extractor_args": YTDLP_EXTRACTOR_ARGS} if YTDLP_EXTRACTOR_ARGS else {}),
    **({"js_runtimes": YTDLP_JS_RUNTIMES} if YTDLP_JS_RUNTIMES else {}),
    **({"ffmpeg_location": FFMPEG_LOCATION} if FFMPEG_LOCATION else {}),
}
