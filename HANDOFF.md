# 雙軌財經情報雷達 — 開發進度交接文件

> 最後更新：2026-04-17（第四次）
> 對應 PRD：PRD_v2.md

---

## 已完成項目

### Phase 1 — 本機管線（全部完成）

| 模組 | 檔案 | 說明 |
|------|------|------|
| YouTube 下載 | `monitor.py` | yt-dlp 抓兩頻道最新直播存檔，平行雙執行緒，關鍵字過濾 |
| 語音轉文字 | `transcribe.py` | Groq Whisper 優先（2000次/日），失敗 fallback faster-whisper |
| 逐字稿前處理 | `preprocess.py` | regex 清洗 + Claude Haiku 語意整理，財經術語標準化 |
| AI 分析 | `analyze.py` | Claude Haiku（dev）/ Sonnet+extended thinking（prod），輸出含 top5_news + investor_reminder |
| 新聞文章生成 | `generate_article.py` | Step 3.5：Claude 轉換成新聞風格盤前速報，禁止出現頻道名/主播名 |
| 資料庫 | `database.py` | SQLite 存檔 + 輸出靜態 JSON（同步寫入 web/public/data/） |
| 渲染 | `social_cards.py` | Playwright 渲染 EDM Banner（PNG）+ PDF（A4 單頁） |
| Email | `main.py` Step 6 | SMTP Gmail 寄送 |
| 主管線 | `main.py` | 完整 9 步驟，支援各種 skip 參數 |
| Windows 排程 | `setup_schedule.py` | 週一至週五定時執行 |

### Phase 2 — Discord Bot（強化完成）

| 功能 | 說明 |
|------|------|
| `/analyze` | 手動觸發管線，含逐步進度 Embed（每步驟即時更新 ⬜→🔄→✅/❌） |
| `/run` | 強制執行完整流程（排程外手動觸發） |
| `/status` | 查詢近期執行記錄 |
| `/publish` | 發布日報（Email + Discord 頻道）|
| `/revise [建議]` | 帶修改建議重新生成 |
| `/panel` | 在頻道重新發布持久化控制面板 |
| 審核 Embed 按鈕（4 個） | ✅ 發布日報 · 🎬 發布影片 · ✏️ 修改建議（Modal 輸入框）· ❌ 取消 |
| 控制面板（持久化） | Bot 上線時自動發布到 DISCORD_CHANNEL_ID；含「🚀 立即執行完整流程」「📋 查看系統狀態」「⚙️ 僅重新分析」按鈕；Bot 重啟後按鈕仍可用 |
| 進度追蹤 Embed | 管線分 5 步驟獨立執行，即時更新同一條訊息（不阻塞 Discord event loop）|
| DM 通知 | 管線失敗（含失敗步驟）或完成時自動 DM 擁有者 |

### 部署設定（完成，Oracle VM 已部署）

| 檔案 | 說明 |
|------|------|
| `Dockerfile` | ARM64 相容（Oracle VM.Standard.A1.Flex）|
| `docker-compose.yml` | 管線一次性執行 + Bot 常駐 + Web 服務 |
| `setup_cron.sh` | SSH 進 Oracle VM 後執行，自動裝 Docker + 設 crontab + 啟動 Discord Bot |

### GitHub（完成）

- Repo：https://github.com/denny5566/NTUAI_project（Private）
- 所有 Phase 1 + Phase 2 + Phase 3 + Phase 4 程式碼已推上去
- `.env` 已在 `.gitignore` 保護

---

### Phase 3 — Remotion 影片（完成，有 1 個 Bug）

| 項目 | 狀態 | 說明 |
|------|------|------|
| 專案初始化 | ✅ | `video/` 目錄，Node.js + Remotion 4.0 |
| 影片結構設計 | ✅ | Opening → 5大新聞 → 綜合洞察 → Ending |
| Opening 場景 | ✅ | 品牌名 + 日期 + 今日焦點 + **雷達動畫（SVG，逐幀）** |
| 新聞條目場景 | ✅ | `NewsItem.tsx`：圖片（上55%）+ 標題/摘要（下45%），第一～第五篇標籤 |
| 綜合洞察場景 | ✅ | `InsightCard.tsx`：觀點分析（藍框）+ 投資人提醒（金框）+ 背景圖 |
| Ending 場景 | ✅ | `Ending.tsx`：品牌結尾 + hashtag + 免責聲明 + 背景圖 |
| 字體 | ✅ | Noto Sans TC（中文）+ Inter（英文）|
| 整體風格 | ✅ | 新聞播報風（深藍黑 + 紅色 ticker + 金色數據）|
| 新聞配圖 | ✅ | **Pexels API（免費）**，依當日新聞標題用 Claude Haiku 轉英文搜尋 |
| 洞察配圖 | ✅ | **Pexels API**，依 clash_or_sync 內容搜尋 |
| 結尾配圖 | ✅ | **Pexels API**，固定 financial future 類型 |
| 旁白聲音 | ✅ | `zh-TW-YunJheNeural`（**男聲**），8 個音檔 |
| 旁白時長 | ✅ | 生成後用 mutagen 量測真實秒數，寫入 `video/src/data/durations.json` |
| 旁白整合 | ✅ | `<Audio>` 串入每個 Remotion 場景，**場景時長動態跟著音檔走**（+3 秒 buffer） |
| 管線自動化 | ✅ | `main.py` Step 4.5 自動生成圖片 + 旁白，並更新 `video/src/data/sample.json` |
| 直式輸出 | ✅ | `Root.tsx`：1080×1920（IG / TikTok），Composition id=`RadarVideo` |
| 橫式輸出 | ✅ | `Root.tsx`：1920×1080（YouTube），Composition id=`RadarVideoHorizontal` |
| AI 圖片生成 | ⚠️ | Nano Banana（`gemini-3.1-flash-image-preview`）需開 Billing，暫用 Pexels |
| **BUFFER_FRAMES 不一致** | ❌ | `RadarVideo.tsx` = 90，`Root.tsx` = 60；Root 的總長度計算偏短，會導致最後幾幀音頻被截斷 |

> **`NewsCard.tsx` 已刪除**（git 顯示 `D video/src/components/NewsCard.tsx`）。新聞場景全部改由 `NewsItem.tsx` 處理（支援5篇，含佔位漸層），已完全取代舊元件。

---

### Phase 4 — 前端展示網頁（完成，有 2 個待填值）

| 項目 | 狀態 | 說明 |
|------|------|------|
| 首頁 | ✅ | `web/index.html`，文章列表（按月分組），點擊進入文章頁 |
| 文章頁 | ✅ | `web/article.html`，讀取 `?date=YYYYMMDD` 顯示對應報告 |
| 股市行情 | ✅ | TradingView Ticker Tape Widget（含黃金、WTI 原油） |
| 閱讀進度條 | ✅ | 頂部紅色細線，隨捲動更新 |
| 文章封面圖 | ✅ | 底部顯示 Pexels 圖片 |
| 樣式 | ✅ | 極簡深色風，7 個設計 token |
| **UI 可讀性強化** | ✅ | `--text-2` #7a7a7a → #b0b0b0、`--text-3` #3d3d3d → #707070；對比度全面提升 |
| **佈局修正** | ✅ | 移除 `home-main` 全域 `max-width:760px`；新聞頁籤用 `.news-inner` 限寬，儀表板/影片頁籤可全寬 |
| **影片頁籤** | ⚠️ | YouTube 頻道嵌入架構已建立，但 `web/index.html:333` 仍有 `YOUR_CHANNEL_ID` 佔位符未填入 |
| **頁尾** | ✅ | YouTube / Instagram / Threads 社群圖示（hover 色彩特效）+ 著作權聲明 |
| FAB AI 對話 | ✅ | 右下角雷達按鈕開啟側邊抽屜，串接 Claude Haiku API |
| **AI 對話改善** | ✅ | 6 個範例問題；歡迎訊息說明用途；允許財經術語說明 |
| 多頁 Vite | ✅ | `vite.config.js` 設定三入口（main/article/dashboard）+ dev `/api/chat` 中介層 |
| Vercel API | ✅ | `web/api/chat.js`（文章問答）、`web/api/dashboard-chat.js`（儀表板 AI）、`web/api/social-stats.js`（社群統計）|
| 後端資料串接 | ✅ | `database.py` 每次 pipeline 後同步寫入 `web/public/data/` |
| 網站部署 | ⚠️ | 本地驗證完畢，後續將與 Vercel 串接讀取 GitHub |
| **RAG 模組缺失** | ❌ | `vite.config.js:42` 呼叫 `modules/rag_indexer.py`，但此檔案不存在；本機 dev 時 RAG 功能會靜默失敗（catch 住了，不會崩潰） |

### Phase 4+ — 個人儀表板（新增）

| 項目 | 狀態 | 說明 |
|------|------|------|
| 儀表板頁面 | ✅ | `web/d.html`，網址 `/d`（比首頁 `/` 多一個字母）|
| 密碼保護 | ✅ | localStorage 驗證；預設密碼 `radar2026`，在 `web/js/dashboard.js:5` 修改 |
| YouTube 統計 | ✅ | 訂閱數/觀看數/影片數 + 最新影片縮圖列表；使用 `YOUTUBE_API_KEY` + `YOUTUBE_CHANNEL_ID` |
| Instagram 統計 | ⚠️ | UI 已建立；需設 `IG_ACCESS_TOKEN` + `IG_USER_ID` 才能顯示數據 |
| Threads 統計 | ⚠️ | UI 已建立；需設 `THREADS_ACCESS_TOKEN` + `THREADS_USER_ID` 才能顯示數據 |
| 留言文字探勘 | ✅ | YouTube 自動抓取留言（用影片 ID）or 手動貼入；AI 分析情感傾向/熱門主題/建議行動 |
| 儀表板 AI 聊天 | ✅ | 可詢問流量趨勢、內容策略、平台比較；5 個範例快捷問題 |
| 社群統計 API | ✅ | `web/api/social-stats.js` — YouTube（即時）、Instagram（需 Token）、Threads（需 Token）|
| 儀表板 CSS | ✅ | `web/css/dashboard.css` — 獨立樣式，不影響主站 |

#### 前端資料讀取邏輯

```
首頁：GET /data/index.json → 列出所有文章（date、title、tags）
文章頁：GET /data/{dateKey}.json（或 /data/latest.json fallback）
封面圖：GET /images/{dateKey}.jpg（不存在時自動隱藏）
```

#### 匿名化規則（已落實）

- `generate_article.py` SYSTEM_PROMPT 明確禁止出現特定頻道名或主播姓名
- `generate_article.py` user_msg 改為「逐字稿來源 A / B」
- 前端側欄觀點標籤改為「技術面觀察」/ 「宏觀基本面」（不顯示頻道名）
- ⚠️ **注意**：`video/src/types.ts` 的 `comparison` 介面仍寫 `capital_futures` / `yu_ting_hao`，未匿名化（僅前端不顯示，JSON 結構內部仍有）

---

## 已知 Bug 與待修項目

| # | 嚴重度 | 位置 | 問題說明 | 建議修法 |
|---|--------|------|----------|----------|
| 1 | 🔴 高 | `discord_bot.py:254` | 呼叫 `m.step_render_video(data)`，但 `main.py` 中此函式不存在，Discord 按「🎬 發布影片」必然崩潰 | 在 `main.py` 新增 `step_render_video()` 或暫時在 discord_bot.py 中移除該呼叫 |
| 2 | 🟡 中 | `video/src/Root.tsx:8` | `BUFFER_FRAMES = 60`，但 `RadarVideo.tsx` 用 90；Root 計算的總 durationInFrames 會比實際短 150 幀（5秒），Remotion Studio 時間軸不準 | 將 `Root.tsx` 的 `BUFFER_FRAMES` 改為 90 |
| 3 | 🟡 中 | `web/index.html:333` | `YOUR_CHANNEL_ID` 佔位符未填入，影片頁籤無法顯示 YouTube 頻道 | 替換為實際 YouTube Channel ID（`UC` 開頭）|
| 4 | 🟠 低 | `web/vite.config.js:42` | 呼叫 `modules/rag_indexer.py`（不存在），本機 dev 時 RAG 靜默失敗 | 建立 `modules/rag_indexer.py` 或移除 RAG 相關程式碼 |
| 5 | 🟠 低 | `video/src/types.ts` | `comparison` 介面欄位名稱直接暴露頻道名（`capital_futures`、`yu_ting_hao`） | 改為 `perspective_a` / `perspective_b`（非必要，不影響執行）|

---

## 環境變數（`.env` 已填）

| 變數 | 狀態 | 用途 |
|------|------|------|
| `ANTHROPIC_API_KEY` | ✅ 已填 | Claude API（分析 + 網站 AI 聊天）|
| `GROQ_API_KEY` | ✅ 已填 | Groq Whisper 語音辨識 |
| `WHISPER_MODEL` | ✅ base | faster-whisper fallback |
| `SMTP_*` / `EMAIL_*` | ✅ 已填 | Gmail SMTP 寄送 |
| `DISCORD_BOT_TOKEN` | ✅ 已填 | Discord Bot |
| `DISCORD_OWNER_ID` | ✅ 已填 | Bot DM 通知目標 |
| `DISCORD_CHANNEL_ID` | ✅ 已填 | Bot 控制面板 + 發文頻道 |
| `GOOGLE_AI_STUDIO_API_KEY` | ✅ 已填 | Nano Banana 圖片生成（需開 Billing）|
| `PEXELS_API_KEY` | ✅ 已填 | Pexels 圖片（免費，200 req/hr）|
| `YOUTUBE_API_KEY` | ✅ 已填 | YouTube Data API（監控 + 儀表板統計）|
| `YOUTUBE_CHANNEL_ID` | ⚠️ 待填 | 儀表板頻道統計用（`UC` 開頭）|
| `IG_ACCESS_TOKEN` | ⚠️ 待填 | Instagram Graph API（儀表板）|
| `IG_USER_ID` | ⚠️ 待填 | Instagram 用戶 ID（儀表板）|
| `THREADS_ACCESS_TOKEN` | ⚠️ 待填 | Threads API（儀表板）|
| `THREADS_USER_ID` | ⚠️ 待填 | Threads 用戶 ID（儀表板）|

> Vercel 環境變數需另外在 Vercel Dashboard 設定（`ANTHROPIC_API_KEY`、`YOUTUBE_API_KEY`、`YOUTUBE_CHANNEL_ID` 等）

---

## 測試結果（2026-04-16）

完整管線跑通（使用現有音檔，非今日最新直播）：
- Groq Whisper 轉錄：✅ 兩頻道各 4 片段
- Claude Haiku 分析：✅
- Playwright 渲染：✅ Banner PNG + PDF（單頁 A4）
- Email 寄送：✅ 收到 dennychen0605@gmail.com

Remotion Studio 可預覽：✅（`cd video && npm start`，port 3005）

圖片生成：✅ Pexels 6+2 張（新聞×5 + opening + insight + ending）
旁白音檔：✅ Edge TTS 8 個 MP3，男聲，動態時長（`video/public/audio/`）

前端網站：✅ Vite dev server 可預覽
- 首頁：`http://localhost:5175/`
- 文章頁：`http://localhost:5175/article.html?date=20260416`

已知問題：
- Windows 關閉 PDF 前無法自動刪除（PermissionError），已加 try/except 跳過
- Nano Banana 圖片生成 free tier limit = 0，需開 Billing 才能用

---

## 下一步待辦

### 緊急修 Bug（下次對話優先）

1. **🔴 修 discord_bot.py 影片發布崩潰** ⚠️
   - `discord_bot.py:254` 呼叫不存在的 `m.step_render_video(data)`
   - 解法 A（快）：在 bot 中暫時顯示「影片渲染功能尚未完成」訊息，避免崩潰
   - 解法 B（完整）：在 `main.py` 新增 `step_render_video(data)` — 呼叫 `generate_audio.py` + `npm run render`

2. **🟡 修 Root.tsx BUFFER_FRAMES 不一致**
   - `video/src/Root.tsx:8` 將 `BUFFER_FRAMES = 60` 改為 `BUFFER_FRAMES = 90`

### 短期（下次對話繼續）

3. **網站社群連結填入** ⚠️
   - `web/index.html:333` 搜尋 `YOUR_CHANNEL_ID`，替換為實際 YouTube Channel ID
   - 同時填入 Instagram / Threads 帳號（搜尋 `YOUR_IG_HERE`、`YOUR_THREADS_HERE`）
   - Vercel 環境變數需新增 `YOUTUBE_CHANNEL_ID`

4. **個人儀表板密碼** ⚠️
   - 密碼設定在 `web/js/dashboard.js` 第 5 行附近的 `CORRECT_PASS`，上線前請確認已修改

5. **Instagram / Threads API 設定** ⚠️
   - Instagram：需 Meta Business / Creator 帳號 + Facebook Developer App → 取得 Long-lived Access Token
   - Threads：需 Meta Developer App（Threads API）→ 取得 Access Token
   - 填入 `.env` 與 Vercel 環境變數後儀表板卡片即自動啟用

6. **Oracle Cloud VM 部署** ✅（已部署，IP: `129.150.39.175`）
   - Discord Bot 已常駐，crontab 每日 09:00 自動執行

7. **直播下載測試**
   - 等有直播時跑 `python main.py --no-email --no-cleanup`
   - **注意**：`web/public/data/20260416.json` 缺少 `article`、`top5_news`、`investor_reminder` 欄位，重新跑管線會補齊

8. **Vercel 部署前端** ⚠️
   - 新增三個 Vercel 環境變數：`ANTHROPIC_API_KEY`、`YOUTUBE_API_KEY`、`YOUTUBE_CHANNEL_ID`
   - `web/` build 後推上 Vercel，vercel.json 已設 `/d` 路由

### 中期（Phase 3 剩餘）

9. **Nano Banana 圖片生成**（待開 Billing）
   - 開啟 Google Cloud Billing 後改用：
     `python generate_assets.py --type all --backend gemini`

10. **影片直式 / 橫式輸出測試**
    ```bash
    cd video
    npm run render:vertical    # out/video_vertical.mp4
    npm run render:horizontal  # out/video_horizontal.mp4
    ```

11. **場景時長微調**（依旁白實際長度）
    - 若有靜音問題，調整 `video/src/RadarVideo.tsx` 的 `BUFFER_FRAMES` 常數（目前 90）

---

## 常用指令

```bash
# 完整管線（含下載）
python main.py

# 跳過下載（用現有音檔）
python main.py --skip-download --no-email --no-cleanup

# 跳過旁白與圖片生成
python main.py --skip-download --skip-audio --no-email --no-cleanup

# 單獨生成圖片（Pexels）
python generate_assets.py --type all

# 單獨生成旁白音檔（男聲，動態時長）
python generate_audio.py

# 啟動 Remotion Studio 預覽
cd video && npm start
# 開啟 http://localhost:3005

# 渲染最終影片（直式）
cd video && npm run render

# 啟動前端 dev server
cd web && npm run dev
# 開啟 http://localhost:5173（或下一個可用 port）

# 啟動 Discord Bot
python discord_bot.py

# Oracle VM 部署（在 VM 上執行）
./setup_cron.sh
```

---

## 專案結構（當前）

```
├── main.py              # 主管線（9 步驟 + Step 3.5 新聞生成 + Step 4.5 圖片/旁白）
├── monitor.py           # Step 1：YouTube 下載（平行雙頻道）
├── transcribe.py        # Step 2：Groq + faster-whisper 轉錄
├── preprocess.py        # Step 2.5：逐字稿前處理
├── analyze.py           # Step 3：Claude 分析（含 top5_news + investor_reminder）
├── generate_article.py  # Step 3.5：Claude 轉換成新聞風格盤前速報（禁止出現頻道名/主播名）
├── database.py          # Step 4：SQLite + 靜態 JSON（同步寫入 web/public/data/）
├── generate_assets.py   # Step 4.5a：Pexels 圖片生成（自動複製封面圖到 web/public/images/）
├── generate_audio.py    # Step 4.5b：Edge TTS 旁白合成（男聲，量測真實時長→durations.json）
├── social_cards.py      # Step 5：Playwright 渲染 EDM Banner + PDF
├── discord_bot.py       # Discord Bot（Phase 2）⚠️ step_render_video() 未實作
├── config.py            # 全域設定（ENV 切換、頻道列表、Whisper 設定）
├── setup_schedule.py    # Windows 排程
├── setup_cron.sh        # Oracle VM 部署腳本
├── Dockerfile           # ARM64 容器（Python 3.12-slim + Playwright）
├── docker-compose.yml   # radar + discord-bot + web 三服務
├── templates/
│   ├── daily_report.html
│   └── edm_banner.html
├── video/               # Remotion 影片專案（Phase 3）
│   ├── src/
│   │   ├── RadarVideo.tsx       # 場景編排 + 音頻整合（BUFFER_FRAMES=90）
│   │   ├── Root.tsx             # Composition：直式 1080×1920 + 橫式 1920×1080 ⚠️ BUFFER_FRAMES=60
│   │   ├── theme.ts             # 顏色 + 字體 token
│   │   ├── types.ts             # TypeScript 介面（NewsItem, RadarData）
│   │   └── components/
│   │       ├── Opening.tsx      # 開場：品牌 + 雷達動畫 + 今日焦點
│   │       ├── NewsItem.tsx     # 新聞條目（×5）：圖片上半 + 標題下半
│   │       ├── InsightCard.tsx  # 綜合洞察：藍框觀點 + 金框提醒
│   │       └── Ending.tsx       # 結尾：品牌 + hashtag + 免責聲明
│   └── public/
│       ├── audio/               # 8 個 MP3（男聲）
│       └── *.jpg                # Pexels 圖片（news_01-05, opening_bg, insight_bg, ending_bg）
├── web/                 # 前端展示網頁（Phase 4）
│   ├── index.html       # 首頁：文章列表（三頁籤）⚠️ YOUR_CHANNEL_ID 未填
│   ├── article.html     # 文章頁：讀取 ?date=YYYYMMDD（含 AI 聊天抽屜）
│   ├── d.html           # 個人儀表板（/d，密碼保護）
│   ├── vite.config.js   # 多頁設定（3 入口）⚠️ rag_indexer.py 不存在
│   ├── vercel.json      # Vercel 部署設定（含 /d 路由 + 3 個 serverless functions）
│   ├── css/style.css    # 極簡深色主題（7 token，已提升對比度）
│   ├── css/dashboard.css # 儀表板專用樣式
│   ├── js/main.js       # 首頁邏輯
│   ├── js/article.js    # 文章頁邏輯（含 AI 聊天抽屜）
│   ├── js/dashboard.js  # 儀表板邏輯（社群統計 + 文字探勘 + AI 聊天）
│   ├── api/chat.js      # AI 聊天（文章頁，RAG + 財經問答）
│   ├── api/dashboard-chat.js  # 儀表板 AI（社群策略分析）
│   ├── api/social-stats.js    # 社群統計 API（YouTube/Instagram/Threads）
│   └── public/
│       ├── data/
│       │   ├── index.json       # 文章目錄（pipeline 後自動重建）
│       │   ├── latest.json      # 最新報告（pipeline 後自動更新）
│       │   └── YYYYMMDD.json    # 各日報告
│       └── images/
│           └── YYYYMMDD.jpg     # 文章封面圖（insight_bg.jpg 複製而來）
└── data/                # SQLite DB + 備份 JSON
```
