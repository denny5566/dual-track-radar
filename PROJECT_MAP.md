# PROJECT MAP — NTUAI 財經雷達

## 1) 專案目標
本專案會自動追蹤兩個 YouTube 財經頻道，取得逐字稿或音檔後完成 AI 分析，並輸出網站資料、圖文素材、影片素材，再透過 Discord 進行審核與發布流程。

## 2) 一句話架構
`Data Ingestion → Transcribe/Preprocess → LLM Analysis → DB/JSON Export → Web/Video Assets → Publish/Review`

## 3) 端到端資料流
1. 抓取來源  
`main.py` Step 1 優先讀 `data/transcripts/`（GitHub Actions 預抓），其次走 `youtube-transcript-api`，最後 fallback `yt-dlp` 下載音檔。
2. 語音與文本處理  
`transcribe.py`（Groq Whisper 或 faster-whisper）→ `preprocess.py` 清洗逐字稿。
3. 分析與內容生成  
`analyze.py` 產出結構化分析 JSON，`generate_article.py` 生成新聞文案。
4. 儲存與前端資料  
`database.py` 寫入 `data/radar.db`，同步輸出 `web/public/data/*.json` 與 `latest.json`、`index.json`。
5. 素材生成  
`social_cards.py` 產 EDM/PDF，`generate_assets.py` 產背景圖，`generate_audio.py` 產旁白，更新 `video/src/data/sample.json`。
6. 發布與操作  
`discord_bot.py` 提供按鈕控制流程；`publish_video.py` 負責 YouTube/Instagram 發布。

## 4) 主要目錄與責任
- `main.py`：主管線編排（Step 1~7）。
- `config.py`：全域設定、模型切換、路徑與第三方金鑰讀取。
- `discord_bot.py`：Discord 控制台與互動流程。
- `database.py`：SQLite 與前端 JSON 匯出。
- `transcript_monitor.py`：YouTube API + 字幕擷取（VM 友善）。
- `monitor.py`：yt-dlp 下載 fallback。
- `transcribe.py`：語音辨識（Groq / local whisper）。
- `web/`：網站前端與 Express API 代理。
- `video/`：Remotion 影片模板與渲染設定。
- `templates/`：EDM 與報告樣板。
- `output/`：可重建暫存（音檔、逐字稿、分析、卡片）。
- `data/`：資料庫與 JSON 備份（核心持久化）。
- `tools/health_check.py`：快速健康檢查。

## 5) 執行模式
1. 本機 CLI  
`python main.py`
2. Docker（VM）  
`docker compose run --rm radar python main.py --no-email --no-cleanup`
3. Discord 日常操作  
由按鈕觸發完整流程、本機下載、重新分析、指定日期重跑、發布審核。

## 6) 常用指令
```bash
# Python 依賴
pip install -r requirements.txt

# Playwright 瀏覽器
playwright install chromium

# 快速檢查
python tools/health_check.py

# Web build
cd web && npm install && npm run build

# Video type-check
cd ../video && npm install && npx tsc --noEmit

# 完整流程（不寄信、不清理）
python main.py --no-email --no-cleanup
```

## 7) 重要輸出路徑
- `data/radar.db`：每日分析主資料。
- `web/public/data/latest.json`：前端最新資料入口。
- `web/public/data/index.json`：文章列表索引。
- `web/public/images/*.jpg`：文章封面圖。
- `video/out/*.mp4`：渲染影片。
- `output/*`：執行暫存（可清理）。

## 8) 環境變數重點
- 必填核心：`ANTHROPIC_API_KEY`, `DISCORD_BOT_TOKEN`, `DISCORD_OWNER_ID`, `YOUTUBE_API_KEY`
- 下載策略：`YTDLP_COOKIE_FILE`, `YTDLP_USE_OAUTH2`, `YTDLP_PLAYER_CLIENTS`
- 轉錄策略：`WHISPER_BACKEND`, `GROQ_API_KEY`
- 發布策略：`YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`, `IG_ACCESS_TOKEN`, `IG_USER_ID`

## 9) 維運風險與注意事項
- Oracle VM 常被 YouTube 封鎖下載，建議優先依賴字幕 API 與 GA 預抓。
- `cookies.txt` 與 `.env` 含敏感資訊，不可提交版本庫。
- Instagram 發布若失敗，多半是 token 或 Meta 資產權限問題，不一定是程式邏輯錯誤。
- `web/dist/` 為編譯產物，通常由 build 生成，不建議手改。

## 10) 建議的新同事上手順序
1. 先讀 `README.md` + 本文件。
2. 設定 `.env`，跑 `tools/health_check.py`。
3. 執行 `python main.py --no-email --no-cleanup` 看完整輸出。
4. 檢查 `web/public/data/latest.json` 與 `data/radar.db` 是否更新。
5. 最後再接 Discord 按鈕流程與 Docker 部署。
