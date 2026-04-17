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
    meta = data.get("meta", {})
    cap  = data.get("capital_futures", {})
    yu   = data.get("yu_ting_hao", {})

    embed = discord.Embed(
        title=f"📊 {meta.get('date', '今日')} 雙軌財經情報",
        description=f"**今日焦點：** {data.get('daily_focus', '—')}",
        color=0x2b5ce6,
        timestamp=datetime.now(),
    )

    cap_points = cap.get("key_points", [])
    if cap_points:
        embed.add_field(
            name=f"🔵 {cap.get('title', '群益期貨')}",
            value="\n".join(f"• {p}" for p in cap_points[:3]),
            inline=False,
        )

    yu_points = yu.get("key_points", [])
    if yu_points:
        embed.add_field(
            name=f"🟠 {yu.get('title', '游庭皓')}",
            value="\n".join(f"• {p}" for p in yu_points[:3]),
            inline=False,
        )

    insight = data.get("combined_insight", "")
    if insight:
        embed.add_field(name="💡 綜合洞察", value=insight[:300], inline=False)

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
        "⬜ 下載音訊",
        "⬜ 語音辨識 + VAD 過濾",
        "⬜ 逐字稿前處理",
        "⬜ Claude AI 分析",
        "⬜ 產出 PDF / Banner",
    ]
    if skip_download:
        steps[0] = "⏭️ 下載音訊（略過）"

    progress_msg = await interaction.followup.send(
        embed=_build_progress_embed(steps)
    )

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

    try:
        # Step 0: Download
        if not skip_download:
            await set_step(0, "🔄")
            await loop.run_in_executor(None, m.step_download)
            await set_step(0, "✅")

        # Step 1: Transcribe
        await set_step(1, "🔄")
        transcripts = await loop.run_in_executor(None, m.step_transcribe)
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
        data = await loop.run_in_executor(None, lambda: m.step_analyze(cleaned or transcripts))
        await set_step(3, "✅")

        # Step 4: Render report cards
        await set_step(4, "🔄")
        await loop.run_in_executor(None, lambda: m.step_render_cards(data))
        await set_step(4, "✅")

        # 最終狀態
        await progress_msg.edit(
            embed=_build_progress_embed(steps, title="✅ 管線執行完成", color=0x22c55e)
        )
        return data

    except Exception as e:
        log.error("管線執行失敗：%s", e, exc_info=True)
        # 標示失敗步驟
        for i, s in enumerate(steps):
            if "🔄" in s:
                await set_step(i, "❌")
        await progress_msg.edit(
            embed=_build_progress_embed(
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
    await interaction.followup.send("📤 發布日報中...")

    def _sync():
        import main as m
        banner_path, pdf_path = m.step_render_cards(data)
        m.step_send_email(data, banner_path, pdf_path)
        m.step_cleanup(banner_path, pdf_path)

    loop = asyncio.get_event_loop()
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
    """執行影片渲染流程（Remotion），完成後通知。"""
    await interaction.followup.send("🎬 影片渲染中，這可能需要幾分鐘...")

    def _sync():
        import main as m
        # step_render_video 負責 Edge TTS + Remotion 渲染
        video_path = m.step_render_video(data)
        return video_path

    loop = asyncio.get_event_loop()
    try:
        video_path = await loop.run_in_executor(None, _sync)
    except Exception as e:
        log.error("影片渲染失敗：%s", e, exc_info=True)
        await interaction.followup.send(f"❌ 影片渲染失敗：{e}")
        await _dm_owner(f"⚠️ 影片渲染失敗\n錯誤：{e}")
        return

    msg = "✅ 影片渲染完成！"
    if video_path:
        msg += f"\n📁 `{video_path}`"
    await interaction.followup.send(msg)
    await _dm_owner(f"✅ {data.get('meta', {}).get('date', '')} 影片渲染完成")


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
    """4 個審核按鈕：發布日報 / 發布影片 / 修改建議 / 取消"""

    def __init__(self):
        super().__init__(timeout=3600)  # 1 小時內有效

    @discord.ui.button(label="✅ 發布日報", style=discord.ButtonStyle.success, row=0)
    async def publish_daily_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        global _pending_data
        if _pending_data is None:
            await interaction.response.send_message("⚠️ 報告已過期，請重新 /analyze", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        data = _pending_data
        _pending_data = None
        self.stop()
        await _do_publish_daily(interaction, data)

    @discord.ui.button(label="🎬 發布影片", style=discord.ButtonStyle.primary, row=0)
    async def publish_video_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        global _pending_data
        if _pending_data is None:
            await interaction.response.send_message("⚠️ 報告已過期，請重新 /analyze", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        data = _pending_data
        await _do_publish_video(interaction, data)

    @discord.ui.button(label="✏️ 修改建議", style=discord.ButtonStyle.secondary, row=1)
    async def revise_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.send_modal(_ReviseModal())

    @discord.ui.button(label="❌ 取消", style=discord.ButtonStyle.danger, row=1)
    async def cancel_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        global _pending_data
        _pending_data = None
        await interaction.response.send_message("已取消，報告未發布。", ephemeral=True)
        self.stop()


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


def _build_control_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎛️ 雙軌財經雷達 — 控制面板",
        description=(
            "使用下方按鈕手動觸發管線，無需等待排程。\n\n"
            "**🚀 立即執行完整流程** — 下載 → 辨識 → 前處理 → 分析 → 產出\n"
            "**📋 查看系統狀態** — 顯示最近 5 筆執行記錄\n"
            "**⚙️ 僅重新分析** — 略過下載，直接對現有音訊重新分析\n\n"
            f"Bot 上線時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        ),
        color=0x4f46e5,
    )
    embed.set_footer(text="⚠️ 僅擁有者可操作 | 雙軌財經情報雷達")
    return embed


# ── 斜線指令 ──────────────────────────────────────────────────────────────────
@bot.tree.command(name="analyze", description="手動觸發分析（可指定頻道）")
@app_commands.describe(channel="capital_futures / yu_ting_hao / all（預設 all）")
async def cmd_analyze(interaction: discord.Interaction, channel: str = "all"):  # noqa: ARG001
    await interaction.response.defer(thinking=True)
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
