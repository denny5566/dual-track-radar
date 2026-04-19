"""
fetch_transcripts_ga.py — GitHub Actions 專用逐字稿擷取腳本

在 GitHub runner（非 datacenter IP）上執行，繞過 Oracle VM 的 YouTube 封鎖限制。
擷取後寫入 data/transcripts/，透過 git commit 同步至 Oracle VM。

Oracle VM 的 docker-compose.yml 已掛載 ./data:/app/data，
git pull 後容器可直接讀取最新逐字稿，不需重建 image 或重啟容器。

執行方式：
  YOUTUBE_API_KEY=xxx python fetch_transcripts_ga.py
"""

from __future__ import annotations

import datetime
import logging
import os
import re
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# 確保能 import 專案模組
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("ENV", "prod")

try:
    from config import CHANNELS, YOUTUBE_API_KEY
    from transcript_monitor import (
        _fetch_youtube_transcript,
        _get_channel_id,
        _get_latest_videos,
    )
except ImportError as e:
    log.error("模組 import 失敗：%s", e)
    sys.exit(1)

# ── 輸出目錄 ──────────────────────────────────────────────────────────────────
# data/transcripts/ 不在 .gitignore 範圍，隨 git commit 同步至 VM
# docker-compose 掛載 ./data:/app/data，VM 端 git pull 後容器立即可見
OUT_DIR = Path(__file__).parent / "data" / "transcripts"
OUT_DIR.mkdir(parents=True, exist_ok=True)

today = datetime.date.today().isoformat()
success_count = 0

log.info("=== GitHub Actions 逐字稿擷取 (%s) ===", today)

if not YOUTUBE_API_KEY:
    log.error("YOUTUBE_API_KEY 未設定，請在 GitHub Secrets 新增此金鑰")
    sys.exit(1)

for channel_key, ch in CHANNELS.items():
    ch_name = ch["name"]
    log.info("── 頻道：%s ──", ch_name)

    # @handle → channel_id
    m = re.search(r"@([^/]+)", ch["url"])
    if not m:
        log.error("[%s] 無法解析 @handle from URL：%s", ch_name, ch["url"])
        continue

    channel_id = _get_channel_id(m.group(1))
    if not channel_id:
        log.error("[%s] 找不到 channel_id", ch_name)
        continue

    # 取最新影片列表
    videos = _get_latest_videos(channel_id, max_results=15)
    if not videos:
        log.error("[%s] 無法取得影片列表", ch_name)
        continue

    keyword = ch.get("title_keyword", "")
    matched = [(v, t, d) for v, t, d in videos if keyword and keyword in t]
    if not matched:
        log.warning("[%s] 找不到含關鍵字「%s」的影片，取最新一支", ch_name, keyword)
        matched = videos[:1]

    video_id, title, video_date = matched[0]
    log.info("[%s] 目標影片：%s (%s)", ch_name, title, video_date)

    # 取字幕
    transcript = _fetch_youtube_transcript(video_id, ch_name)
    if transcript:
        out_path = OUT_DIR / f"{channel_key}.txt"
        out_path.write_text(transcript, encoding="utf-8")
        log.info("[OK] %s：%d 字 → %s", ch_name, len(transcript), out_path)
        success_count += 1
    else:
        log.error("[FAIL] %s (video_id=%s)：無法取得字幕", ch_name, video_id)

# 寫入日期戳記（VM 端用來確認是否為今日資料）
(OUT_DIR / "fetch_date.txt").write_text(today, encoding="utf-8")
log.info("=== 完成：%d/%d 頻道成功 ===", success_count, len(CHANNELS))

if success_count == 0:
    log.error("所有頻道均失敗，請檢查 YOUTUBE_API_KEY 和網路連線")
    sys.exit(1)
