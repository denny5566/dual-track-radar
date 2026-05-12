# 專案全面檢查報告（2026-04-21）

本次目標：針對目前專案進行「可執行性 + 可維護性」全域檢查，並列出仍受外部條件限制的項目。

## 1) 已完成的全面檢查

### A. Python 程式
- 檢查方式：`compileall`（語法層）
- 結果：`PY_COMPILE_OK`
- 補充：`main.py --help`、`publish_video.py --help` 可正常執行

### B. Web 前端（Vite）
- 檢查方式：`npm run build`（`web/`）
- 結果：成功，產出 `dist/*`

### C. Video（Remotion/TypeScript）
- 檢查方式：`npx tsc --noEmit`（`video/`）
- 結果：已修正型別錯誤後通過
- 修正檔案：
  - `video/src/RadarVideo.tsx`
  - `video/src/Root.tsx`

### D. JSON / YAML 設定檔
- JSON：逐一 `json.loads` 檢查（git tracked `.json`）
- YAML：`yaml.safe_load` 檢查（git tracked `.yml/.yaml`）
- 結果：全部通過

### E. Node/JS 語法
- 檢查方式：`node --check`（`web/server.js` + `web/api/*.js` + `web/js/*.js`）
- 結果：通過

### F. Docker Compose 組態
- 檢查方式：`docker compose config`
- 結果：語法通過
- 補充：確認 `discord-bot` 已掛載 `web/public/videos` 與 `video/out`（供 IG Reels 發布流程）

---

## 2) 本輪已修正的程式問題

### 2.1 個人儀表板「最新 YouTube 影片」破圖/版面錯位
- 症狀：`d.html` 的近期影片卡片受全站 `.video-card` 樣式污染，導致位置與尺寸異常
- 修正：在 `dashboard.css` 以 `.recent-videos-grid .video-card` 做範圍覆寫，重置會衝突的定位/動畫屬性
- 檔案：`web/css/dashboard.css`

### 2.2 影片發布流程穩定性
- 問題：Discord 長流程中 webhook token 過期，造成進度訊息編輯中斷
- 修正：加入 `safe_progress_edit()`，若 edit 失敗改用 followup 回報，避免流程整段中止
- 檔案：`discord_bot.py`

### 2.3 Instagram 發布錯誤可觀測性
- 問題：IG 發布失敗時，原本錯誤上下文不夠清楚
- 修正：在容器建立與發布階段補上 HTTP 狀態與回應 body 摘要 log
- 檔案：`publish_video.py`

### 2.4 Remotion TypeScript 型別錯誤
- 問題：`video/src/Root.tsx` 與 `RadarVideo` props 型別不相容
- 修正：明確 export props 型別，並在 Root 中集中 default props、補上安全型別轉換
- 檔案：
  - `video/src/RadarVideo.tsx`
  - `video/src/Root.tsx`

---

## 3) 目前「仍未完成」且原因清楚的項目

### 3.1 Instagram Reels 自動發布（阻塞中）
- 目前狀態：程式流程正常（渲染、複製到公開 URL、呼叫 Graph API 都有跑到）
- 實際阻塞：Meta API 回覆 `Invalid OAuth access token - Cannot parse access token (code 190)`
- 判斷：屬外部授權資產/Token 問題，不是程式邏輯錯誤
- 需要條件：
  1. 可用的 `IG_ACCESS_TOKEN`
  2. 對應正確的 `IG_USER_ID`
  3. IG 專業帳號與 FB 粉專/Business 資產綁定權限正常

---

## 4) 建議的下一步（外部條件就緒後）

1. 更新 `.env` 中 `IG_ACCESS_TOKEN`（確認可用且未過期）
2. 重啟：`docker compose up -d discord-bot radar`
3. 以 `step_publish_instagram()` 做一次實發驗證（使用現有 `video/out/video_vertical.mp4`）
4. 驗證成功後，再走 Discord 按鈕流程做 end-to-end 發布

---

## 5) 結論

- **可在本地/VM 內由程式控制的部分**：本輪已全面檢查並修正主要問題。  
- **目前唯一關鍵未完成項目**：Instagram 發布權杖與 Meta 資產權限（外部平台限制）。  
- 一旦 token/資產權限恢復，本專案發布鏈路可立即再驗證與上線。
