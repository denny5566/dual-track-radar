"""
AI 雙軌財經情報雷達 — 主管線（PRD v2）
執行順序：
  1. 監控並下載今日雙頻道音檔（ThreadPoolExecutor）
  2. faster-whisper 轉錄（含 VAD 過濾 + pydub 切片）
  2.5 逐字稿前處理（regex 清洗 + Claude Haiku 語意整理）
  3. Claude 分析，產出結構化 JSON
  4. SQLite 存檔 + 輸出靜態 JSON（供 Vercel 讀取）
  5. Playwright 渲染 EDM Banner + PDF 報告
  6. 寄送 Email
  7. 清理暫存檔案（音檔、逐字稿、Banner、PDF）

用法：
  python main.py                          # 完整流程（含寄信）
  python main.py --skip-download          # 跳過下載（使用已有音檔）
  python main.py --skip-download --video-date 2026-04-16
  python main.py --skip-transcribe        # 跳過轉錄（使用已有逐字稿）
  python main.py --skip-preprocess        # 跳過前處理（直接送原始逐字稿）
  python main.py --skip-cards             # 跳過圖片生成
  python main.py --no-email              # 不寄信
  python main.py --no-cleanup            # 保留暫存檔案（debug 用）
"""

from __future__ import annotations

import argparse
import logging
import smtplib
import sys
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from config import (
    ANALYSIS_DIR,
    AUDIO_DIR,
    BASE_DIR,
    CARDS_DIR,
    CLAUDE_MODEL,
    EMAIL_FROM,
    EMAIL_RECIPIENTS,
    ENV,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
    TRANSCRIPT_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ── Step 1 ──────────────────────────────────────────────────────────────────
def step_download(
    url_overrides: dict[str, str] | None = None,
    target_date: str | None = None,
) -> dict:
    """
    Step 1：取得逐字稿。

    策略優先順序：
      1. GitHub Actions 預取（data/transcripts/，每日 07:00 由 GA 自動擷取並 git commit）
         → Oracle VM git pull 後立即可用，完全不需 VM 碰 YouTube
      2. youtube-transcript-api 字幕 API（VM 直接呼叫，游庭澔頻道通常可用）
      3. yt-dlp 音檔下載 Fallback（本機可用，VM 上被封鎖）
    """
    import datetime
    from config import CHANNELS as _CHANNELS

    log.info(
        "=== Step 1：取得逐字稿（GA 預取 → 字幕 API → yt-dlp，url_overrides=%s, target_date=%s）===",
        url_overrides, target_date,
    )

    # ── 優先：GitHub Actions 預取逐字稿 ──────────────────────────────────────
    # GA 每天 07:00 AM 在 GitHub runner（非封鎖 IP）擷取，git commit 至 data/transcripts/
    # VM 端 docker-compose 掛載 ./data:/app/data，git pull 後容器直接可見
    if not url_overrides and not target_date:  # 指定 URL / 日期時跳過 GA，確保取到指定資料
        ga_dir = BASE_DIR / "data" / "transcripts"
        date_file = ga_dir / "fetch_date.txt"
        today_str = datetime.date.today().isoformat()

        if date_file.exists() and date_file.read_text(encoding="utf-8").strip() == today_str:
            ga_results: dict = {}
            for key in _CHANNELS:
                txt_path = ga_dir / f"{key}.txt"
                if txt_path.exists():
                    text = txt_path.read_text(encoding="utf-8").strip()
                    if text:
                        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
                        (TRANSCRIPT_DIR / f"{key}.txt").write_text(text, encoding="utf-8")
                        ga_results[key] = {
                            "channel": key,
                            "success": True,
                            "transcript": text,
                            "transcript_source": "github_actions",
                            "audio_path": None,
                            "video_url": None,
                            "title": None,
                            "video_date": None,
                        }
                        log.info("[GA] %s：%d 字", key, len(text))

            if len(ga_results) == len(_CHANNELS):
                log.info("✅ 所有頻道已由 GitHub Actions 預取，跳過 API 呼叫")
                return ga_results

            log.warning("⚠️ GitHub Actions 逐字稿不完整（%d/%d），繼續 API 擷取",
                        len(ga_results), len(_CHANNELS))
        else:
            log.info("GitHub Actions 今日逐字稿尚未就緒（fetch_date=%s），繼續 API 擷取",
                     date_file.read_text(encoding="utf-8").strip() if date_file.exists() else "無")

    # ── 字幕 API（主要方式）──────────────────────────────────────────────────
    try:
        from transcript_monitor import run_dual_transcript_monitor
        results = run_dual_transcript_monitor(url_overrides=url_overrides, target_date=target_date)
        failed = [k for k, v in results.items() if not v.get("success")]

        if not failed:
            # 全部成功，直接回傳（跳過 yt-dlp）
            for key, res in results.items():
                log.info("[OK] %s：%d 字（來源：字幕 API）",
                         key, len(res.get("transcript") or ""))
            return results

        log.warning("字幕 API 部分失敗（%s），嘗試 yt-dlp fallback", failed)

    except Exception as e:
        log.warning("字幕 API 不可用（%s），回退到 yt-dlp", e)
        results = {}
        failed = list(__import__("config").CHANNELS.keys())

    # ── yt-dlp Fallback（本機執行可用；VM 上通常被封鎖）────────────────────
    try:
        from monitor import run_dual_monitor
        audio_results = run_dual_monitor(url_overrides=url_overrides, target_date=target_date)
        for key in failed:
            if audio_results.get(key, {}).get("success"):
                results[key] = audio_results[key]
                log.info("[OK] %s：yt-dlp 下載成功", key)
            else:
                results.setdefault(key, audio_results.get(key, {
                    "channel": key, "success": False, "audio_path": None,
                }))
                log.info("[FAIL] %s：無音檔（VM IP 被封鎖，請用本機下載）", key)
    except Exception as e:
        log.error("yt-dlp fallback 失敗：%s", e)

    for key, res in results.items():
        icon = "[OK]" if res.get("success") else "[FAIL]"
        source = res.get("transcript_source", "audio")
        log.info("%s %s: %s（來源：%s）", icon, key,
                 res.get("title") or res.get("audio_path") or "無", source)
    return results


# ── Step 2 ──────────────────────────────────────────────────────────────────
def step_transcribe() -> dict[str, str | None]:
    from transcribe import transcribe_both
    log.info("=== Step 2：faster-whisper 語音轉文字（含 VAD 過濾） ===")
    transcripts = transcribe_both()
    for key, text in transcripts.items():
        chars = len(text) if text else 0
        icon = "[OK]" if text else "[FAIL]"
        log.info("%s %s：%d 字", icon, key, chars)
    return transcripts


# ── Step 2.5 ────────────────────────────────────────────────────────────────
def step_preprocess(transcripts: dict[str, str | None]) -> dict[str, str | None]:
    from preprocess import preprocess_both
    log.info("=== Step 2.5：逐字稿前處理（regex + Claude Haiku） ===")
    cleaned = preprocess_both(transcripts, use_haiku=True)
    for key, text in cleaned.items():
        chars = len(text) if text else 0
        icon = "[OK]" if text else "[FAIL]"
        log.info("%s %s 清洗後：%d 字", icon, key, chars)
    return cleaned


# ── Step 3 ──────────────────────────────────────────────────────────────────
def step_analyze(transcripts: dict[str, str | None], video_date: str | None = None) -> dict | None:
    from transcribe import load_cleaned_transcript, load_transcript
    from analyze import analyze

    log.info("=== Step 3：Claude 雙軌分析（model=%s, env=%s, video_date=%s） ===", CLAUDE_MODEL, ENV, video_date or "今日")

    # 優先使用前處理後的清洗版；若無則 fallback 原始逐字稿
    ta = (transcripts.get("capital_futures")
          or load_cleaned_transcript("capital_futures")
          or load_transcript("capital_futures"))
    tb = (transcripts.get("yu_ting_hao")
          or load_cleaned_transcript("yu_ting_hao")
          or load_transcript("yu_ting_hao"))

    if not ta and not tb:
        log.error("[FAIL] 兩個頻道均無逐字稿，無法進行分析")
        return None

    # 單頻道模式：一個頻道缺席時，用提示語告知 Claude
    if not ta:
        log.warning("[WARN] 群益期貨逐字稿缺失，使用單頻道模式（僅游庭澔）")
        ta = "（本日群益期貨觀點逐字稿無法取得，請以游庭澔財經皓角的內容為主進行分析，雙軌比較欄位可標注「資料不足」）"
    if not tb:
        log.warning("[WARN] 游庭澔逐字稿缺失，使用單頻道模式（僅群益期貨）")
        tb = "（本日游庭澔財經皓角逐字稿無法取得，請以群益期貨觀點的內容為主進行分析，雙軌比較欄位可標注「資料不足」）"

    data = analyze(ta, tb, today=video_date)
    log.info("[OK] 分析完成（日期：%s）：%s", data.get("meta", {}).get("date", "?"), data.get("daily_focus", ""))
    return data


# ── Step 4 ──────────────────────────────────────────────────────────────────
def step_save_db(data: dict) -> None:
    from database import export_json_for_github, save_report
    log.info("=== Step 4：SQLite 存檔 + 靜態 JSON 輸出 ===")
    save_report(data)
    json_path = export_json_for_github(data, BASE_DIR)
    log.info("[OK] 靜態 JSON 已輸出（可推送至 GitHub）：%s", json_path)


# ── Step 4.5 ─────────────────────────────────────────────────────────────────
def step_generate_video_assets(data: dict) -> None:
    """更新 Remotion 資料檔 + 生成旁白音檔。"""
    import json
    from generate_audio import run as generate_audio

    log.info("=== Step 4.5：更新影片資料 + 生成 Edge TTS 旁白 ===")

    # 更新 video/src/data/sample.json（供 Remotion 讀取最新分析結果）
    video_data_path = BASE_DIR / "video" / "src" / "data" / "sample.json"
    if video_data_path.exists():
        import json as _json
        existing = _json.loads(video_data_path.read_text(encoding="utf-8"))
        # 保留原有 image_url（圖片不隨每次分析重置）
        existing_urls = {
            item.get("headline", ""): item.get("image_url")
            for item in existing.get("top5_news", [])
        }
        news = []
        for i, item in enumerate(data.get("top5_news", [])[:5]):
            news.append({
                "headline":  item.get("headline", ""),
                "summary":   item.get("summary", ""),
                "image_url": existing_urls.get(item.get("headline", ""),
                             f"news_{i+1:02d}.jpg"),
            })
        merged = {**data, "top5_news": news}
        video_data_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.info("[OK] video/src/data/sample.json 已更新")

    # 生成旁白音檔
    generate_audio(data)
    log.info("[OK] 旁白音檔已生成至 video/public/audio/")

    # 生成場景配圖（依當日文字向 Pexels 搜尋）
    from generate_assets import run as generate_assets
    generate_assets(data, backend="pexels")
    log.info("[OK] 場景配圖已生成至 video/public/")


# ── Step 5 ──────────────────────────────────────────────────────────────────
def step_render_cards(data: dict) -> tuple[Path, Path]:
    from social_cards import render_daily_report
    log.info("=== Step 5：Playwright 渲染 EDM Banner 與 PDF 報告 ===")
    banner_path, pdf_path = render_daily_report(data)
    log.info("[OK] EDM Banner：%s", banner_path)
    log.info("[OK] PDF 報告：%s", pdf_path)
    return banner_path, pdf_path


# ── Step 6 ──────────────────────────────────────────────────────────────────
def step_send_email(data: dict, banner_path: Path, pdf_path: Path) -> None:
    log.info("=== Step 6：寄送每日報告 Email ===")

    subject = data.get("outputs", {}).get("edm_subject", "【雙軌雷達】今日財經情報")
    recipients = [r.strip() for r in EMAIL_RECIPIENTS if r.strip()]

    if not recipients:
        log.warning("未設定收件人（EMAIL_RECIPIENTS），跳過寄信")
        return

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(recipients)

    # HTML 本文內嵌 banner 圖片
    related = MIMEMultipart("related")
    html_body = """\
    <html><body style="margin:0;padding:20px;background:#0d0d0d;">
    <img src="cid:edm_banner"
         style="display:block;max-width:600px;width:100%;margin:0 auto;border-radius:4px;">
    </body></html>
    """
    related.attach(MIMEText(html_body, "html", "utf-8"))

    with open(banner_path, "rb") as f:
        img = MIMEImage(f.read())
        img.add_header("Content-ID", "<edm_banner>")
        img.add_header("Content-Disposition", "inline", filename=banner_path.name)
        related.attach(img)

    msg.attach(related)

    # PDF 附件
    with open(pdf_path, "rb") as f:
        pdf = MIMEApplication(f.read(), _subtype="pdf")
        pdf.add_header("Content-Disposition", "attachment", filename=pdf_path.name)
        msg.attach(pdf)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, recipients, msg.as_string())

    log.info("[OK] Email 已寄出至 %d 位收件人", len(recipients))


# ── Step 5.5：影片渲染（Remotion）────────────────────────────────────────────
def step_render_video(data: dict) -> dict[str, Path | None]:
    """
    呼叫 Remotion CLI 渲染影片。
    回傳 {"horizontal": Path | None, "vertical": Path | None}
      horizontal → 1920×1080（YouTube）
      vertical   → 1080×1920（Instagram Reels）
    """
    import subprocess

    log.info("=== Step 5.5：Remotion 影片渲染 ===")

    # 渲染前先更新 sample.json + 旁白音檔 + 場景圖片
    step_generate_video_assets(data)

    video_dir = BASE_DIR / "video"
    out_dir   = video_dir / "out"
    out_dir.mkdir(exist_ok=True)

    results: dict[str, Path | None] = {"horizontal": None, "vertical": None}

    tasks = [
        ("horizontal", "RadarVideoHorizontal", out_dir / "video_horizontal.mp4"),
        ("vertical",   "RadarVideo",           out_dir / "video_vertical.mp4"),
    ]

    for key, composition, out_file in tasks:
        log.info("[Remotion] 渲染 %s (%s)...", key, composition)
        cmd = ["npx", "remotion", "render", composition, str(out_file)]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(video_dir),
                capture_output=True,
                text=True,
                timeout=600,   # 最多等 10 分鐘
            )
            if proc.returncode == 0:
                log.info("[OK] %s 影片已渲染：%s", key, out_file)
                results[key] = out_file
            else:
                log.error("[FAIL] %s 渲染失敗：%s", key, proc.stderr[-500:])
        except subprocess.TimeoutExpired:
            log.error("[FAIL] %s 渲染逾時（10 分鐘）", key)
        except FileNotFoundError:
            log.error("[FAIL] 找不到 npx，請確認 Node.js 已安裝並在 PATH 中")
            break

    return results


# ── Step 6.5：發布至 YouTube / Instagram ─────────────────────────────────────
def step_publish_youtube(video_path: Path, data: dict) -> str | None:
    """
    上傳 video_path 至 YouTube，回傳 video_id。
    """
    from publish_video import upload_to_youtube

    log.info("=== Step 6.5a：上傳影片至 YouTube ===")
    date_str = data.get("meta", {}).get("date", "")
    focus    = data.get("daily_focus", "")
    title    = f"【財經雷達】{date_str} {focus}"[:100]
    desc_lines = [
        focus,
        "",
        "── 今日重點 ──",
    ]
    for item in data.get("top5_news", [])[:5]:
        desc_lines.append(f"• {item.get('headline', '')}")
    desc_lines += [
        "",
        "⚠️ 本影片僅供參考，非投資建議",
        "#財經雷達 #台股 #StockRadar",
    ]
    description = "\n".join(desc_lines)

    video_id = upload_to_youtube(video_path, title=title, description=description)
    if video_id:
        log.info("[OK] YouTube 影片：https://www.youtube.com/watch?v=%s", video_id)
    return video_id


def step_publish_instagram(video_path: Path, data: dict) -> str | None:
    """
    上傳 video_path 至 Instagram Reels，回傳 media_id。
    """
    from publish_video import upload_to_instagram

    log.info("=== Step 6.5b：上傳 Reels 至 Instagram ===")
    date_str = data.get("meta", {}).get("date", "")
    focus    = data.get("daily_focus", "")
    news_tags = " ".join(
        f"#{item.get('headline', '')[:8].replace(' ', '')}"
        for item in data.get("top5_news", [])[:3]
        if item.get("headline")
    )
    caption = (
        f"【財經雷達】{date_str}\n"
        f"{focus}\n\n"
        f"#財經雷達 #台股 #StockRadar #盤前分析 {news_tags}"
    )[:2200]   # IG 說明上限 2200 字

    media_id = upload_to_instagram(video_path, caption=caption)
    if media_id:
        log.info("[OK] Instagram Reels 發布完成：media_id=%s", media_id)
    return media_id


# ── Step 7 ──────────────────────────────────────────────────────────────────
def step_cleanup(
    banner_path: Path | None,
    pdf_path: Path | None,
    keep_transcripts: bool = False,
) -> None:
    """
    清理暫存檔案（PRD v2 § 4.3）：
    刪除音檔、逐字稿（原始 + 清洗後）、分析 JSON、Banner 與 PDF。
    只保留：SQLite 資料庫、靜態 JSON（data/）、執行 log。

    keep_transcripts=True 時跳過 TRANSCRIPT_DIR，保留逐字稿至當天手動清除。
    """
    log.info("=== Step 7：清理暫存檔案（keep_transcripts=%s）===", keep_transcripts)
    removed = 0

    dirs_to_clean = [AUDIO_DIR, ANALYSIS_DIR]
    if not keep_transcripts:
        dirs_to_clean.append(TRANSCRIPT_DIR)

    for directory in dirs_to_clean:
        for f in directory.glob("*"):
            if f.is_file():
                f.unlink()
                log.info("已刪除：%s", f.name)
                removed += 1

    for path in (banner_path, pdf_path):
        if path and path.exists():
            try:
                path.unlink()
                log.info("已刪除：%s", path.name)
                removed += 1
            except PermissionError:
                log.warning("檔案被佔用，跳過刪除：%s（請手動關閉後刪除）", path.name)

    log.info("清理完成，共刪除 %d 個檔案", removed)


def step_cleanup_transcripts() -> None:
    """單獨清理逐字稿目錄（當天結束後手動觸發）。"""
    log.info("=== 清理逐字稿 ===")
    removed = 0
    for f in TRANSCRIPT_DIR.glob("*"):
        if f.is_file():
            f.unlink()
            log.info("已刪除：%s", f.name)
            removed += 1
    log.info("逐字稿清理完成，共刪除 %d 個檔案", removed)


def step_cleanup_outputs() -> None:
    """清理 output 內的音檔、逐字稿、分析 JSON、卡片。"""
    log.info("=== 清理 output 暫存 ===")
    removed = 0
    for directory in (AUDIO_DIR, TRANSCRIPT_DIR, ANALYSIS_DIR, CARDS_DIR):
        if not directory.exists():
            continue
        for f in directory.glob("*"):
            if f.is_file():
                f.unlink()
                log.info("已刪除：%s", f)
                removed += 1
    log.info("output 暫存清理完成，共刪除 %d 個檔案", removed)


def step_cleanup_media_assets() -> None:
    """清理影片渲染與旁白等可重建資產，不動資料庫與網站 JSON。"""
    log.info("=== 清理影片 / 媒體暫存 ===")
    removed = 0
    media_patterns = {
        BASE_DIR / "video" / "public" / "audio": ["*.mp3"],
        BASE_DIR / "video" / "public": ["opening_bg.jpg", "insight_bg.jpg", "ending_bg.jpg", "news_*.jpg"],
        BASE_DIR / "video" / "out": ["*"],
        BASE_DIR / "web" / "public" / "videos": ["*"],
    }
    for directory, patterns in media_patterns.items():
        if not directory.exists():
            continue
        for pattern in patterns:
            for f in directory.glob(pattern):
                if f.is_file():
                    f.unlink()
                    log.info("已刪除：%s", f)
                    removed += 1
    log.info("影片 / 媒體暫存清理完成，共刪除 %d 個檔案", removed)


def step_cleanup_all_temp() -> None:
    """清理所有可重建暫存，不動資料庫與網站靜態 JSON。"""
    step_cleanup_outputs()
    step_cleanup_media_assets()


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="AI 雙軌財經情報雷達管線")
    parser.add_argument("--skip-download",    action="store_true", help="跳過音檔下載")
    parser.add_argument("--skip-transcribe",  action="store_true", help="跳過語音轉文字")
    parser.add_argument("--skip-preprocess",  action="store_true", help="跳過逐字稿前處理")
    parser.add_argument("--skip-article",     action="store_true", help="跳過文章生成")
    parser.add_argument("--skip-cards",       action="store_true", help="跳過圖片生成")
    parser.add_argument("--skip-audio",       action="store_true", help="跳過旁白音檔生成")
    parser.add_argument("--no-email",         action="store_true", help="不寄送 Email")
    parser.add_argument("--no-cleanup",       action="store_true", help="保留暫存檔案（debug）")
    parser.add_argument("--video-date",       help="指定分析日期（YYYY-MM-DD），供 skip-download / 指定舊片測試使用")
    args = parser.parse_args()

    log.info("=== 雙軌財經情報雷達啟動 ===  env=%s  model=%s", ENV, CLAUDE_MODEL)

    # Step 1
    video_date: str | None = args.video_date
    if not args.skip_download:
        download_results = step_download(target_date=args.video_date)
        # 從下載結果擷取影片日期（優先群益，其次游庭澔）
        for res in download_results.values():
            if res.get("video_date"):
                video_date = res["video_date"]
                break

    # Step 2
    transcripts: dict[str, str | None] = {}
    if not args.skip_transcribe:
        transcripts = step_transcribe()

    # Step 2.5
    cleaned_transcripts: dict[str, str | None] = {}
    if not args.skip_preprocess:
        cleaned_transcripts = step_preprocess(transcripts)

    data = step_analyze(cleaned_transcripts or transcripts, video_date=video_date)
    if data is None:
        log.error("管線中止：分析失敗")
        sys.exit(1)

    # Step 3.5
    if not args.skip_article:
        log.info("=== Step 3.5：生成新聞風格文章 ===")
        from generate_article import generate_article
        from transcribe import load_cleaned_transcript, load_transcript
        
        ta = ((cleaned_transcripts.get("capital_futures") or transcripts.get("capital_futures"))
              or load_cleaned_transcript("capital_futures") or load_transcript("capital_futures"))
        tb = ((cleaned_transcripts.get("yu_ting_hao") or transcripts.get("yu_ting_hao"))
              or load_cleaned_transcript("yu_ting_hao") or load_transcript("yu_ting_hao"))
              
        if ta and tb:
            article_data = generate_article(ta, tb)
            if "article" in article_data:
                data["article"] = article_data["article"]
                log.info("[OK] 新聞文章生成成功")
            else:
                log.warning("[WARN] 新聞文章生成未返回預期格式")
        else:
             log.warning("[WARN] 缺少逐字稿，跳過文章生成")

    # Step 4
    step_save_db(data)

    # Step 4.5
    if not args.skip_audio:
        step_generate_video_assets(data)

    # Step 5
    banner_path: Path | None = None
    pdf_path: Path | None = None
    if not args.skip_cards:
        banner_path, pdf_path = step_render_cards(data)

    # Step 6
    if not args.no_email and banner_path and pdf_path:
        step_send_email(data, banner_path, pdf_path)

    # Step 7（無論是否寄信，都執行清理）
    if not args.no_cleanup:
        step_cleanup(banner_path, pdf_path)

    log.info("=== 管線完成 ===")


if __name__ == "__main__":
    main()
