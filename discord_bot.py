"""
Discord Bot — 雙軌財經情報雷達控制介面（PRD v2 § 2.5）

指令：
  /analyze [channel]  手動觸發指定頻道（或全部）分析
  /status             查詢最近執行狀態
  /publish            確認發布（寄 Email + Discord 貼文）
  /revise [建議]       重新生成分析報告

Bot 也會在以下事件主動 DM 擁有者：
  - 管線任一步驟失敗
  - 管線完成等待審核

環境變數：
  DISCORD_BOT_TOKEN   Bot Token（必填）
  DISCORD_OWNER_ID    擁有者 User ID（必填，接收 DM 通知）
  DISCORD_CHANNEL_ID  Bot 發文用頻道 ID（選填）
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

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

# ── 環境變數 ─────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.getenv("DISCORD_BOT_TOKEN", "")
OWNER_ID     = int(os.getenv("DISCORD_OWNER_ID", "0"))
CHANNEL_ID   = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

if not BOT_TOKEN:
    log.error("DISCORD_BOT_TOKEN 未設定，Bot 無法啟動")
    sys.exit(1)

# ── Bot 設定 ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 暫存最近一次分析結果，供 /publish 使用
_pending_data: dict | None = None


# ── 工具函式 ─────────────────────────────────────────────────────────────────
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
    outputs = data.get("outputs", {})
    cap = data.get("capital_futures", {})
    yu = data.get("yu_ting_hao", {})

    embed = discord.Embed(
        title=f"📊 {meta.get('date', '今日')} 雙軌財經情報",
        description=f"**今日焦點：** {data.get('daily_focus', '—')}",
        color=0x2b5ce6,
        timestamp=datetime.now(),
    )

    # 群益期貨摘要
    cap_points = cap.get("key_points", [])
    if cap_points:
        embed.add_field(
            name=f"🔵 {cap.get('title', '群益期貨')}",
            value="\n".join(f"• {p}" for p in cap_points[:3]),
            inline=False,
        )

    # 游庭皓摘要
    yu_points = yu.get("key_points", [])
    if yu_points:
        embed.add_field(
            name=f"🟠 {yu.get('title', '游庭皓')}",
            value="\n".join(f"• {p}" for p in yu_points[:3]),
            inline=False,
        )

    # 綜合洞察
    insight = data.get("combined_insight", "")
    if insight:
        embed.add_field(name="💡 綜合洞察", value=insight[:300], inline=False)

    embed.set_footer(text="⚠️ 僅供參考，非投資建議 | #雙軌財經雷達 #台股")
    return embed


async def _run_pipeline_async(
    interaction: discord.Interaction,
    skip_download: bool = False,
    revise_hint: str = "",
) -> dict | None:
    """在 asyncio executor 中執行同步管線，避免阻塞 Bot。"""
    await interaction.followup.send("⏳ 管線啟動中，請稍候...")

    def _run():
        import importlib
        import main as m

        # 動態重新載入以確保最新狀態
        importlib.reload(m)

        results = {}
        if not skip_download:
            results["download"] = m.step_download()

        transcripts = m.step_transcribe()
        cleaned = m.step_preprocess(transcripts)

        # 若有修改建議，附加到逐字稿後再送分析
        if revise_hint:
            for key in cleaned:
                if cleaned[key]:
                    cleaned[key] = cleaned[key] + f"\n\n[修改建議] {revise_hint}"

        data = m.step_analyze(cleaned or transcripts)
        return data

    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, _run)
        return data
    except Exception as e:
        log.error("管線執行失敗：%s", e, exc_info=True)
        await interaction.followup.send(f"❌ 管線失敗：{e}")
        await _dm_owner(f"⚠️ 雙軌雷達管線失敗\n錯誤：{e}")
        return None


# ── 斜線指令 ─────────────────────────────────────────────────────────────────
@bot.tree.command(name="analyze", description="手動觸發分析（可指定頻道）")
@app_commands.describe(channel="capital_futures / yu_ting_hao / all（預設 all）")
async def cmd_analyze(interaction: discord.Interaction, channel: str = "all"):
    await interaction.response.defer(thinking=True)
    global _pending_data

    data = await _run_pipeline_async(interaction)
    if data is None:
        return

    _pending_data = data

    embed = _build_report_embed(data)
    view = _ReviewView()
    await interaction.followup.send(
        "✅ 分析完成，請確認後選擇操作：",
        embed=embed,
        view=view,
    )
    await _dm_owner(f"✅ 分析完成，請至 Discord 審核並發布 {data.get('meta', {}).get('date', '')} 日報")


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
            value=f"env={r['env']}  model={r['model']}\n{r['created_at']}",
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

    await _do_publish(interaction, _pending_data)
    _pending_data = None


@bot.tree.command(name="revise", description="提供修改建議並重新生成分析")
@app_commands.describe(hint="修改建議（例：請更強調科技股走勢）")
async def cmd_revise(interaction: discord.Interaction, hint: str):
    await interaction.response.defer(thinking=True)
    global _pending_data

    data = await _run_pipeline_async(interaction, skip_download=True, revise_hint=hint)
    if data is None:
        return

    _pending_data = data
    embed = _build_report_embed(data)
    view = _ReviewView()
    await interaction.followup.send(
        f"🔄 依建議重新生成完成（建議：{hint[:50]}）",
        embed=embed,
        view=view,
    )


# ── 發布邏輯（共用於 /publish 和 Embed 按鈕）──────────────────────────────
async def _do_publish(interaction: discord.Interaction, data: dict) -> None:
    """寄 Email、在 Discord 頻道貼文、存檔、清理暫存。"""
    await interaction.followup.send("📤 發布中...")

    def _publish_sync():
        import main as m
        from config import CARDS_DIR

        banner_path, pdf_path = m.step_render_cards(data)
        m.step_send_email(data, banner_path, pdf_path)
        m.step_cleanup(banner_path, pdf_path)

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _publish_sync)
    except Exception as e:
        log.error("發布失敗：%s", e, exc_info=True)
        await interaction.followup.send(f"❌ 發布失敗：{e}")
        await _dm_owner(f"⚠️ 發布失敗\n錯誤：{e}")
        return

    # 在指定 Discord 頻道貼出摘要
    if CHANNEL_ID:
        try:
            ch = bot.get_channel(CHANNEL_ID)
            if ch:
                embed = _build_report_embed(data)
                await ch.send(embed=embed)
        except Exception as e:
            log.warning("Discord 頻道貼文失敗：%s", e)

    await interaction.followup.send("✅ 發布完成！Email 已寄出，暫存檔已清理。")
    await _dm_owner(f"✅ {data.get('meta', {}).get('date', '')} 日報已發布")


# ── 審核互動按鈕 View ────────────────────────────────────────────────────────
class _ReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=3600)  # 1 小時內有效

    @discord.ui.button(label="✅ 發布日報", style=discord.ButtonStyle.success)
    async def publish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        global _pending_data
        if _pending_data is None:
            await interaction.response.send_message("⚠️ 報告已過期，請重新 /analyze", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        await _do_publish(interaction, _pending_data)
        _pending_data = None
        self.stop()

    @discord.ui.button(label="❌ 取消", style=discord.ButtonStyle.danger)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        global _pending_data
        _pending_data = None
        await interaction.response.send_message("已取消，報告未發布。", ephemeral=True)
        self.stop()


# ── Bot 事件 ─────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await bot.tree.sync()
    log.info("Bot 已上線：%s（ID: %s）", bot.user, bot.user.id)
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
