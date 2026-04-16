# 雙軌財經情報雷達 — 開發進度交接文件

> 最後更新：2026-04-16
> 對應 PRD：PRD_v2.md

---

## 已完成項目

### Phase 1 — 本機管線（全部完成）

| 模組 | 檔案 | 說明 |
|------|------|------|
| YouTube 下載 | `monitor.py` | yt-dlp 抓兩頻道最新直播存檔 |
| 語音轉文字 | `transcribe.py` | Groq Whisper 優先，失敗 fallback faster-whisper |
| 逐字稿前處理 | `preprocess.py` | regex 清洗 + Claude Haiku 語意整理 |
| AI 分析 | `analyze.py` | Claude Haiku（dev）/ Sonnet（prod）|
| 資料庫 | `database.py` | SQLite 存檔 + 輸出靜態 JSON |
| 渲染 | `social_cards.py` | Playwright 渲染 EDM Banner（PNG）+ PDF |
| Email | `main.py` Step 6 | SMTP Gmail 寄送 |
| 主管線 | `main.py` | 完整 7 步驟，支援各種 skip 參數 |
| Windows 排程 | `setup_schedule.py` | 週一至週五定時執行 |

### Phase 2 — Discord Bot（完成）

| 功能 | 說明 |
|------|------|
| `/analyze` | 手動觸發管線 |
| `/status` | 查詢近期執行記錄 |
| `/publish` | 發布日報（Email + Discord 頻道） |
| `/revise [建議]` | 帶修改建議重新生成 |
| Embed 按鈕 | 發布 / 取消 |
| DM 通知 | 管線失敗或完成時自動 DM 擁有者 |

### 部署設定（完成，尚未上 Oracle）

| 檔案 | 說明 |
|------|------|
| `Dockerfile` | ARM64 相容（Oracle VM.Standard.A1.Flex）|
| `docker-compose.yml` | 管線一次性執行 + Bot 常駐 |
| `setup_cron.sh` | SSH 進 Oracle VM 後執行，自動裝 Docker + 設 crontab |

---

## 環境變數（`.env` 已填）

| 變數 | 狀態 |
|------|------|
| `ANTHROPIC_API_KEY` | ✅ 已填 |
| `GROQ_API_KEY` | ✅ 已填 |
| `WHISPER_MODEL` | ✅ base |
| `SMTP_*` / `EMAIL_*` | ✅ 已填（Gmail 應用程式密碼）|
| `DISCORD_BOT_TOKEN` | ✅ 已填 |
| `DISCORD_OWNER_ID` | ✅ 已填 |
| `DISCORD_CHANNEL_ID` | ✅ 已填 |

---

## 測試結果（2026-04-16）

完整管線跑通（使用現有音檔，非今日最新直播）：
- Groq Whisper 轉錄：✅ 兩頻道各 4 片段
- Claude Haiku 分析：✅
- Playwright 渲染：✅ Banner PNG + PDF（單頁 A4）
- Email 寄送：✅ 收到 dennychen0605@gmail.com

已知問題：
- Windows 關閉 PDF 前無法自動刪除（PermissionError），已加 try/except 跳過

---

## 下一步待辦

### 短期（下次對話繼續）

1. **Oracle Cloud VM 部署**
   - SSH 進 VM（Ubuntu 22.04 ARM）
   - `git clone` 專案到 VM
   - 填好 VM 上的 `.env`
   - 執行 `./setup_cron.sh`（自動裝 Docker + 設 crontab + 啟動 Discord Bot）
   - 測試：`docker compose run --rm radar python main.py --no-email --no-cleanup`

2. **直播下載問題**
   - 目前測試用的音檔不是今日最新
   - 等有直播時，直接跑 `python main.py --no-email --no-cleanup`
   - 確認 yt-dlp 能正確抓到「群益早安」和「早晨財經速解讀」關鍵字的影片

### 中期（Phase 3）

3. **Remotion 影片製作**
   - 安裝 Node.js + Remotion
   - 設計影片模板（開場 → 新聞卡片 → 數據圖表 → 結尾）
   - 整合 Nanobanana（Google AI Studio 免費 50 張/日）取得素材
   - 整合 Edge TTS（`zh-TW-HsiaoChenNeural`）合成旁白

4. **圖片素材串接**
   - 優先：Nanobanana API
   - 備援：Pexels API / Unsplash API

### 長期（Phase 4）

5. **Vercel 網站**
   - Next.js 建置
   - Oracle VM 每次產出日報後 `git push` JSON 到 GitHub
   - Vercel 自動偵測部署，網站讀取靜態 JSON 顯示歷史日報

---

## 常用指令

```bash
# 完整管線（含下載）
python main.py

# 跳過下載（用現有音檔）
python main.py --skip-download --no-email --no-cleanup

# 只重新渲染 PDF（從已存 JSON）
python -c "
import json
from social_cards import render_daily_report
data = json.loads(open('data/20260416.json', encoding='utf-8').read())
render_daily_report(data)
"

# 啟動 Discord Bot
python discord_bot.py

# Oracle VM 部署（在 VM 上執行）
./setup_cron.sh
```

---

## 專案結構（當前）

```
├── main.py              # 主管線（7 步驟）
├── monitor.py           # Step 1：YouTube 下載
├── transcribe.py        # Step 2：Groq + faster-whisper 轉錄
├── preprocess.py        # Step 2.5：逐字稿前處理
├── analyze.py           # Step 3：Claude 分析
├── database.py          # Step 4：SQLite + 靜態 JSON
├── social_cards.py      # Step 5：Playwright 渲染
├── discord_bot.py       # Discord Bot（Phase 2）
├── config.py            # 全域設定
├── setup_schedule.py    # Windows 排程
├── setup_cron.sh        # Oracle VM 部署腳本
├── Dockerfile           # ARM64 容器
├── docker-compose.yml   # 管線 + Bot 服務
├── templates/
│   ├── daily_report.html    # PDF 模板（單頁 A4）
│   └── edm_banner.html      # Banner 模板（600×300）
├── data/                # SQLite DB + 靜態 JSON（不清理）
├── output/              # 音檔、逐字稿、分析、圖片（執行後清理）
└── .env                 # API Keys（不 commit）
```
