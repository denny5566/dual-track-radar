"""
AI 雙軌財經情報雷達 — 主管線
執行順序：
  1. 監控並下載今日雙頻道音檔（ThreadPoolExecutor）
  2. Whisper 轉錄為逐字稿
  3. Claude Opus 交叉分析，產出 JSON
  4. Playwright 渲染每日報告圖片（YYYYMMDD.png）
  5. 寄送圖片 Email

用法：
  python main.py                        # 完整流程（含寄信）
  python main.py --skip-download        # 跳過下載（使用已有音檔）
  python main.py --skip-transcribe      # 跳過轉錄（使用已有逐字稿）
  python main.py --skip-cards           # 跳過圖片生成
  python main.py --no-email             # 不寄信
"""

from __future__ import annotations

import argparse
import logging
import smtplib
import sys
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from config import (
    EMAIL_FROM,
    EMAIL_RECIPIENTS,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ── Step 1 ──────────────────────────────────────────────────────────────────
def step_download() -> dict:
    from monitor import run_dual_monitor
    log.info("=== Step 1：監控並下載音檔 ===")
    results = run_dual_monitor()
    for key, res in results.items():
        icon = "✅" if res["success"] else "❌"
        log.info("%s %s: %s", icon, key, res.get("audio_path") or "無音檔")
    return results


# ── Step 2 ──────────────────────────────────────────────────────────────────
def step_transcribe() -> dict[str, str | None]:
    from transcribe import transcribe_both
    log.info("=== Step 2：Whisper 語音轉文字 ===")
    transcripts = transcribe_both()
    for key, text in transcripts.items():
        chars = len(text) if text else 0
        icon = "✅" if text else "❌"
        log.info("%s %s：%d 字", icon, key, chars)
    return transcripts


# ── Step 3 ──────────────────────────────────────────────────────────────────
def step_analyze(transcripts: dict[str, str | None]) -> dict | None:
    from transcribe import load_transcript
    from analyze import analyze

    log.info("=== Step 3：Claude 雙軌分析 ===")

    ta = transcripts.get("capital_futures") or load_transcript("capital_futures")
    tb = transcripts.get("yu_ting_hao") or load_transcript("yu_ting_hao")

    if not ta or not tb:
        log.error("❌ 逐字稿缺失，無法進行分析")
        return None

    data = analyze(ta, tb)
    log.info("✅ 分析完成：%s", data.get("daily_focus", ""))
    return data


# ── Step 4 ──────────────────────────────────────────────────────────────────
def step_render_cards(data: dict) -> Path:
    from social_cards import render_daily_report
    log.info("=== Step 4：Playwright 渲染每日報告圖片 ===")
    path = render_daily_report(data)
    log.info("✅ 報告圖片：%s", path)
    return path


# ── Step 5 ──────────────────────────────────────────────────────────────────
def step_send_email(data: dict, img_path: Path) -> None:
    log.info("=== Step 5：寄送每日報告 Email ===")

    subject = data.get("outputs", {}).get("edm_subject", "【雙軌雷達】今日財經情報")
    recipients = [r.strip() for r in EMAIL_RECIPIENTS if r.strip()]

    if not recipients:
        log.warning("未設定收件人（EMAIL_RECIPIENTS），跳過寄信")
        return

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(recipients)

    html_body = f"""
    <html><body style="margin:0;padding:20px;background:#f0f0f0;">
    <img src="cid:daily_report"
         style="display:block;max-width:680px;width:100%;margin:0 auto;border-radius:4px;">
    </body></html>
    """
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with open(img_path, "rb") as f:
        img = MIMEImage(f.read())
        img.add_header("Content-ID", "<daily_report>")
        img.add_header("Content-Disposition", "inline", filename=img_path.name)
        msg.attach(img)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, recipients, msg.as_string())

    log.info("✅ Email 已寄出至 %d 位收件人", len(recipients))


# ── Step 6 ──────────────────────────────────────────────────────────────────
def step_cleanup(img_path: Path | None) -> None:
    """刪除音檔、逐字稿、分析 JSON、報告圖片，釋放磁碟空間。"""
    from config import AUDIO_DIR, TRANSCRIPT_DIR, ANALYSIS_DIR

    log.info("=== Step 6：清理暫存檔案 ===")
    removed = 0

    for directory in (AUDIO_DIR, TRANSCRIPT_DIR, ANALYSIS_DIR):
        for f in directory.glob("*"):
            if f.is_file():
                f.unlink()
                log.info("已刪除：%s", f.name)
                removed += 1

    if img_path and img_path.exists():
        img_path.unlink()
        log.info("已刪除：%s", img_path.name)
        removed += 1

    log.info("清理完成，共刪除 %d 個檔案", removed)


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="AI 雙軌財經情報雷達管線")
    parser.add_argument("--skip-download",   action="store_true", help="跳過音檔下載")
    parser.add_argument("--skip-transcribe", action="store_true", help="跳過語音轉文字")
    parser.add_argument("--skip-cards",      action="store_true", help="跳過圖片生成")
    parser.add_argument("--no-email",        action="store_true", help="不寄送 Email")
    args = parser.parse_args()

    # Step 1
    if not args.skip_download:
        step_download()

    # Step 2
    transcripts: dict[str, str | None] = {}
    if not args.skip_transcribe:
        transcripts = step_transcribe()

    # Step 3
    data = step_analyze(transcripts)
    if data is None:
        log.error("管線中止：分析失敗")
        sys.exit(1)

    # Step 4
    img_path: Path | None = None
    if not args.skip_cards:
        img_path = step_render_cards(data)

    # Step 5
    if not args.no_email and img_path:
        step_send_email(data, img_path)
        step_cleanup(img_path)

    log.info("=== 管線完成 ===")


if __name__ == "__main__":
    main()
