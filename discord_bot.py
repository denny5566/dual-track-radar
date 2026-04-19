"""
Discord Bot — 雙軌財經情報雷達控制介面（PRD v2 § 2.5）

指令：
  /analyze [channel]  手動觸發指定頻道（或全部）分析
  /status             查詢最近執行狀態
  /publish            確認發布（寄 Email + Discord 貼文）
  /revise [建議]       重新生成分析報告
  /run                強制執行完整流程（排程外觸發）

Bot 事件通知：
  - 任一步驟失敗 → DM 擁有者
  - 完成等待審核 → DM 擁有者

環境變數：
  DISCORD_BOT_TOKEN   Bot Token（必填）
  DISCORD_OWNER_ID    擁有者 User ID（必填）
  DISCORD_CHANNEL_ID  Bot 發文 + 控制面板頻道 ID（選填）
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("discord_bot")

# ── 環境變數 ──────────────────────────────────────────────────────────────────
BOT_TOKEN  = os.getenv("DISCORD_BOT_TOKEN", "")
OWNER_ID   = int(os.getenv("DISCORD_OWNER_ID", "0"))
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

if not BOT_TOKEN:
    log.error("DISCORD_BOT_TOKEN 未設定，Bot 無法啟動")
    sys.exit(1)

# ── Bot 設定 ──────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 暫存最近一次分析結果，供 /publish 使用
_pending_data: dict | None = None
# 暫存已渲染的 PDF / Banner 路徑（避免發布時重複渲染）
_pending_cards: tuple | None = None   # (banner_path, pdf_path)


# ── 工具函式 ──────────────────────────────────────────────────────────────────
async def _dm_owner(content: str) -> None:
    """發送 DM 給擁有者。"""
    try:
        owner = await bot.fetch_user(OWNER_ID)
        await owner.send(content)
    except Exception as e:
        log.warning("無法發送 DM 給擁有者：%s", e)


def _build_report_embed(data: dict) -> discord.Embed:
    """將分析 JSON 轉為 Discord Embed 預覽（PRD v2 § 7.3）。"""
    meta       = data.get("meta", {})
    comparison = data.get("comparison", {})
    cap        = comparison.get("capital_futures", {})
    yu         = comparison.get("yu_ting_hao", {})
    article    = data.get("article", {})

    # 優先顯示文章標題，否則顯示今日焦點
    if article.get("title"):
        description = f"📰 **{article['title']}**\n\n**今日焦點：** {data.get('daily_focus', '—')}"
    else:
        description = f"**今日焦點：** {data.get('daily_focus', '—')}"

    embed = discord.Embed(
        title=f"📊 {meta.get('date', '今日')} 雙軌財經情報",
        description=description,
        color=0x2b5ce6,
        timestamp=datetime.now(),
    )

    cap_points = cap.get("main_points", [])
    if cap_points:
        embed.add_field(
            name=f"🔵 {cap.get('title', '技術面觀察')}",
            value="\n".join(f"• {p}" for p in cap_points[:3]),
            inline=False,
        )

    yu_points = yu.get("main_points", [])
    if yu_points:
        embed.add_field(
            name=f"🟠 {yu.get('title', '宏觀基本面')}",
            value="\n".join(f"• {p}" for p in yu_points[:3]),
            inline=False,
        )

    clash = data.get("clash_or_sync", "")
    if clash:
        embed.add_field(name="💡 觀點統整", value=clash[:300], inline=False)

    source_videos = data.get("_source_videos", {})
    if source_videos:
        links = []
        for res in source_videos.values():
            if res.get("success") and res.get("video_url"):
                title = res.get("title", res.get("channel", ""))
                links.append(f"[{title[:45]}]({res['video_url']})")
        if links:
            embed.add_field(name="📎 來源影片", value="\n".join(links), inline=False)

    embed.set_footer(text="⚠️ 僅供參考，非投資建議 | #雙軌財經雷達 #台股")
    return embed


def _build_progress_embed(steps: list[str], title: str = "⚙️ 管線執行中", color: int = 0x4f46e5) -> discord.Embed:
    """建立步驟進度 Embed。"""
    return discord.Embed(
        title=title,
        description="\n".join(steps),
        color=color,
        timestamp=datetime.now(),
    )


# ── 核心管線（逐步進度更新）────────────────────────────────────────────────────
async def _run_pipeline_with_progress(
    interaction: discord.Interaction,
    skip_download: bool = False,
    revise_hint: str = "",
    url_overrides: dict[str, str] | None = None,
    target_date: str | None = None,
) -> dict | None:
    """
    逐步執行管線，並在同一條 Embed 訊息中即時更新進度。
    每個 step 各在獨立 executor 執行，避免阻塞 Discord event loop。
    """
    import importlib
    import main as m
    importlib.reload(m)

    loop = asyncio.get_event_loop()

    # 步驟清單（icon 開頭可動態替換）
    steps = [
        "⬜ 取得逐字稿（字幕 API / 下載音訊）",
        "⬜ 語音辨識（音檔模式時執行）",
        "⬜ 逐字稿前處理",
        "⬜ Claude AI 分析",
        "⬜ 生成新聞文章",
        "⬜ 產出 PDF / Banner",
    ]
    if skip_download:
        steps[0] = "⏭️ 取得逐字稿（略過）"

    progress_msg = await interaction.followup.send(
        embed=_build_progress_embed(steps)
    )
    _channel = interaction.channel  # 15 分鐘後 token 過期時的備用頻道

    async def set_step(idx: int, icon: str) -> None:
        """就地替換步驟圖示並編輯訊息。"""
        line = steps[idx]
        for old in ("⬜", "🔄", "✅", "❌"):
            line = line.replace(old, icon, 1)
        steps[idx] = line
        try:
            await progress_msg.edit(embed=_build_progress_embed(steps))
        except Exception:
            pass

    async def safe_final_edit(embed: discord.Embed) -> None:
        """嘗試編輯進度訊息；若 interaction token 已過期則在頻道發新訊息。"""
        try:
            await progress_msg.edit(embed=embed)
        except Exception:
            if _channel:
                await _channel.send(embed=embed)

    download_results: dict = {}

    try:
        # Step 0: 取得逐字稿（字幕 API 優先）
        if not skip_download:
            await set_step(0, "🔄")
            download_results = await loop.run_in_executor(
                None, lambda: m.step_download(url_overrides=url_overrides, target_date=target_date)
            )
            failed_chs = [k for k, v in download_results.items() if not v.get("success")]
            if failed_chs:
                await set_step(0, "❌")
                raise RuntimeError(
                    f"逐字稿取得失敗：{', '.join(failed_chs)}\n"
                    "字幕 API 不可用（影片尚未處理完畢或字幕停用），且 VM IP 被 YouTube 封鎖。\n\n"
                    "**解決方法：**\n"
                    "1️⃣ 稍等 15–30 分鐘後再試（字幕需時間生成）\n"
                    "2️⃣ 或在本機執行：`python download_helper.py` 後按「⚙️ 僅重新分析」"
                )
            await set_step(0, "✅")

        # Step 1: 語音辨識（字幕 API 成功時自動跳過）
        captions_fetched = all(
            v.get("transcript_source") in ("youtube_captions", "github_actions")
            for v in download_results.values()
        ) if download_results else False

        if captions_fetched:
            # 字幕 API 已取得逐字稿並存檔，直接跳過 Whisper
            steps[1] = steps[1].replace("⬜", "⏭️")
            await progress_msg.edit(embed=_build_progress_embed(steps))
            transcripts = {k: v.get("transcript") for k, v in download_results.items()}
        else:
            await set_step(1, "🔄")
            transcripts = await loop.run_in_executor(None, m.step_transcribe)
            empty_chs = [k for k, v in transcripts.items() if not v]
            if empty_chs:
                await set_step(1, "❌")
                raise RuntimeError(
                    f"語音辨識失敗：{', '.join(empty_chs)} 的逐字稿為空\n"
                    "可能原因：音檔損壞、音訊過短或全為靜音。"
                )
            await set_step(1, "✅")

        # Step 2: Preprocess
        await set_step(2, "🔄")
        cleaned = await loop.run_in_executor(None, lambda: m.step_preprocess(transcripts))
        await set_step(2, "✅")

        if revise_hint:
            for key in cleaned:
                if cleaned[key]:
                    cleaned[key] += f"\n\n[修改建議] {revise_hint}"

        # Step 3: Analyze
        await set_step(3, "🔄")
        # 從下載結果擷取影片日期，確保 meta.date 反映影片日期而非今天
        _video_date: str | None = target_date
        for _res in download_results.values():
            if _res.get("video_date"):
                _video_date = _res["video_date"]
                break
        data = await loop.run_in_executor(None, lambda: m.step_analyze(cleaned or transcripts, video_date=_video_date))
        if data is None:
            raise RuntimeError("Claude 分析失敗：逐字稿缺失或 API 回傳空結果，請確認音訊已下載")
        if download_results:
            data["_source_videos"] = download_results
        await set_step(3, "✅")

        # Step 4: Generate news article (新聞文章生成)
        await set_step(4, "🔄")
        try:
            from generate_article import generate_article as _gen_article
            from transcribe import load_cleaned_transcript, load_transcript
            ta_text = (
                cleaned.get("capital_futures")
                or load_cleaned_transcript("capital_futures")
                or load_transcript("capital_futures")
            )
            tb_text = (
                cleaned.get("yu_ting_hao")
                or load_cleaned_transcript("yu_ting_hao")
                or load_transcript("yu_ting_hao")
            )
            if ta_text and tb_text:
                article_result = await loop.run_in_executor(
                    None, lambda: _gen_article(ta_text, tb_text)
                )
                if article_result.get("article"):
                    data["article"] = article_result["article"]
                    log.info("[OK] 新聞文章生成成功：%s", data["article"].get("title", ""))
            else:
                log.warning("[WARN] 逐字稿不足，跳過文章生成")
        except Exception as _e:
            log.warning("文章生成失敗（不中斷流程）：%s", _e)
        await set_step(4, "✅")

        # Step 5: Render report cards
        await set_step(5, "🔄")
        banner_path, pdf_path = await loop.run_in_executor(None, lambda: m.step_render_cards(data))
        await set_step(5, "✅")

        # 儲存路徑供發布時使用（避免重複渲染）
        global _pending_cards
        _pending_cards = (banner_path, pdf_path)

        # 最終狀態
        await safe_final_edit(
            _build_progress_embed(steps, title="✅ 管線執行完成", color=0x22c55e)
        )

        # DM 傳送 PDF 預覽給擁有者
        if OWNER_ID and pdf_path:
            try:
                from pathlib import Path as _Path
                owner = await bot.fetch_user(OWNER_ID)
                await owner.send(
                    content=f"📄 **{data.get('meta', {}).get('date', '今日')} 日報已生成**\n請審核後在頻道點擊按鈕發布。",
                    file=discord.File(str(pdf_path), filename=_Path(pdf_path).name),
                )
            except Exception as e:
                log.warning("PDF DM 傳送失敗：%s", e)

        return data

    except Exception as e:
        log.error("管線執行失敗：%s", e, exc_info=True)
        # 標示失敗步驟
        for i, s in enumerate(steps):
            if "🔄" in s:
                await set_step(i, "❌")
        await safe_final_edit(
            _build_progress_embed(
                steps + [f"\n**錯誤：** {str(e)[:300]}"],
                title="❌ 管線執行失敗",
                color=0xef4444,
            )
        )
        await _dm_owner(f"⚠️ 雙軌雷達管線失敗\n步驟：{[s for s in steps if '❌' in s]}\n錯誤：{e}")
        return None


# ── 發布邏輯（共用）──────────────────────────────────────────────────────────
async def _do_publish_daily(interaction: discord.Interaction, data: dict) -> None:
    """寄 Email、在 Discord 頻道貼文、存檔、清理暫存。"""
    global _pending_cards
    await interaction.followup.send("📤 發布日報中...")

    loop = asyncio.get_event_loop()

    # 優先使用管線已渲染的路徑，避免重複渲染
    cards = _pending_cards
    _pending_cards = None

    def _sync():
        import main as m
        from pathlib import Path as _Path
        nonlocal cards
        if cards and cards[0] and _Path(str(cards[0])).exists():
            banner_path, pdf_path = cards
        else:
            banner_path, pdf_path = m.step_render_cards(data)
        m.step_send_email(data, banner_path, pdf_path)
        m.step_cleanup(banner_path, pdf_path, keep_transcripts=True)

    try:
        await loop.run_in_executor(None, _sync)
    except Exception as e:
        log.error("日報發布失敗：%s", e, exc_info=True)
        await interaction.followup.send(f"❌ 日報發布失敗：{e}")
        await _dm_owner(f"⚠️ 日報發布失敗\n錯誤：{e}")
        return

    if CHANNEL_ID:
        try:
            ch = bot.get_channel(CHANNEL_ID)
            if ch:
                await ch.send(embed=_build_report_embed(data))
        except Exception as e:
            log.warning("Discord 頻道貼文失敗：%s", e)

    await interaction.followup.send("✅ 日報發布完成！Email 已寄出，暫存檔已清理。")
    await _dm_owner(f"✅ {data.get('meta', {}).get('date', '')} 日報已發布")


async def _do_publish_video(interaction: discord.Interaction, data: dict) -> None:
    """
    執行完整影片流程：渲染（Remotion）→ 上傳 YouTube → 上傳 Instagram Reels。
    各步驟獨立報告，單一失敗不中斷後續步驟。
    """
    loop = asyncio.get_event_loop()
    date_str = data.get("meta", {}).get("date", "")

    # ── Step 1：渲染（~5~10 分鐘）────────────────────────────────────────────
    steps = [
        "⬜ 更新影片資料 + 渲染（約 5–10 分鐘）",
        "⬜ 上傳至 YouTube",
        "⬜ 上傳至 Instagram Reels",
    ]
    progress_msg = await interaction.followup.send(
        embed=_build_progress_embed(steps, title="🎬 影片發布流程")
    )

    async def set_step(idx: int, icon: str) -> None:
        line = steps[idx]
        for old in ("⬜", "🔄", "✅", "❌", "⏭️"):
            line = line.replace(old, icon, 1)
        steps[idx] = line
        try:
            await progress_msg.edit(embed=_build_progress_embed(steps, title="🎬 影片發布流程"))
        except Exception:
            pass

    # 渲染
    await set_step(0, "🔄")
    try:
        import main as m
        video_paths: dict = await loop.run_in_executor(None, lambda: m.step_render_video(data))
        await set_step(0, "✅")

        # DM Banner 預覽（影片檔案太大，以 Banner 圖代替）
        if OWNER_ID and _pending_cards and _pending_cards[0]:
            try:
                from pathlib import Path as _Path
                banner_p = _Path(str(_pending_cards[0]))
                if banner_p.exists():
                    owner = await bot.fetch_user(OWNER_ID)
                    await owner.send(
                        content=f"🎬 **{date_str} 影片已渲染完成**\n請確認 Banner 預覽，回頻道按「▶️ YouTube」或「📸 Instagram」上傳。",
                        file=discord.File(str(banner_p), filename=banner_p.name),
                    )
            except Exception as _e:
                log.warning("Banner DM 傳送失敗：%s", _e)
    except Exception as e:
        log.error("影片渲染失敗：%s", e, exc_info=True)
        await set_step(0, "❌")
        for i in [1, 2]:
            await set_step(i, "⏭️")
        await progress_msg.edit(
            embed=_build_progress_embed(
                steps + [f"\n**錯誤：** {str(e)[:300]}"],
                title="❌ 影片渲染失敗", color=0xef4444,
            )
        )
        await _dm_owner(f"⚠️ 影片渲染失敗\n錯誤：{e}")
        return

    h_path = video_paths.get("horizontal")
    v_path = video_paths.get("vertical")
    result_lines: list[str] = []

    # ── Step 2：YouTube（橫式）───────────────────────────────────────────────
    if h_path:
        await set_step(1, "🔄")
        try:
            yt_id = await loop.run_in_executor(None, lambda: m.step_publish_youtube(h_path, data))
            if yt_id:
                await set_step(1, "✅")
                result_lines.append(f"▶️ YouTube：https://www.youtube.com/watch?v={yt_id}")
                # 把 video_id 寫回 data 並更新網站資料 JSON（供影音專區嵌入）
                data["youtube_video_id"] = yt_id
                try:
                    await loop.run_in_executor(None, lambda: m.step_save_db(data))
                    log.info("[OK] youtube_video_id 已更新至網站 JSON：%s", yt_id)
                except Exception as _save_err:
                    log.warning("更新網站影片 ID 失敗：%s", _save_err)
            else:
                await set_step(1, "❌")
                result_lines.append("▶️ YouTube：上傳失敗（請檢查 OAuth2 憑證）")
        except Exception as e:
            log.error("YouTube 上傳失敗：%s", e)
            await set_step(1, "❌")
            result_lines.append(f"▶️ YouTube：❌ {str(e)[:100]}")
    else:
        await set_step(1, "⏭️")
        result_lines.append("▶️ YouTube：渲染失敗，略過")

    # ── Step 3：Instagram Reels（直式）──────────────────────────────────────
    if v_path:
        await set_step(2, "🔄")
        try:
            ig_id = await loop.run_in_executor(None, lambda: m.step_publish_instagram(v_path, data))
            if ig_id:
                await set_step(2, "✅")
                result_lines.append(f"📸 Instagram：發布成功（media_id={ig_id}）")
            else:
                await set_step(2, "❌")
                result_lines.append("📸 Instagram：上傳失敗（請檢查 IG_ACCESS_TOKEN / IG_VIDEO_BASE_URL）")
        except Exception as e:
            log.error("Instagram 上傳失敗：%s", e)
            await set_step(2, "❌")
            result_lines.append(f"📸 Instagram：❌ {str(e)[:100]}")
    else:
        await set_step(2, "⏭️")
        result_lines.append("📸 Instagram：渲染失敗，略過")

    # 最終摘要
    any_success = "✅" in steps[1] or "✅" in steps[2]
    title  = "✅ 影片發布完成" if any_success else "⚠️ 影片發布（部分失敗）"
    color  = 0x22c55e if any_success else 0xf59e0b
    await progress_msg.edit(
        embed=_build_progress_embed(steps + [""] + result_lines, title=title, color=color)
    )
    await _dm_owner(f"🎬 {date_str} 影片發布完成\n" + "\n".join(result_lines))


# ── 指定 URL 下載 Modal ───────────────────────────────────────────────────────
class _CustomUrlModal(discord.ui.Modal, title="📥 指定影片 URL"):
    cap_url = discord.ui.TextInput(
        label="群益期貨 YouTube URL（留空則下載最新）",
        style=discord.TextStyle.short,
        required=False,
        placeholder="https://www.youtube.com/watch?v=...",
        max_length=200,
    )
    yu_url = discord.ui.TextInput(
        label="游庭澔 YouTube URL（留空則下載最新）",
        style=discord.TextStyle.short,
        required=False,
        placeholder="https://www.youtube.com/watch?v=...",
        max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        global _pending_data
        await interaction.response.defer(thinking=True)

        url_overrides: dict[str, str] = {}
        if self.cap_url.value.strip():
            url_overrides["capital_futures"] = self.cap_url.value.strip()
        if self.yu_url.value.strip():
            url_overrides["yu_ting_hao"] = self.yu_url.value.strip()

        data = await _run_pipeline_with_progress(interaction, url_overrides=url_overrides or None)
        if data is None:
            return

        _pending_data = data
        embed = _build_report_embed(data)
        view = _ReviewView()
        hint = "、".join(
            f"{k}={v[32:43]}..." for k, v in url_overrides.items()
        ) if url_overrides else "（全部下載最新）"
        await interaction.followup.send(f"✅ 指定 URL 執行完成（{hint}）：", embed=embed, view=view)


class _DateRerunModal(discord.ui.Modal, title="🗓️ 指定日期重跑"):
    target_date = discord.ui.TextInput(
        label="日期（YYYY-MM-DD）",
        style=discord.TextStyle.short,
        required=True,
        placeholder="2026-04-16",
        max_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        global _pending_data
        import re as _re

        raw = self.target_date.value.strip()
        if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            await interaction.response.send_message("⚠️ 日期格式錯誤，請輸入 `YYYY-MM-DD`。", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        data = await _run_pipeline_with_progress(interaction, target_date=raw)
        if data is None:
            return

        _pending_data = data
        embed = _build_report_embed(data)
        view = _ReviewView()
        await interaction.followup.send(f"✅ {raw} 指定日期重跑完成：", embed=embed, view=view)


# ── 修改建議 Modal ────────────────────────────────────────────────────────────
class _ReviseModal(discord.ui.Modal, title="✏️ 修改建議"):
    hint = discord.ui.TextInput(
        label="請輸入修改建議",
        style=discord.TextStyle.paragraph,
        placeholder="例：請更強調科技股走勢，並加入費城半導體指數分析",
        required=True,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        global _pending_data
        await interaction.response.defer(thinking=True)

        data = await _run_pipeline_with_progress(
            interaction, skip_download=True, revise_hint=self.hint.value
        )
        if data is None:
            return

        _pending_data = data
        embed = _build_report_embed(data)
        view = _ReviewView()
        await interaction.followup.send(
            f"🔄 依建議重新生成完成（建議：{self.hint.value[:60]}{'...' if len(self.hint.value) > 60 else ''}）",
            embed=embed,
            view=view,
        )


# ── 審核按鈕 View（分析完成後顯示）──────────────────────────────────────────
class _ReviewView(discord.ui.View):
    """
    5 個審核按鈕：發布日報 / 發布至網站 / 發布影片 / 修改建議 / 取消
    使用 custom_id 設為持久化 View（bot 重啟後按鈕仍可使用）。
    _pending_data 過期時統一回覆「請重新執行」。
    """

    def __init__(self):
        super().__init__(timeout=None)  # persistent — 不超時

    @discord.ui.button(label="📧 送出 EDM", style=discord.ButtonStyle.success,
                       custom_id="review_publish_daily", row=0)
    async def publish_daily_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        global _pending_data
        if _pending_data is None:
            await interaction.response.send_message("⚠️ 報告已過期或 Bot 已重啟，請重新執行管線。", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        data = _pending_data
        _pending_data = None
        await _do_publish_daily(interaction, data)

    @discord.ui.button(label="📰 發布新聞", style=discord.ButtonStyle.primary,
                       custom_id="review_publish_web", row=0)
    async def publish_db_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        global _pending_data
        if _pending_data is None:
            await interaction.response.send_message("⚠️ 報告已過期或 Bot 已重啟，請重新執行管線。", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        data = _pending_data
        try:
            import main as m
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: m.step_save_db(data))
            await interaction.followup.send("✅ 已寫入資料庫並更新網站（`web/public/data/`）。")
            await _dm_owner(f"🗄️ {data.get('meta', {}).get('date', '')} 報告已發布至網站")
        except Exception as e:
            log.error("發布至資料庫失敗：%s", e, exc_info=True)
            await interaction.followup.send(f"❌ 發布失敗：{e}")

    @discord.ui.button(label="🎬 發布影片", style=discord.ButtonStyle.secondary,
                       custom_id="review_publish_video", row=0)
    async def publish_video_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        global _pending_data
        if _pending_data is None:
            await interaction.response.send_message("⚠️ 報告已過期或 Bot 已重啟，請重新執行管線。", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        data = _pending_data
        await _do_publish_video(interaction, data)

    @discord.ui.button(label="✏️ 修改建議", style=discord.ButtonStyle.secondary,
                       custom_id="review_revise", row=1)
    async def revise_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.send_modal(_ReviseModal())

    @discord.ui.button(label="❌ 取消", style=discord.ButtonStyle.danger,
                       custom_id="review_cancel", row=1)
    async def cancel_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        global _pending_data
        _pending_data = None
        await interaction.response.send_message("已取消，報告未發布。", ephemeral=True)


# ── 控制面板 View（持久化，排程外強制執行）────────────────────────────────────
class _ControlPanelView(discord.ui.View):
    """
    持久化控制面板（timeout=None），Bot 重啟後仍可使用。
    需在 on_ready 中呼叫 bot.add_view() 重新註冊。
    """

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🚀 立即執行完整流程",
        style=discord.ButtonStyle.success,
        custom_id="ctrl_force_run",
        row=0,
    )
    async def force_run_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        global _pending_data
        await interaction.response.defer(thinking=True)

        await interaction.followup.send(
            "🚀 **強制執行啟動**\n排程外手動觸發，開始完整管線流程...",
            ephemeral=False,
        )

        data = await _run_pipeline_with_progress(interaction)
        if data is None:
            return

        _pending_data = data
        embed = _build_report_embed(data)
        view = _ReviewView()
        await interaction.followup.send("✅ 分析完成，請確認後選擇操作：", embed=embed, view=view)
        await _dm_owner(f"✅ 強制執行完成，請至 Discord 審核 {data.get('meta', {}).get('date', '')} 日報")

    @discord.ui.button(
        label="📋 查看系統狀態",
        style=discord.ButtonStyle.secondary,
        custom_id="ctrl_status",
        row=0,
    )
    async def status_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            from database import list_reports
            reports = list_reports(limit=5)
        except Exception as e:
            await interaction.followup.send(f"❌ 無法讀取資料庫：{e}", ephemeral=True)
            return

        if not reports:
            await interaction.followup.send("📭 尚無執行記錄", ephemeral=True)
            return

        embed = discord.Embed(title="📋 近期執行記錄（最近 5 筆）", color=0x444444)
        for r in reports:
            embed.add_field(
                name=r["date"],
                value=f"env=`{r['env']}`  model=`{r['model']}`\n{r['created_at']}",
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="🖥️ 本機下載",
        style=discord.ButtonStyle.primary,
        custom_id="ctrl_local_download",
        row=1,
    )
    async def local_download_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        """發出觸發訊號，讓本機 local_listener.py 執行下載並上傳至 VM。"""
        await interaction.response.defer(thinking=False)

        trigger_embed = discord.Embed(
            title="⬇️ 本機下載請求",
            description=(
                "`local_listener.py` 偵測到此訊號後會自動下載並上傳音檔。\n\n"
                "上傳完成後請按 **「⚙️ 僅重新分析（不下載）」** 繼續流程。\n\n"
                "⚠️ 若 2 分鐘後無回應，請確認本機已執行 `python local_listener.py`"
            ),
            color=0x4f46e5,
            timestamp=datetime.now(),
        )
        trigger_embed.set_footer(text="LOCAL_DOWNLOAD_TRIGGER")
        await interaction.followup.send(embed=trigger_embed)

    @discord.ui.button(
        label="⚙️ 僅重新分析（不下載）",
        style=discord.ButtonStyle.secondary,
        custom_id="ctrl_reanalyze",
        row=1,
    )
    async def reanalyze_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        global _pending_data
        await interaction.response.defer(thinking=True)

        data = await _run_pipeline_with_progress(interaction, skip_download=True)
        if data is None:
            return

        _pending_data = data
        embed = _build_report_embed(data)
        view = _ReviewView()
        await interaction.followup.send("✅ 重新分析完成：", embed=embed, view=view)

    @discord.ui.button(
        label="📥 指定 URL 下載",
        style=discord.ButtonStyle.secondary,
        custom_id="ctrl_custom_url",
        row=2,
    )
    async def custom_url_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.send_modal(_CustomUrlModal())

    @discord.ui.button(
        label="🗓️ 指定日期重跑",
        style=discord.ButtonStyle.primary,
        custom_id="ctrl_date_rerun",
        row=2,
    )
    async def date_rerun_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.send_modal(_DateRerunModal())

    @discord.ui.button(
        label="🗑️ 清理逐字稿",
        style=discord.ButtonStyle.danger,
        custom_id="ctrl_cleanup_transcripts",
        row=3,
    )
    async def cleanup_transcripts_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            import main as m
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, m.step_cleanup_transcripts)
            await interaction.followup.send("✅ 逐字稿已清理完畢。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 清理失敗：{e}", ephemeral=True)

    @discord.ui.button(
        label="🧹 清理全部暫存",
        style=discord.ButtonStyle.danger,
        custom_id="ctrl_cleanup_all_temp",
        row=3,
    )
    async def cleanup_all_temp_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            import main as m
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, m.step_cleanup_all_temp)
            await interaction.followup.send(
                "✅ 已清理所有可重建暫存（音檔 / 逐字稿 / 分析 JSON / Banner / PDF / 影片旁白與渲染產物）。",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(f"❌ 清理失敗：{e}", ephemeral=True)


def _build_control_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎛️ 雙軌財經雷達 — 控制面板",
        description=(
            "使用下方按鈕手動觸發管線，無需等待排程。\n\n"
            "**🚀 立即執行完整流程** — VM 自動下載 → 辨識 → 分析 → 產出\n"
            "**📋 查看系統狀態** — 顯示最近 5 筆執行記錄\n"
            "**🖥️ 本機下載** — 觸發本機下載音檔並上傳 VM（需先開啟 local_listener.py）\n"
            "**⚙️ 僅重新分析（不下載）** — 用已上傳的音檔直接分析\n"
            "**📥 指定 URL 下載** — 填入 YouTube 網址下載特定影片\n"
            "**🗓️ 指定日期重跑** — 依日期搜尋兩個頻道的當日影片並重跑\n"
            "**🗑️ 清理逐字稿** — 清掉 output/transcripts/\n"
            "**🧹 清理全部暫存** — 清掉音檔、逐字稿、分析、卡片、旁白與影片暫存\n\n"
            "💡 **YouTube 被封鎖時的流程**：\n"
            "本機執行 `python local_listener.py` → 按「🖥️ 本機下載」→ 按「⚙️ 僅重新分析」\n\n"
            f"Bot 上線時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        ),
        color=0x4f46e5,
    )
    embed.set_footer(text="⚠️ 僅擁有者可操作 | 雙軌財經情報雷達")
    return embed


# ── 斜線指令 ──────────────────────────────────────────────────────────────────
@bot.tree.command(name="analyze", description="手動觸發分析（可指定頻道）")
@app_commands.describe(channel="capital_futures / yu_ting_hao / all（預設 all）")
async def cmd_analyze(interaction: discord.Interaction, channel: str = "all"):
    await interaction.response.defer(thinking=True)
    log.info("/analyze 觸發（channel=%s）", channel)
    global _pending_data

    data = await _run_pipeline_with_progress(interaction)
    if data is None:
        return

    _pending_data = data
    embed = _build_report_embed(data)
    view = _ReviewView()
    await interaction.followup.send("✅ 分析完成，請確認後選擇操作：", embed=embed, view=view)
    await _dm_owner(f"✅ 分析完成，請至 Discord 審核 {data.get('meta', {}).get('date', '')} 日報")


@bot.tree.command(name="run", description="強制執行完整管線（排程外觸發）")
async def cmd_run(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    global _pending_data

    data = await _run_pipeline_with_progress(interaction)
    if data is None:
        return

    _pending_data = data
    embed = _build_report_embed(data)
    view = _ReviewView()
    await interaction.followup.send("✅ 強制執行完成，請確認後選擇操作：", embed=embed, view=view)
    await _dm_owner(f"✅ 強制執行完成 — {data.get('meta', {}).get('date', '')}")


@bot.tree.command(name="status", description="查詢最近執行狀態")
async def cmd_status(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    try:
        from database import list_reports
        reports = list_reports(limit=5)
    except Exception as e:
        await interaction.followup.send(f"❌ 無法讀取資料庫：{e}")
        return

    if not reports:
        await interaction.followup.send("📭 尚無執行記錄")
        return

    embed = discord.Embed(title="📋 近期執行記錄", color=0x444444)
    for r in reports:
        embed.add_field(
            name=r["date"],
            value=f"env=`{r['env']}`  model=`{r['model']}`\n{r['created_at']}",
            inline=False,
        )
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="publish", description="發布待審核的日報（Email + Discord）")
async def cmd_publish(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    global _pending_data

    if _pending_data is None:
        await interaction.followup.send("⚠️ 目前沒有待發布的報告，請先執行 /analyze")
        return

    data = _pending_data
    _pending_data = None
    await _do_publish_daily(interaction, data)


@bot.tree.command(name="revise", description="提供修改建議並重新生成分析")
@app_commands.describe(hint="修改建議（例：請更強調科技股走勢）")
async def cmd_revise(interaction: discord.Interaction, hint: str):
    await interaction.response.defer(thinking=True)
    global _pending_data

    data = await _run_pipeline_with_progress(interaction, skip_download=True, revise_hint=hint)
    if data is None:
        return

    _pending_data = data
    embed = _build_report_embed(data)
    view = _ReviewView()
    await interaction.followup.send(
        f"🔄 依建議重新生成完成（建議：{hint[:60]}）",
        embed=embed,
        view=view,
    )


@bot.tree.command(name="panel", description="在此頻道重新發布控制面板")
async def cmd_panel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    view = _ControlPanelView()
    await interaction.channel.send(embed=_build_control_panel_embed(), view=view)
    await interaction.followup.send("✅ 控制面板已發布", ephemeral=True)


# ── Bot 事件 ──────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    # 重新註冊持久化 View（Bot 重啟後按鈕仍可用）
    bot.add_view(_ControlPanelView())
    bot.add_view(_ReviewView())

    await bot.tree.sync()
    log.info("Bot 已上線：%s（ID: %s）", bot.user, bot.user.id)

    # 在指定頻道發布控制面板
    if CHANNEL_ID:
        try:
            ch = bot.get_channel(CHANNEL_ID)
            if ch:
                await ch.send(embed=_build_control_panel_embed(), view=_ControlPanelView())
        except Exception as e:
            log.warning("控制面板發布失敗：%s", e)

    await _dm_owner(f"🤖 雙軌財經雷達 Bot 已上線（{datetime.now().strftime('%Y-%m-%d %H:%M')}）")


@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log.error("指令錯誤：%s", error, exc_info=True)
    msg = f"❌ 指令執行失敗：{error}"
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


# ── 啟動 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(BOT_TOKEN)
