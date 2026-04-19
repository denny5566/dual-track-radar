# AI 雙軌財經情報雷達

自動追蹤兩個 YouTube 財經頻道，取得逐字稿或音檔後完成分析，輸出網站資料、PDF、Banner、影片素材，並可透過 Discord 控制整條流程。

監控頻道：
- [群益期貨觀點](https://www.youtube.com/@i-view6024/streams)
- [游庭澔的財經皓角](https://www.youtube.com/@yutinghaofinance/streams)

## 核心流程

```text
GitHub Actions 預抓逐字稿
        ↓
YouTube 字幕 API
        ↓
yt-dlp 音檔下載 fallback
        ↓
Whisper / Groq 轉錄
        ↓
逐字稿前處理
        ↓
Claude 分析 + 新聞文章生成
        ↓
SQLite / 靜態 JSON / 網站資料
        ↓
Banner / PDF / 影片旁白 / 配圖
        ↓
Email / YouTube / Instagram / Discord 審核
```

## 環境需求

- Python 3.10+
- Node.js 20+
- `ffmpeg`
- Chromium for Playwright

本機安裝後建議先執行：

```bash
pip install -r requirements.txt
playwright install chromium
```

## .env 重點設定

至少要有這些：

```env
ANTHROPIC_API_KEY=...
DISCORD_BOT_TOKEN=...
DISCORD_OWNER_ID=...
DISCORD_CHANNEL_ID=...
YOUTUBE_API_KEY=...

YTDLP_COOKIE_FILE=./cookies.txt
YTDLP_USE_OAUTH2=false
YTDLP_PLAYER_CLIENTS=
```

說明：
- `YTDLP_COOKIE_FILE=./cookies.txt`：固定用專案根目錄 cookies。
- `YTDLP_PLAYER_CLIENTS=`：預設留空，交給 yt-dlp 自己選 client。
- 程式會自動偵測 `node` 讓 yt-dlp 解 JavaScript challenge。
- 若帶 cookies 下載舊影片失敗，現在會自動 fallback 成不帶 cookies 重試。

## 最常用的三種操作方式

### 1. Discord 日常操作

最推薦的日常流程是直接從 Discord 控制面板操作。

控制面板按鈕：
- `🚀 立即執行完整流程`：VM 直接跑完整流程。
- `📋 查看系統狀態`：看最近 5 筆執行紀錄。
- `🖥️ 本機下載`：通知本機 `local_listener.py` 下載並上傳音檔。
- `⚙️ 僅重新分析（不下載）`：對已在 VM 的音檔直接分析。
- `📥 指定 URL 下載`：輸入特定 YouTube URL 直接跑。
- `🗓️ 指定日期重跑`：依日期搜尋當天影片並重跑。
- `🗑️ 清理逐字稿`：清除 `output/transcripts/`。
- `🧹 清理全部暫存`：清除音檔、逐字稿、分析、卡片、旁白與影片暫存。

分析完成後的審核按鈕：
- `📧 送出 EDM`
- `📰 發布新聞`
- `🎬 發布影片`
- `✏️ 修改建議`
- `❌ 取消`

### 2. 本機 CLI 測試

完整跑一次：

```bash
python main.py
```

常用測試參數：

```bash
python main.py --no-email --no-cleanup
python main.py --skip-download --no-email --no-cleanup
python main.py --skip-download --video-date 2026-04-16 --no-email --no-cleanup
```

### 3. VM 正式環境測試

```bash
cd ~/NTUAI_project
docker compose run --rm radar python main.py --no-email --no-cleanup
```

如果是重跑歷史日期：

```bash
docker compose run --rm radar python main.py --skip-download --video-date 2026-04-16 --no-email --no-cleanup
```

## YouTube 被 VM 擋住時的標準流程

當 VM 抓不到影片時，改走這條：

1. 本機執行監聽器

```bash
python local_listener.py
```

2. Discord 按 `🖥️ 本機下載`
3. 等本機完成下載並自動上傳到 VM
4. Discord 按 `⚙️ 僅重新分析（不下載）`

本機也可以直接手動指定 URL 上傳：

```bash
python download_helper.py --cap "https://www.youtube.com/watch?v=..." --yu "https://www.youtube.com/watch?v=..."
```

## 指定日期重跑

### Discord

直接按 `🗓️ 指定日期重跑`，輸入 `YYYY-MM-DD`。

系統會：
- 用 YouTube API / yt-dlp 搜同日期影片
- 優先取符合頻道關鍵字的影片
- 自動跑完整分析流程

### CLI

如果音檔已經準備好：

```bash
python main.py --skip-download --video-date 2026-04-16 --no-email --no-cleanup
```

## 清理策略

### 清理逐字稿

只刪：
- `output/transcripts/*`

### 清理全部暫存

會刪：
- `output/audio/*`
- `output/transcripts/*`
- `output/analysis/*`
- `output/cards/*`
- `video/public/audio/*`
- `video/public/news_*.jpg`
- `video/public/opening_bg.jpg`
- `video/public/insight_bg.jpg`
- `video/public/ending_bg.jpg`
- `video/out/*`
- `web/public/videos/*`

不會刪：
- `data/radar.db`
- `data/*.json`
- `web/public/data/*.json`
- `web/public/images/*.jpg`

## VM 部署與同步

本機推送：

```bash
git add .
git commit -m "message"
git push ntuai master
```

VM 更新：

```bash
cd ~/NTUAI_project
git pull --ff-only origin master
```

若有 Docker / requirements / Playwright 相關更新，建議重建：

```bash
docker compose build radar
docker compose build discord-bot
docker compose up -d discord-bot web
```

## VM 常用指令

```bash
docker compose ps
docker compose logs -f discord-bot
docker compose run --rm radar python main.py --no-email --no-cleanup
docker compose run --rm radar playwright install chromium
```

## 常見問題

### 1. Discord 按了完整流程，但 VM 下載失敗

代表字幕 API 沒拿到，VM 又被 YouTube 擋了。請改走：

```text
本機開 local_listener.py
→ Discord 按「🖥️ 本機下載」
→ Discord 按「⚙️ 僅重新分析（不下載）」
```

### 2. 指定舊影片下載失敗

現在程式會自動先帶 cookies，再 fallback 不帶 cookies。若仍失敗，通常是：
- cookies 已失效
- 該影片格式異常
- YouTube 對該 client 做了限制

### 3. Playwright 報找不到瀏覽器

請在該環境重跑：

```bash
playwright install chromium
```

如果是 Docker 環境，請在容器內跑：

```bash
docker compose run --rm radar playwright install chromium
```

## 專案結構

```text
main.py
discord_bot.py
download_helper.py
local_listener.py
monitor.py
transcript_monitor.py
transcribe.py
analyze.py
generate_article.py
social_cards.py
generate_audio.py
generate_assets.py
config.py
templates/
web/
video/
```
