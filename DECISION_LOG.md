# Decision Log

## 2026-06-01 Threads 週報文案風格

- 決策：Threads 文案改為新聞媒體摘要型，參考鉅亨網 / MoneyDJ / 工商時報，不走社群 KOL 或券商投研口吻。
- 範圍：目前先套用在「每週 Shorts + Threads 週報文案」按鈕；每日 Threads 快訊另作後續功能，不混進第一版。
- 長度：250-350 字。
- 版型：分段易讀，使用「【本週市場焦點】」作為短標，避免清單式「5 個觀察變數」。
- 內容密度：每段都要帶具體事件，不只寫抽象變數或泛泛市場情緒。
- 語氣邊界：市場資訊整理，不使用買點、布局、明牌、推薦標的等投資建議語氣。
- 風險：若事件標題本身太長，需截短避免 Threads 草稿變成堆疊式清單；若要提高頻率，應另設每日快訊文案流程。

## 2026-05-31 網頁後台半操作型 YouTube 發布

- 決策：網頁後台定位為半操作型後台，不完全取代 Discord。
- 範圍：第一版只支援 Oracle VM 上的後台，不支援 Vercel 後台。
- 發布平台：第一版只做 YouTube，預設發布為 `unlisted`。
- 操作邊界：後台按鈕只發布已產生好的 `video/out/video_horizontal.mp4`，不從抓影片、分析、生成整條流程開始跑。
- 成功後處理：回寫 `youtube_video_id`，更新 SQLite / `web/public/data/latest.json` / 日期 JSON / `videos.json`。
- 原因：VM 擁有 Python、SQLite、影片檔、OAuth env 與 Remotion 產物；Vercel serverless 不適合長任務與本機檔案發布。
- 風險：後台目前仍是前端密碼門檻，若對外公開需再補 server-side auth；YouTube OAuth 失效或影片檔被清理時仍需人工修復。

## 2026-05-25 Weekly Market Shorts 作品集 Demo

- 決策：新增獨立 Weekly Shorts pipeline，不重寫既有每日日報 / EDM / 影片流程。
- 定位：作品集展示，重點是端到端 AI 自動化產品能力，而非短期追求觀看數或訂閱數。
- 影片形式：YouTube Shorts，45–60 秒，週日晚上 8 點發布節奏。
- 核心承諾：每週 60 秒，看懂 5 個牽動台股 / 美股的重大市場事件。
- 目標觀眾：有投資台股 / 美股，但沒有時間每天追財經節目的年輕投資者或研究型散戶。
- 資料來源：第一層沿用兩個 YouTube 財經頻道的既有分析；第二層直接串英文市場新聞 API 與經濟日曆 API。
- 即時性邊界：免費 API 為主，追求最近 24–72 小時新聞與下週經濟日曆，不宣稱交易級即時。
- 視覺語氣：接近網站深色金融 terminal / research card 風格，搭配 Pexels 圖片作輔助，不使用新聞 API 圖片，避免媒體照片授權風險。
- 旁白：冷靜自然的 AI 中文旁白，不露臉。
- 事件格式：每個重大事件固定為「新聞一句 + 牽動變數」，避免投資建議語氣；因事件數增至 5 個，每個事件講解深度降低。
- CTA：完整事件整理與下週經濟日曆，放在說明欄。
- 審核：Discord 顯示草稿摘要與影片路徑，第一版只支援「確認發布」。
- 發布：確認後直接發布到 YouTube `unlisted`，兼顧作品集展示與品質風險。
- 成功標準：能自動產出一支風格接近網站、語氣冷靜、包含 5 個重大市場事件、Pexels 圖片與下週關鍵事件提示的 YouTube Shorts demo。
- 風險：免費 API 可能延遲或覆蓋不足、AI 可能選題不佳、財經內容需避免被誤解為投資建議、Discord 整合增加實作成本。

## 2026-05-05 YouTube 影片發布可靠化

- 決策：第一階段先確保已生成影片能穩定發布到 YouTube。
- 原因：若發布授權與上傳鏈路不穩，影音生成品質升級無法產生實際效益。
- 暫不處理：不大改 Remotion 影音生成品質、自動化模板或視覺架構。
- 狀態紀錄：不存使用者本機，改存 VM 專案目錄的既有 Docker volume `./data/radar.db`。
- 紀錄形式：新增 SQLite `video_publish_jobs` 表，讓 Discord、CLI 與後續 dashboard 可查詢同一份發布狀態。
- 重試策略：單次 YouTube 發布最多自動重試 3 次；OAuth、檔案不存在、不可重試的 4xx、配額或權限問題直接記錄明確原因，修正後人工重跑。
- 成功指標：YouTube 發布成功率、平均嘗試次數、失敗原因可辨識率、失敗後人工重跑完成率。
- 風險：YouTube API 配額、OAuth refresh token 失效、VM 網路不穩、影片檔案路徑與 volume 掛載不一致。

## 2026-05-05 VM Cron 全自動公開發布 YouTube

- 決策：影片發布採真正全自動，VM 週一至週五 09:00 cron 主流程最後自動渲染橫式影片並直接公開發布 YouTube。
- 邊界：原本手動、本機與 Discord 流程不應被影響；全自動發布必須由 `AUTO_PUBLISH_YOUTUBE_PUBLIC=true` 或 `--auto-publish-youtube-public` 明確啟用。
- 執行點：`main.py` 在 Email 後、cleanup 前執行自動渲染與 YouTube public 上傳，確保影片檔案還沒被清理。
- 重複發布防護：若當次 data 已有 `youtube_video_id`，自動發布會跳過，避免同一份資料重複上傳。
- 風險：全自動 public 發布可能把錯誤日期、錯誤內容或品質不佳影片直接公開；目前以發布紀錄、OAuth 預檢與失敗中止降低風險，但沒有人工內容審核。
