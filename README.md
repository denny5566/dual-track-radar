# AI 雙軌財經情報雷達

自動監控兩大 YouTube 財經頻道，每日下載直播存檔、語音轉文字、Claude AI 交叉分析，產出報告圖片並寄送 Email。

## 運作流程

```
YouTube 直播存檔
    ↓ yt-dlp 下載 mp3
Whisper 語音轉文字
    ↓
Claude Opus AI 分析
    ↓
Playwright 渲染報告圖片
    ↓
Gmail 寄送（寄出後自動清除暫存檔）
```

監控頻道：
- [群益期貨觀點](https://www.youtube.com/@i-view6024/streams)
- [游庭澔的財經皓角](https://www.youtube.com/@yutinghaofinance/streams)

---

## 環境需求

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/)（yt-dlp 與 Whisper 皆需要）

---

## 安裝

```bash
git clone https://github.com/denny5566/dual-track-radar.git
cd dual-track-radar

pip install -r requirements.txt
playwright install chromium

# 複製設定檔並填入你的 API key 與 SMTP 資訊
copy .env.example .env
```

### .env 設定說明

```
ANTHROPIC_API_KEY=你的 Claude API Key
WHISPER_MODEL=base

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=你的 Gmail
SMTP_PASSWORD=Gmail 應用程式密碼
EMAIL_FROM=你的 Gmail
EMAIL_RECIPIENTS=收件人 Email
```

> Gmail 需使用「應用程式密碼」，非登入密碼。開啟方式：Google 帳戶 → 安全性 → 兩步驟驗證 → 應用程式密碼。

---

## 使用方式

### 完整執行一次

```bash
python main.py
```

### 常用參數

```bash
python main.py --skip-download    # 使用已有音檔，跳過下載
python main.py --skip-transcribe  # 使用已有逐字稿，跳過轉錄
python main.py --no-email         # 不寄信（測試用，暫存檔不會被刪除）
```

---

## 定時自動執行（Windows 工作排程器）

### 啟動排程

```bash
# 每天早上 10:00 自動執行
python setup_schedule.py --time 10:00
```

### 查看目前狀態

```bash
schtasks /query /tn "DualTrackRadar" /fo LIST
```

---

## 停止寄送

### 方法一：暫停（之後可恢復）

```bash
schtasks /change /tn "DualTrackRadar" /disable
```

恢復：

```bash
schtasks /change /tn "DualTrackRadar" /enable
```

### 方法二：永久刪除排程

```bash
schtasks /delete /tn "DualTrackRadar" /f
```

### 方法三：用 Windows 介面操作

1. 按 `Win + R`，輸入 `taskschd.msc`，按 Enter
2. 找到「DualTrackRadar」
3. 右鍵 → **停用** 或 **刪除**

### 立即手動執行一次

```bash
schtasks /run /tn "DualTrackRadar"
```

---

## 注意事項

- **電腦需要開著**，排程才能在指定時間執行。若當時電腦是關機或睡眠，該次會跳過。
- `.env` 已加入 `.gitignore`，不會上傳到 GitHub。
- 寄信成功後，音檔、逐字稿、圖片會自動刪除。

---

## 專案結構

```
├── main.py            # 主管線
├── monitor.py         # Step 1：YouTube 下載
├── transcribe.py      # Step 2：Whisper 轉錄
├── analyze.py         # Step 3：Claude 分析
├── social_cards.py    # Step 4：圖片生成
├── setup_schedule.py  # Windows 排程設定
├── config.py          # 全域設定
├── templates/
│   └── daily_report.html
├── .env.example       # 設定範本
└── requirements.txt
```
