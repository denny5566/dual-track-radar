# 財經新聞追蹤日報系統 PRD
> 資訊 hub 及 remotion 二合一專案｜規格書 v2

| 欄位 | 內容 |
|------|------|
| 文件版本 | v2.0 |
| 建立日期 | 2026 年 4 月 15 日 |
| 更新日期 | 2026 年 4 月 16 日 |
| 專案性質 | 個人自動化專案 |
| 主要技術 | Python / Docker / Oracle Cloud |
| 費用目標 | 每月 USD$5 以內（Claude API 費用為主，其餘使用免費服務） |

---

## 變更紀錄

| 版本 | 日期 | 變更內容 |
|------|------|----------|
| v1.0 | 2026-04-15 | 初版建立 |
| v2.0 | 2026-04-16 | 新增 VAD 靜音過濾、逐字稿前處理流程、Nanobanana 素材優先順序調整、Haiku 測試環境設定、Vercel 定位釐清、Oracle VM 資料庫定位說明 |

---

## 1. 專案概述

### 1.1 背景與目標

本專案旨在建立一套完全自動化的財經新聞追蹤與推播系統，定期擷取 YouTube 財經直播（群益期貨、游庭皓甚至國內外頻道）的音訊內容，透過 AI 語音辨識與文字分析，自動產出財金日報（PDF + EDM）及財經快報影片，並透過 Discord Bot 進行審核與多平台發布。

### 1.2 核心價值主張

- 每日自動化產出財金摘要，無需人工介入
- 輸出分支：文字日報（PDF/EDM）+ 短影片（Remotion）+ 網站更新（Vercel）
- Discord 作為統一控制介面，支援手動觸發與審核互動
- 整體架構費用目標：Claude API 費用（其餘使用免費服務）

### 1.3 使用者

| 角色 | 說明 |
|------|------|
| 主要使用者 | 我（透過 Discord 操作） |
| 內容受眾 | 財金日報訂閱者（Email）、瀏覽網站者 |
| 影片平台受眾 | YouTube / Instagram 追蹤者 |

---

## 2. 功能需求

### 2.1 直播內容擷取

- 使用 YouTube Data API v3 每小時（暫定）排程查詢指定頻道的新直播或存檔
- 支援多頻道監控（群益期貨、游庭皓，未來可擴充）
- 發現新直播時，透過 Discord 通知並自動觸發後續流程
- 使用 yt-dlp 下載音訊（mp3 格式），並用 pydub 切割為 10 分鐘片段

### 2.2 語音轉文字

- 呼叫 faster-whisper（本地）或 Groq Whisper API（雲端）進行語音辨識
- **送 Whisper 前先執行 Silero VAD 過濾**：移除靜音與無人聲片段，避免 Whisper 在空白音訊產生幻覺文字；faster-whisper 直接啟用 `vad_filter=True` 參數即可
- 指定語言為繁體中文（`language=zh`）以提升辨識準確率（後續若關注國外直播須修改）
- 逐字稿分段儲存，保留時間戳記供後續參考

### 2.2.5 逐字稿前處理（送 LLM 前必做）

財經直播逐字稿常有大量中英夾雜、語助詞、口頭禪等雜訊，直接送 Claude 會增加 token 用量並降低摘要品質。流程如下：

**步驟一：清除雜訊**
- 移除語助詞（啊、欸、那個、就是說）
- 移除過長停頓標記與重複片段
- 移除無意義填充詞

**步驟二：術語標準化**
- 統一常見財經術語格式（例：SP500 / S&P500 / 標普 500 → 統一格式）
- 統一數字表達（例：三萬七 → 37,000）

**步驟三：完成後送 Claude 分析**

> 實作方式：優先用 Python regex 處理基本清洗；複雜語意整理可用 Claude Haiku（成本低）做第一層整理後再交 Sonnet 深度分析。

### 2.3 AI 分析（日報分支）

- 呼叫 Claude Sonnet API 對逐字稿進行重點摘要
- 輸出結構：5 條市場重點、今日關鍵數據、操作建議（不報明牌，內容客觀為主）
- 同步產出 EDM Banner（HTML）與 PDF 報告
- 寄送後（或發布至平台留底後）自動刪除音檔、逐字稿、EDM 及 PDF（節省儲存空間）

### 2.4 影片製作（影片分支）

Claude 從逐字稿萃取 3–5 個關鍵字後，依以下優先順序取得素材：

**素材取得優先順序：**

| 順序 | 來源 | 說明 | 費用 |
|------|------|------|------|
| 1 | Nanobanana（Google AI Studio 免費額度） | 風格一致的 AI 生成圖，每日 50 張免費 | $0 |
| 2 | Pexels API / Unsplash API | 真實照片，免費商業授權 | $0 |
| 3 | Nanobanana 付費 API | 免費額度用完的備援 | ~$0.03/張 |
| 4 | Replicate（Flux Schnell） | 最後備援 | 有免費額度 |

> Nanobanana 優先的理由：可控制固定圖片風格，讓每支影片視覺一致；免費額度（50 張/日）對本專案用量完全足夠。正式發布需使用付費 API 取得無浮水印圖片。

- 呼叫 Edge TTS（`zh-TW-HsiaoChenNeural`）合成旁白語音
- 使用 Remotion 渲染影片：開場動畫 → 新聞卡片 → 數據圖表 → 結尾
- 影片規格：1080×1920（直式）或 1920×1080（橫式），長度 60–180 秒

### 2.5 Discord Bot 審核流程（暫定）

| 指令 | 說明 | Bot 回應 |
|------|------|----------|
| `/analyze [頻道]` | 手動觸發指定頻道分析 | 分析進度通知 + 完成後 Embed 預覽 |
| `/status` | 查詢目前排程狀態 | 顯示上次執行時間與結果 |
| `/publish` | 確認發布所有輸出 | 依序發送至各平台 |
| `/revise [建議]` | 要求重新生成 | 重新送 Claude 分析後重新渲染 |

> 審核 Embed 包含：摘要預覽、影片縮圖、按鈕（發布 / 修改建議 / 取消）
> 可能再加入社群圖文，但本專案以影片為優先

---

## 3. 技術架構

### 3.1 主機環境

| 項目 | 內容 |
|------|------|
| 主機平台 | Oracle Cloud VM（永久免費雲端機器，非本機） |
| 機器規格 | VM.Standard.A1.Flex — 4 OCPU / 24 GB RAM / ARM 架構 |
| 作業系統 | Ubuntu 22.04 LTS |
| 容器化 | Docker（確保環境一致性） |
| 排程機制 | Linux crontab（系統層） |
| 資料庫 | SQLite（存於 Oracle VM，輕量免安裝，足夠個人用量） |
| 網站展示 | Vercel（永久免費，靜態部署） |
| 程式碼管理 | GitHub（免費，Vercel 自動串接） |

> **Oracle VM 與 Vercel 分工說明：**
> Oracle VM 是 24 小時運作的雲端機器，負責所有重工作（下載、Whisper、Claude 分析、渲染、Discord Bot 常駐）。每次產出日報後，自動將摘要 JSON 推送至 GitHub repo，Vercel 網站讀取靜態 JSON 顯示內容，兩者不需要即時連線，架構簡單且安全。
>
> **為何不用 Supabase：** 本專案為個人用量，Oracle VM 上的 SQLite 即可滿足需求，無需額外引入外部資料庫服務。
>
> **Vercel Cron 限制（不適合本專案主流程）：** Vercel 免費方案 Cron Job 每天只能觸發一次，且函式最長執行 60 秒，無法處理 Whisper 等長時工作，因此主流程排程仍由 Oracle VM crontab 負責。

### 3.2 技術選型總覽

| 模組 | 工具 | 選型理由 |
|------|------|----------|
| 音訊下載 | yt-dlp | 開源免費，支援 YouTube 存檔 |
| 音訊切割 | pydub | 輕量，ARM 相容性佳 |
| 靜音過濾 | Silero VAD | 防止 Whisper 幻覺，faster-whisper 內建支援 |
| 語音轉文字 | faster-whisper（本地） | 音檔不離機，隱私保障，24GB RAM 足夠 |
| 備援語音辨識 | Groq Whisper API | 2000 次/日免費，速度快 |
| 逐字稿清洗 | Python regex + Claude Haiku | 低成本前處理，提升 LLM 輸入品質 |
| 文字分析 | Claude Sonnet API | 繁中理解佳，結構化輸出穩定 |
| 影片渲染 | Remotion（Node.js） | 程式化影片生成，可版控 |
| 語音合成 | Edge TTS | 完全免費，zh-TW 聲音品質佳 |
| 圖片素材（優先） | Nanobanana（Gemini Flash） | 風格一致，免費額度 50 張/日 |
| 圖片素材（備援） | Pexels API / Unsplash API | 免費商業授權真實照片 |
| AI 圖像備援 | Replicate（Flux Schnell） | 有免費額度 |
| Discord Bot | discord.py | Python 生態，維護活躍 |
| 郵件發送 | Gmail API | 免費，支援 HTML EDM |
| 資料庫 | SQLite（on Oracle VM） | 輕量，個人用量足夠，無需外部服務 |
| 網站展示 | Vercel + Next.js | 永久免費，讀取 GitHub 靜態 JSON |

### 3.3 測試環境設定

開發測試期間為節省 API 費用，透過環境變數自動切換模型：

```bash
# .env 設定
ENV=dev    # 測試環境：使用 Claude Haiku
ENV=prod   # 正式環境：使用 Claude Sonnet
```

```python
# 程式碼邏輯
import os
model = "claude-haiku-4-5" if os.getenv("ENV") == "dev" else "claude-sonnet-4-6"
```

> Haiku 費用約為 Sonnet 的 1/10，適合開發測試階段頻繁呼叫。

---

## 4. 資料流程

### 4.1 日報分支流程

| 步驟 | 輸入 | 輸出 | 執行位置 |
|------|------|------|----------|
| 1. 觸發 | Cron 排程 / Discord 指令 | 啟動訊號 | Oracle VM |
| 2. 下載 | YouTube 頻道 URL | mp3 音檔 | Oracle VM |
| 3. 切片 | mp3 音檔 | 10 分鐘片段 × N | Oracle VM |
| 4. VAD 過濾 | 音訊片段 | 有人聲的片段 | Oracle VM（Silero VAD） |
| 5. 轉文字 | 過濾後音訊 | 逐字稿 txt | Oracle VM（faster-whisper） |
| 6. 前處理 | 逐字稿 txt | 清洗後文字 | Oracle VM（regex + Haiku） |
| 7. 分析 | 清洗後逐字稿 | 摘要 JSON | Claude Sonnet API |
| 8. 產出 | 摘要 JSON | PDF + EDM HTML | Oracle VM |
| 9. 存檔 | 摘要 JSON | 寫入 SQLite + 推送 GitHub | Oracle VM |
| 10. 審核 | PDF + EDM 預覽 | 發布確認 | Discord Bot |
| 11. 發送 | PDF + EDM | 寄出 Email + Discord | Oracle VM |
| 12. 清除 | 音檔、切片、逐字稿、EDM、PDF | （已刪除） | Oracle VM |

### 4.2 網站更新流程

```
Oracle VM 產出摘要 JSON
→ git push 到 GitHub repo（/data/YYYYMMDD.json）
→ Vercel 自動偵測更新重新部署
→ Next.js 網站讀取靜態 JSON 顯示日報
```

### 4.3 暫存檔案管理

- 工作目錄：`/home/ubuntu/jobs/{date}/`
- 執行完成後自動清除：音檔、切片、逐字稿、EDM、PDF
- 只保留：摘要 JSON（寫入 SQLite + 推送 GitHub）、執行 log
- Log 保留 30 天後自動輪替

### 4.4 錯誤處理

- 每個步驟設定 retry 機制（最多 3 次，指數退避）
- 任何步驟失敗時，透過 Discord DM 通知擁有者
- 通知內容包含：失敗步驟、錯誤訊息、建議操作

---

## 5. 非功能需求

### 5.1 時間限制

| 項目 | 時間 |
|------|------|
| 每日日報完成時間 | 觸發時間 09:30 |
| 每週影片完成時間 | 每週一 08:00 前（觸發時間週日 22:00），發布頻率待確認 |
| Discord 審核等待 | 等待擁有者操作，無超時限制 |
| 單次完整流程上限 | 2 小時（含 VAD + Whisper + 前處理 + Claude + 渲染） |

### 5.2 費用限制

| 服務 | 方案 | 費用 | 備案 |
|------|------|------|------|
| Oracle Cloud VM | Always Free | $0 永久 | 無需備案 |
| Groq Whisper API | Free Tier | $0（2000 次/日） | 切換 faster-whisper |
| Claude Sonnet API | Pay-as-you-go | ~$1–3/月估計 | 降低 max_tokens |
| Claude Haiku API | Pay-as-you-go | ~$0.1–0.3/月（測試 + 前處理用） | — |
| Nanobanana | Google AI Studio 免費額度 | $0（50 張/日） | 切換付費 API $0.03/張 |
| Pexels / Unsplash | Free API | $0 | 換用另一家 |
| Edge TTS | 免費開源 | $0 | 換用 Kokoro TTS |
| Vercel | Hobby 方案 | $0 永久 | 換用 GitHub Pages |
| GitHub | Free 方案 | $0 永久 | 無需備案 |
| SQLite（on VM） | 內建 | $0 永久 | 無需備案 |

---

## 6. 外部依賴與 API 管理

### 6.1 API 清單

| API | 用途 | 免費額度 | Key 存放位置 |
|-----|------|----------|--------------|
| YouTube Data API v3 | 查詢直播 | 10,000 單位/日 | Oracle VM 環境變數 |
| Groq API | Whisper 語音辨識 | 2,000 次/日 | Oracle VM 環境變數 |
| Claude API (Anthropic) | 逐字稿前處理（Haiku）+ 分析（Sonnet） | 按用量計費 | Oracle VM 環境變數 |
| Nanobanana API | AI 圖像生成（風格一致） | 50 張/日（Google AI Studio） | Oracle VM 環境變數 |
| Pexels API | 影片素材搜尋 | 200 次/時 | Oracle VM 環境變數 |
| Unsplash API | 影片素材搜尋 | 50 次/時（Demo） | Oracle VM 環境變數 |
| Replicate API | AI 圖像生成（備援） | 有免費額度 | Oracle VM 環境變數 |
| Gmail API | 寄送日報 Email | 免費 | Oracle VM 環境變數 |
| Discord Bot Token | Bot 操作權限 | 免費 | Oracle VM 環境變數 |

### 6.2 環境變數管理規範

- 所有 API Key 一律存放於 Oracle VM 的 `/etc/environment` 或 `.env` 檔
- `.env` 不得提交至 GitHub（加入 `.gitignore`）
- Docker 透過 `--env-file` 注入環境變數，不寫死於 Dockerfile
- 每季定期輪替 API Key 並更新文件
- `ENV` 變數控制模型切換（`dev` = Haiku，`prod` = Sonnet）

---

## 7. 輸出規格

### 7.1 日報規格

#### PDF

| 項目 | 規格 |
|------|------|
| 頁面尺寸 | A4（210 × 297 mm），margin 全部為 0 |
| 規範 | 內容不可超過一頁 A4、最多列到 5 點 |
| 檔案命名 | `financial-daily-YYYYMMDD.pdf` |

**固定欄位：**
- Header：品牌名「雙軌財經情報雷達」＋主旨標題＋日期
- Today's Focus：深黑底（`#111`），當日焦點一句話
- 雙欄對比：來源 A（群益期貨）vs 來源 B（游庭皓）並排
  - 來源 A：標題、情緒標籤、關鍵點位、核心觀點、操作策略
  - 來源 B：標題、情緒標籤、總經指標、核心觀點、操作策略
- 綜合洞察：兩來源比較結論
- Footer：`#雙軌財經雷達 #台股 #投資分析`＋「僅供參考，非投資建議」

**字型 fallback 順序：**
`Helvetica Neue` → `Arial` → `Noto Sans TC` → `PingFang TC` → `sans-serif`

**色系：**

| 用途 | 色碼 |
|------|------|
| 背景 | `#f8f7f4`（米白） |
| 深色區塊（Focus 背景） | `#111` |
| 主文字 | `#1a1a1a` / `#111` |
| 次要文字 | `#444` / `#666` |
| 標註文字（label） | `#aaa` / `#bbb` / `#ccc` |
| 來源 A 識別色（法人藍） | `#2b5ce6`（config: `#1a56db`） |
| 來源 B 識別色（名家橘） | `#e67e2b`（config: `#d97706`） |
| 多方標籤 | 底 `#e8f5ee`，字 `#1a6637` |
| 空方標籤 | 底 `#fce8e8`，字 `#8b1a1a` |
| 中性標籤 | 底 `#f0ede8`，字 `#666` |

#### EDM Banner

| 項目 | 規格 |
|------|------|
| 尺寸 | 600 × 300 px（PNG） |
| 背景色 | `#111`（深黑） |
| 檔案命名 | `YYYYMMDD_banner.png` |

**固定欄位：**
- Topbar：品牌名「雙軌財經情報雷達」＋日期
- Hero：標籤「Daily Briefing」＋當日 EDM 主旨標題
- Footer：今日焦點摘要（截斷）＋「詳細分析見附件」

**字型 fallback 順序：**
`Helvetica Neue` → `Arial` → `Noto Sans TC` → `PingFang TC` → `sans-serif`

### 7.2 影片規格

| 項目 | 規格 |
|------|------|
| 解析度 | 1080×1920（直式，IG/TikTok）或 1920×1080（橫式，YouTube） |
| 長度 | 60–180 秒 |
| 幀率 | 30fps |
| 字幕 | 自動生成，白色字幕帶黑色描邊 |
| 聲音 | Edge TTS 旁白 + 輕音樂（CC0 授權） |
| 檔案命名 | `financial-reel-YYYYMMDD.mp4` |

### 7.3 Discord Embed 格式

- 標題：當日日期 + 頻道名稱
- 內文：5 條重點摘要（最多 200 字）
- 縮圖：EDM Banner 預覽圖
- 按鈕列：發布日報 ／ 發布影片 ／ 修改建議 ／ 取消

---

## 8. 開發里程碑

| 階段 | 目標 | 主要工作項目 |
|------|------|-------------|
| Phase 1 | 基礎流程：日報自動化 | Oracle VM 設定、Docker 環境建立、yt-dlp + Silero VAD + faster-whisper、逐字稿前處理、Claude API 分析、Gmail 寄送 |
| Phase 2 | Discord 控制：Discord Bot 審核 | discord.py Bot 架設、指令系統（`/analyze` `/publish`）、Embed + Button 互動、錯誤通知機制 |
| Phase 3 | 影片製作：Remotion 影片輸出 | Remotion 模板設計、Nanobanana 圖片生成整合、Edge TTS 語音合成、影片自動上傳 YouTube |
| Phase 4 | 網站展示：日報存檔上線 | Vercel + Next.js 建置、Oracle VM 自動推送 JSON 至 GitHub、歷史日報查詢介面 |

---

## 9. 架構圖

```
觸發層
├── YouTube API（每小時排程查新直播）
├── Cron Job（Oracle VM 定時排程）
└── Discord 指令（手動觸發 /analyze）
        ↓
Oracle Cloud VM（永久免費雲端機器）— 主要工作區
├── yt-dlp 下載 → pydub 切片（10分鐘段）
│       ↓
├── Silero VAD 靜音過濾（vad_filter=True）
│       ↓
├── faster-whisper 語音轉文字
│       ↓
├── 逐字稿前處理（regex 清洗 + Haiku 整理）
│       ↓
├── Claude Sonnet 分析
│       ↓ 分支
│   日報分支                        影片分支
│   EDM Banner + PDF 報告           素材取得（Nanobanana → Pexels）
│                                   Edge TTS 語音合成
│                                   Remotion 影片渲染
│       ↓                               ↓
├── SQLite 存檔 + JSON 推送 GitHub
│       ↓
└── Discord Bot 審核（發布 / 修改建議 / 重新生成）
        ↓
輸出層
├── Gmail 寄送（EDM + PDF）
├── Discord 發文（社群自動推播）
├── YouTube / IG（影片自動發布）
└── Vercel 網站（讀取 GitHub JSON 顯示日報）

外部免費 API
├── Nanobanana（Google AI Studio，50張/日免費）
├── Pexels API / Unsplash API
├── Edge TTS
└── GitHub（程式碼 + 日報 JSON 存放）
```

---

## 10. 參考資料

1. 自動化剪輯經驗分享：https://cloud.tencent.com/developer/article/2624103
2. Groq Whisper API：https://console.groq.com/docs/speech-to-text
3. Discord 操作 Claude：https://blog.ray-realms.com/yong-discord-cao-kong-ni-de-claudecode-wan-zheng-jiao-xue/
4. Remotion Lab：https://remotionlab.com/
5. Silero VAD：https://github.com/snakers4/silero-vad
6. Nanobanana API：https://nanobananaapi.ai/
7. 其他可能可參考：https://github.com/public-apis/public-apis
