# 雙軌財經情報雷達 — 開發進度交接文件

> 最後更新：2026-04-20（第八次）
> 對應 PRD：PRD_v2.md

---

## 目前現況摘要

### 這次已補上的核心修正

- `yt-dlp` 不再預設強制使用 `mweb/ios/android` client，改為交給 yt-dlp 自行選擇，降低 YouTube 要求 PO Token 導致的失敗率。
- `config.py` 會自動偵測專案內 `cookies.txt`，也會自動設定 `node` 給 yt-dlp 解 JS challenge。
- 指定舊影片 URL 時，若「帶 cookies 下載失敗」，現在會自動 fallback 成「不帶 cookies 再試一次」。
- `main.py` 新增 `--video-date YYYY-MM-DD`，可正確補跑歷史日期，不會再把產出日期寫成今天。
- Discord 控制面板已新增：
  - `🗓️ 指定日期`
  - `🧹 清理全部暫存`
- VM 上的 Playwright Chromium 已補裝完成，Banner / PDF 渲染可正常執行。

### 已驗證可成功的歷史重跑案例

- 日期：`2026-04-16`
- 群益期貨：`https://www.youtube.com/watch?v=jI5eVvdjWVQ`
- 游庭皓：`https://www.youtube.com/watch?v=iUY1Ql7xFFI`
- 本機與 VM 都已成功跑完整流程，且輸出日期已確認為 `2026-04-16`。

### VM 時區與排程換算

- VM 系統時區：`UTC`
- 目前 crontab：

```bash
20 2 * * 1-5 cd ~/NTUAI_project && git pull >> ~/pipeline.log 2>&1 && docker compose run --rm radar python main.py --no-cleanup >> ~/pipeline.log 2>&1
```

- 這代表：
  - `UTC`：週一到週五 `02:20`
  - `Asia/Taipei`：週一到週五 `10:20`
  - `America/New_York`：前一天 `20:20`（夏令時間）
  - `America/Los_Angeles`：前一天 `17:20`（夏令時間）

> 結論：如果要討論「美國時間看起來是不是前一天就跑了」，答案是 **對**，因為 VM 用的是 UTC，不是台北時區。

### 目前最大的真實風險

1. 自動排程雖然會準時觸發，但不保證每天都能從 VM 直接抓到 YouTube 音訊。
2. 真正最穩的流程仍然是：
   - GitHub Actions 預抓逐字稿
   - 或 YouTube 字幕 API
   - 都失敗時才 fallback 到下載音檔
3. 若當天剛好遇到：
   - GitHub Actions 沒有逐字稿
   - 字幕 API 也失敗
   - VM 又被 YouTube 擋下載
   則自動流程仍可能失敗。
4. Groq Whisper 偶爾會撞 rate limit，雖然現在會 fallback 到本地 `faster-whisper`，但執行時間會明顯變慢。
5. `cookies.txt` 即使剛更新，也可能隨 YouTube/瀏覽器狀態再次失效，因此不能把 cookies 視為永久解法。

### 現在建議的實際操作策略

- 平日自動排程：先讓 VM 在 `10:20 Asia/Taipei` 自動跑。
- 如果 Discord / log 顯示下載失敗：
  - 本機啟動 `python local_listener.py`
  - 在 Discord 按 `🖥️ 本機下載`
  - 上傳完成後按 `⚙️ 重新分析`
- 如果要補跑歷史內容：
  - 優先使用 Discord `🗓️ 指定日期`
  - 或 CLI：`python main.py --skip-download --video-date YYYY-MM-DD`


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
| 審核 Embed 按鈕（5 個） | 📧 送出 EDM · 📰 發布新聞 · 🎬 發布影片 · ✏️ 修改建議（Modal 輸入框）· ❌ 取消 |
| 控制面板（持久化） | Bot 上線時自動發布到 DISCORD_CHANNEL_ID；含「🚀 立即執行完整流程」「📋 查看系統狀態」「🖥️ 本機下載」「⚙️ 僅重新分析」「📥 指定 URL 下載」「🗑️ 清理逐字稿」按鈕 |
| **🖥️ 本機下載** | 發出 `LOCAL_DOWNLOAD_TRIGGER` Embed，讓本機 `local_listener.py` 偵測並執行下載 |
| 進度追蹤 Embed | 管線分 5 步驟獨立執行，即時更新同一條訊息（不阻塞 Discord event loop）|
| DM 通知 | 管線失敗（含失敗步驟）或完成時自動 DM 擁有者 |
| **影片發布流程** | ✅ `_do_publish_video()` 完整重寫：渲染 → YouTube → Instagram 三步驟進度 Embed，各步獨立不互相阻擋 |

### 部署設定（完成，Oracle VM 已部署）

| 檔案 | 說明 |
|------|------|
| `Dockerfile` | ARM64 相容（Oracle VM.Standard.A1.Flex）+ Node.js 20（Remotion 渲染用） |
| `docker-compose.yml` | 管線一次性執行 + Bot 常駐 + Web 服務；含 video/out + web/public/videos volume |
| `setup_cron.sh` | SSH 進 Oracle VM 後執行，自動裝 Docker + 設 crontab + 啟動 Discord Bot |

**Oracle VM 連線資訊：**
- IP：`129.150.39.175`
- 使用者：`opc`
- SSH Key：`C:\Users\user\ssh\ssh-key-2026-04-16.key`
- 指令：`ssh -i "C:/Users/user/ssh/ssh-key-2026-04-16.key" opc@129.150.39.175`

### GitHub（完成）

- Repo：https://github.com/denny5566/NTUAI_project（Private）
- 所有 Phase 1–4 程式碼已推上去
- `.env` 已在 `.gitignore` 保護

---

### Phase 3 — Remotion 影片（完成）

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
| **BUFFER_FRAMES 修正** | ✅ | `Root.tsx` 已改為 90，與 `RadarVideo.tsx` 一致 |
| AI 圖片生成 | ⚠️ | Nano Banana（`gemini-3.1-flash-image-preview`）需開 Billing，暫用 Pexels |
| **YouTube 上傳** | ✅ | `publish_video.py`：OAuth2 refresh_token 無需瀏覽器，自動上傳橫式影片 |
| **Instagram Reels 上傳** | ✅ | `publish_video.py`：3步驟（create container → poll → publish），使用現有 IG token |
| **管線整合** | ✅ | `main.py` 新增 `step_render_video()` / `step_publish_youtube()` / `step_publish_instagram()` |

> **`NewsCard.tsx` 已刪除**，新聞場景全部改由 `NewsItem.tsx` 處理（支援5篇，含佔位漸層）。

---

### Phase 4 — 前端展示網頁

| 項目 | 狀態 | 說明 |
|------|------|------|
| 首頁 | ✅ | `web/index.html`，文章列表（按月分組），點擊進入文章頁 |
| 文章頁 | ✅ | `web/article.html`，讀取 `?date=YYYYMMDD` 顯示對應報告 |
| 股市行情 | ✅ | TradingView Ticker Tape Widget（含黃金、WTI 原油） |
| 閱讀進度條 | ✅ | 頂部紅色細線，隨捲動更新 |
| 文章封面圖 | ✅ | 底部顯示 Pexels 圖片 |
| **影片頁籤** | ✅ | YouTube Channel ID 已填入（`UCIEr1HSgijuXq6S2L1R0T9A`） |
| **頁尾** | ✅ | YouTube / Instagram / Threads 社群圖示 + 著作權聲明 |
| FAB AI 對話 | ✅ | 右下角雷達按鈕開啟側邊抽屜，串接 Claude Haiku API |
| 多頁 Vite | ✅ | `vite.config.js` 設定三入口（main/article/dashboard）|
| Vercel API | ✅ | `web/api/chat.js`、`web/api/dashboard-chat.js`、`web/api/social-stats.js` |
| 後端資料串接 | ✅ | `database.py` 每次 pipeline 後同步寫入 `web/public/data/` |
| **Oracle VM 部署** | ✅ | `http://129.150.39.175` 已上線，docker 常駐 |
| **RAG 模組缺失** | ✅ | `vite.config.js` 已移除 `rag_indexer.py` 呼叫，改為空字串 |
| Vercel 部署 | ⚠️ | 本地驗證完畢，尚未串接 Vercel |

### Phase 4+ — 個人儀表板

| 項目 | 狀態 | 說明 |
|------|------|------|
| 儀表板頁面 | ✅ | `web/d.html`，網址 `/d` |
| **密碼保護** | ✅ | `web/js/dashboard.js:10`，密碼已更新為 `radar2026` |
| YouTube 統計 | ✅ | 訂閱數/觀看數/影片數 + 頻道名稱 + 最新影片縮圖；**VM 上線驗證：回傳「財經雷達」✅** |
| Instagram 統計 | ✅ | **VM 上線驗證：@stockradar888 即時顯示 ✅**；粉絲數測試模式回傳 0（正常，需 App 審核後才有真實數字） |
| Threads 統計 | ❌ | Token 填錯（誤填 App Secret）；待重新取得正確 Token |
| 帳號名稱顯示 | ✅ | YouTube / Instagram / Threads 卡片均有 `@帳號名` 副標題 |
| 留言文字探勘 | ✅ | YouTube 自動抓取留言 + AI 分析情感傾向/熱門主題 |
| 儀表板 AI 聊天 | ✅ | 5 個範例快捷問題 |
| 社群統計 API | ✅ | `web/api/social-stats.js`（已修正 Instagram v22.0 endpoint + Threads v1.0）|
| **儀表板順序** | ✅ | ① 重要經濟行事曆 → ② 總經指標雷達 → ③ 美股&台股走勢圖 |
| **台股線圖修正** | ✅ | 移除 `container_id` 防止 TradingView 快取錯誤股票 |
| **熱門排行移除** | ✅ | TradingView hotlists 不支援 TWSE，已從儀表板刪除 |

### Phase 4++ — 行動版 RWD

| 項目 | 狀態 | 說明 |
|------|------|------|
| **字體縮放** | ✅ | `html { font-size: 16px }`，desktop 改 18px |
| **Tab 導覽列手機版** | ✅ | ≤560px 改為垂直排版（icon + 文字上下），`white-space: nowrap` |
| **圖表高度** | ✅ | 手機 ≤640px：`.chart-main { height: 300px }`、`.heat-box { height: 260px }` |
| **橫向溢位** | ✅ | `body { overflow-x: hidden }` |
| **切換 Tab 捲頂** | ✅ | `window.scrollTo({ top: 0, behavior: 'instant' })` 防止標題被 sticky nav 蓋住 |
| **Sticky nav top** | ✅ | `tab-nav { top: 92px }`（ticker 46px + header ~46px） |
| **首頁/儀表板 padding** | ✅ | 手機 `padding-top: 2rem` 防止 sticky nav 蓋到標題 |

---

### YouTube 音訊下載架構（重要）

Oracle Cloud VM 的 IP 被 YouTube 列為資料中心 IP，**即使有 cookies 也無法下載音訊**。目前採用兩種方案並行：

#### 方案 A：本機下載（已實作，可靠）

```
本機 Windows（家用 IP）→ yt-dlp 下載 MP3 → SCP 上傳 VM
```

**使用流程：**
1. 本機安裝依賴：`pip install yt-dlp requests python-dotenv`
2. 確認 `.env` 有 `DISCORD_BOT_TOKEN` 和 `DISCORD_CHANNEL_ID`
3. 啟動監聽器：`python local_listener.py`（背景執行，每 15 秒輪詢 Discord）
4. Discord 控制面板按「🖥️ 本機下載」
5. 監聽器偵測到觸發訊號（120 秒有效期），自動執行 `download_helper.py`
6. 下載完成後，Discord 回報 VM 上的檔案大小（SSH 驗證）
7. 按「⚙️ 僅重新分析（不下載）」繼續流程

**音檔存放位置：**
- 本機：`c:\Users\user\Desktop\114-2\NTUAI\NTUAI_project\output\audio\`
  - `capital_latest.mp3`（群益期貨）
  - `yu_latest.mp3`（游庭澔）
- VM：`/home/opc/NTUAI_project/output/audio/`（SCP 上傳後）

**也可直接執行：**
```bash
# 自動抓最新直播存檔
python download_helper.py

# 指定特定影片 URL
python download_helper.py --cap "https://www.youtube.com/watch?v=..." --yu "https://www.youtube.com/watch?v=..."
```

#### 方案 B：OAuth2 Device Code（實驗性，可能繞過 VM IP 封鎖）

`yt-dlp-youtube-oauth2` 插件以「智慧電視」身份認證，有機會繞過資料中心 IP 封鎖。

**VM 一次性設定：**
```bash
# 1. SSH 進 VM
ssh -i "C:/Users/user/ssh/ssh-key-2026-04-16.key" opc@129.150.39.175

# 2. 進入 discord-bot 容器
docker exec -it $(docker ps -qf name=discord-bot) bash

# 3. 執行 OAuth2 授權（任意 YouTube URL 皆可）
yt-dlp --username oauth2 --password '' "https://www.youtube.com/watch?v=jNQXAC9IVRw"
# 終端機顯示：
#   Please open https://www.google.com/device and enter code XXXX-XXXX

# 4. 用手機或電腦開啟網址，輸入 8 位數代碼，登入 Google 帳號授權

# 5. 授權成功後，token 存於 /root/.cache/yt-dlp/（docker volume ./cache 持久化）
exit
```

**啟用 OAuth2 下載（VM 上的 .env）：**
```bash
YTDLP_USE_OAUTH2=true
```
然後重建容器：`docker compose up --build -d discord-bot`

> ⚠️ 注意：OAuth2 是否能繞過 Oracle Cloud IP 封鎖尚未確認，請先試跑看看。成功後就不再需要本機下載。

---

## 已知 Bug 與待修項目

| # | 嚴重度 | 位置 | 問題說明 | 建議修法 |
|---|--------|------|----------|----------|
| 1 | 🟡 中 | `.env` Threads | `THREADS_ACCESS_TOKEN` 填的是 App Secret，`THREADS_USER_ID` 填的是 App ID；Threads 卡片「無法載入」 | 重新至 Meta Developer → threads_post App → 用戶樣板產生器 → 產生存取權杖 |
| 2 | 🟠 低 | `video/src/types.ts` | `comparison` 介面欄位名稱直接暴露頻道名（`capital_futures`、`yu_ting_hao`） | 改為 `perspective_a` / `perspective_b`（非必要，不影響執行）|
| 3 | 🟠 低 | YouTube OAuth2 | `publish_video.py` 需先跑 `python publish_video.py --auth` 一次取得 REFRESH_TOKEN | 填入 `.env` 的 `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` 後執行一次授權流程 |

---

## 環境變數狀態

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
| `YOUTUBE_CHANNEL_ID` | ✅ 已填 | 儀表板頻道統計，VM 驗證通過 |
| `YOUTUBE_CLIENT_ID` | ⚠️ 待填 | YouTube OAuth2 影片上傳用 |
| `YOUTUBE_CLIENT_SECRET` | ⚠️ 待填 | YouTube OAuth2 影片上傳用 |
| `YOUTUBE_REFRESH_TOKEN` | ⚠️ 待填 | 執行 `python publish_video.py --auth` 後取得 |
| `IG_ACCESS_TOKEN` | ✅ 已填 | Instagram Graph API v22.0，VM 驗證通過（測試模式）|
| `IG_USER_ID` | ✅ 已填 | Instagram 用戶 ID（17841429843231869）|
| `IG_VIDEO_BASE_URL` | ⚠️ 待填 | Instagram Reels 上傳用，例如 `http://129.150.39.175/videos/` |
| `THREADS_ACCESS_TOKEN` | ❌ 填錯 | 目前填的是 App Secret，需重新取得 |
| `THREADS_USER_ID` | ❌ 填錯 | 目前填的是 App ID，可清空（API 用 /me）|

> **VM 同步方式**：`scp -i "C:/Users/user/ssh/ssh-key-2026-04-16.key" .env opc@129.150.39.175:~/NTUAI_project/.env`
> 之後執行 `docker compose build web && docker compose up -d web` 重啟生效

---

## 測試結果

### 管線（2026-04-16）
- Groq Whisper 轉錄：✅ 兩頻道各 4 片段
- Claude Haiku 分析：✅
- Playwright 渲染：✅ Banner PNG + PDF（單頁 A4）
- Email 寄送：✅ 收到 dennychen0605@gmail.com

### Remotion 影片（2026-04-16）
- Studio 預覽：✅（`cd video && npm start`，port 3005）
- 圖片生成：✅ Pexels 8 張
- 旁白音檔：✅ Edge TTS 8 個 MP3，男聲

### 前端（2026-04-17，Oracle VM）
| 頁面 / 功能 | 狀態 |
|------------|------|
| 首頁 `http://129.150.39.175/` | ✅ |
| 文章頁 `/article.html?date=20260416` | ✅ |
| 儀表板 `/d` | ✅ |
| YouTube 統計 | ✅ 即時（財經雷達，1 訂閱）|
| Instagram 統計 | ✅ 即時（@stockradar888，測試模式 followers=0）|
| Threads 統計 | ❌ Token 填錯 |
| AI 聊天抽屜 | ✅ |
| 手機版 RWD | ✅ Tab 不換行、圖表正常、無橫向溢位 |

---

## 環境變數狀態（新增）

| 變數 | 狀態 | 用途 |
|------|------|------|
| `YTDLP_USE_OAUTH2` | ⚠️ 選填 | `true` = 啟用 OAuth2 Device Code 下載（需先完成互動授權）|

---

## 下一步待辦

### 緊急

1. **❌ 修 Threads Token**
   - Meta Developer → `threads_post` App → 使用案例 → 設定 → 用戶樣板產生器
   - 點 stockradar888 的「產生存取權杖」，拿到長字串填入 `.env`
   - `THREADS_USER_ID` 清空（API 自動用 /me）
   - 同步到 VM：`scp -i "C:/Users/user/ssh/ssh-key-2026-04-16.key" .env opc@129.150.39.175:~/NTUAI_project/.env`
   - 重建容器：`docker compose build web && docker compose up -d web`

2. **⚠️ 設定 YouTube OAuth2 上傳憑證**
   - Google Cloud Console → 建立 OAuth2 用戶端憑證（桌面應用程式）
   - 填入 `.env`：`YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET`
   - 本機執行：`python publish_video.py --auth` → 瀏覽器授權 → 取得 REFRESH_TOKEN → 填入 `.env`
   - 同步 `.env` 到 VM

3. **⚠️ 設定 Instagram Reels 上傳 URL**
   - 填入 `.env`：`IG_VIDEO_BASE_URL=http://129.150.39.175/videos/`
   - 確認 `web/public/videos/` 目錄存在並由 web service 提供服務

### 短期

4. **部署最新前端到 Oracle VM**（本次修改尚未部署）
   ```bash
   # 本機執行（PowerShell / Git Bash）
   scp -i "C:/Users/user/ssh/ssh-key-2026-04-16.key" web/index.html opc@129.150.39.175:~/NTUAI_project/web/index.html
   scp -i "C:/Users/user/ssh/ssh-key-2026-04-16.key" web/js/main.js opc@129.150.39.175:~/NTUAI_project/web/js/main.js
   scp -i "C:/Users/user/ssh/ssh-key-2026-04-16.key" web/css/style.css opc@129.150.39.175:~/NTUAI_project/web/css/style.css
   # VM 上重建 web 容器
   ssh -i "C:/Users/user/ssh/ssh-key-2026-04-16.key" opc@129.150.39.175 "cd ~/NTUAI_project && docker compose build web && docker compose up -d web"
   ```

5. **測試本機下載流程**
   - 確認本機已安裝 yt-dlp：`pip install yt-dlp`
   - 執行：`python local_listener.py`
   - Discord 按「🖥️ 本機下載」，確認音檔出現在 `output/audio/`

6. **（選用）測試 OAuth2 VM 下載**
   - 依上方「方案 B」步驟在 VM 授權一次
   - 設 `YTDLP_USE_OAUTH2=true`，重建容器，試跑完整流程

6. **Vercel 部署前端**
   - 新增 Vercel 環境變數：`ANTHROPIC_API_KEY`、`YOUTUBE_API_KEY`、`YOUTUBE_CHANNEL_ID`、`IG_ACCESS_TOKEN`

### 中期

7. **Nano Banana 圖片生成**（待開 Billing）
8. **影片直式 / 橫式輸出測試**（`npm run render:vertical` / `render:horizontal`）

---

## 常用指令

```bash
# ── 本機下載工具（在 Windows 本機執行）──────────────────────────
# 啟動監聽器（等 Discord 觸發）
python local_listener.py

# 直接下載兩頻道最新音檔並上傳 VM（不需要監聽器）
python download_helper.py

# 指定特定影片下載
python download_helper.py --cap "URL" --yu "URL"

# ── 完整管線（在 Oracle VM 或 Docker 內執行）─────────────────────
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

# 渲染最終影片（直式）
cd video && npm run render

# 啟動前端 dev server
cd web && npm run dev

# 啟動 Discord Bot
python discord_bot.py

# YouTube OAuth2 初始授權（只需做一次）
python publish_video.py --auth

# 手動上傳影片到 YouTube
python publish_video.py --youtube video/out/video_horizontal.mp4

# 手動上傳影片到 Instagram
python publish_video.py --instagram video/out/video_vertical.mp4

# SSH 進 Oracle VM
ssh -i "C:/Users/user/ssh/ssh-key-2026-04-16.key" opc@129.150.39.175

# 同步 .env 到 VM
scp -i "C:/Users/user/ssh/ssh-key-2026-04-16.key" .env opc@129.150.39.175:~/NTUAI_project/.env

# VM 上重建並啟動 web 容器
cd ~/NTUAI_project && docker compose build web && docker compose up -d web

# VM 上查看所有容器狀態
docker ps
```

---

## 專案結構（當前）

```
├── main.py              # 主管線（9 步驟 + Step 3.5 新聞生成 + Step 4.5 圖片/旁白 + 影片渲染/上傳）
├── monitor.py           # Step 1：YouTube 下載（平行雙頻道，支援 OAuth2）
├── local_listener.py    # 本機 Windows 用：輪詢 Discord，偵測「🖥️ 本機下載」觸發並執行 download_helper.py
├── download_helper.py   # 本機 Windows 用：用家用 IP 下載音檔，SCP 上傳至 Oracle VM
├── transcribe.py        # Step 2：Groq + faster-whisper 轉錄
├── preprocess.py        # Step 2.5：逐字稿前處理
├── analyze.py           # Step 3：Claude 分析（含 top5_news + investor_reminder）
├── generate_article.py  # Step 3.5：Claude 轉換成新聞風格盤前速報
├── database.py          # Step 4：SQLite + 靜態 JSON（同步寫入 web/public/data/）
├── generate_assets.py   # Step 4.5a：Pexels 圖片生成
├── generate_audio.py    # Step 4.5b：Edge TTS 旁白合成
├── social_cards.py      # Step 5：Playwright 渲染 EDM Banner + PDF
├── publish_video.py     # 影片發布：YouTube OAuth2 + Instagram Reels（3步驟）
├── discord_bot.py       # Discord Bot（Phase 2，影片發布流程已修正）
├── config.py            # 全域設定（含 YouTube/IG 上傳憑證）
├── setup_schedule.py    # Windows 排程
├── setup_cron.sh        # Oracle VM 部署腳本
├── Dockerfile           # ARM64 容器 + Node.js 20（Remotion 渲染）
├── docker-compose.yml   # radar + discord-bot + web 三服務（含 video volume）
├── templates/
│   ├── daily_report.html
│   └── edm_banner.html
├── video/               # Remotion 影片專案（Phase 3）
│   ├── src/
│   │   ├── RadarVideo.tsx       # 場景編排（BUFFER_FRAMES=90）
│   │   ├── Root.tsx             # 直式+橫式 Composition（BUFFER_FRAMES=90，已修正）
│   │   ├── theme.ts
│   │   ├── types.ts
│   │   └── components/
│   │       ├── Opening.tsx
│   │       ├── NewsItem.tsx     # 取代舊 NewsCard.tsx
│   │       ├── InsightCard.tsx
│   │       └── Ending.tsx
│   └── public/
│       ├── audio/               # 8 個 MP3（男聲）
│       └── *.jpg                # Pexels 圖片
├── web/                 # 前端展示網頁（Phase 4）
│   ├── index.html       # 首頁（YouTube Channel ID 已填；儀表板順序已修正）
│   ├── article.html     # 文章頁
│   ├── d.html           # 個人儀表板（/d，密碼 radar2026）
│   ├── server.js        # Oracle VM 用 Express server（取代 Vercel serverless）
│   ├── vite.config.js   # RAG 呼叫已移除
│   ├── vercel.json
│   ├── css/style.css    # RWD 手機版已修正
│   ├── css/dashboard.css
│   ├── js/main.js       # 切換 Tab 時 scrollTo(top)
│   ├── js/article.js
│   ├── js/dashboard.js  # 密碼已更新為 radar2026
│   ├── api/chat.js
│   ├── api/dashboard-chat.js
│   ├── api/social-stats.js    # 已修正 Instagram v22.0 + Threads v1.0
│   └── public/
│       ├── data/        # pipeline 自動更新
│       ├── images/      # 封面圖
│       └── videos/      # Remotion 渲染影片（供 Instagram 公開 URL）
└── data/                # SQLite DB + 備份 JSON
```
