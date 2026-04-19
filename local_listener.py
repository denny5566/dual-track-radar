"""
local_listener.py — 本機下載監聽器

在你的 Windows 本機執行，每 15 秒輪詢 Discord 頻道。
當偵測到 Discord 控制面板的「🖥️ 本機下載」觸發訊號時：
  1. 在本機以家用 IP 下載兩頻道音檔（MP3）
  2. SCP 上傳至 Oracle VM
  3. 在 Discord 頻道回報結果
上傳成功後，到 Discord 按「⚙️ 僅重新分析（不下載）」即可。

啟動方式：
  python local_listener.py

停止：Ctrl+C
"""

from __future__ import annotations

import os
import sys
import time
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── 讀取 .env ─────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

BOT_TOKEN  = os.getenv("DISCORD_BOT_TOKEN", "")
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID", "")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ 缺少 DISCORD_BOT_TOKEN 或 DISCORD_CHANNEL_ID，請確認 .env 設定")
    sys.exit(1)

DISCORD_API    = "https://discord.com/api/v10"
HEADERS        = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
POLL_INTERVAL  = 15          # 輪詢間隔（秒）
TRIGGER_EXPIRE = 120         # 觸發訊號有效期（秒），超過則忽略避免重複執行
TRIGGER_MARKER = "LOCAL_DOWNLOAD_TRIGGER"


# ── Discord REST 工具 ─────────────────────────────────────────────────────────

def get_messages(after_id: str | None = None) -> list[dict]:
    params: dict = {"limit": 20}
    if after_id:
        params["after"] = after_id
    try:
        r = requests.get(
            f"{DISCORD_API}/channels/{CHANNEL_ID}/messages",
            headers=HEADERS, params=params, timeout=10,
        )
        return r.json() if r.ok else []
    except Exception:
        return []


def post_to_channel(content: str) -> None:
    try:
        requests.post(
            f"{DISCORD_API}/channels/{CHANNEL_ID}/messages",
            headers=HEADERS,
            json={"content": content},
            timeout=10,
        )
    except Exception:
        pass


def _snowflake_to_dt(snowflake_id: str) -> datetime:
    """將 Discord snowflake ID 轉換成 UTC datetime。"""
    ts_ms = (int(snowflake_id) >> 22) + 1420070400000
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)


def is_trigger(msg: dict) -> bool:
    """判斷訊息是否為本機下載觸發，且在有效期內。"""
    for embed in msg.get("embeds", []):
        if TRIGGER_MARKER in embed.get("footer", {}).get("text", ""):
            # 檢查觸發時間是否在有效期內
            msg_time = _snowflake_to_dt(msg["id"])
            age = (datetime.now(tz=timezone.utc) - msg_time).total_seconds()
            if age <= TRIGGER_EXPIRE:
                return True
            else:
                print(f"  [skip] 觸發訊號已過期（{age:.0f} 秒前），忽略。")
    return False


# ── 下載 + 上傳 ───────────────────────────────────────────────────────────────

def run_download() -> tuple[bool, str]:
    """執行 download_helper.py，回傳 (成功?, 輸出文字)。"""
    script = Path(__file__).parent / "download_helper.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=300,      # 最多等 5 分鐘
            cwd=str(script.parent),
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "下載超時（> 5 分鐘）"
    except Exception as e:
        return False, str(e)


# ── 主迴圈 ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 55)
    print("  雙軌財經雷達 — 本機下載監聽器")
    print("=" * 55)
    print(f"  頻道 ID ：{CHANNEL_ID}")
    print(f"  輪詢間隔：{POLL_INTERVAL} 秒")
    print(f"  觸發有效期：{TRIGGER_EXPIRE} 秒")
    print("  按 Ctrl+C 停止")
    print()

    # 取得目前最新訊息 ID，避免誤處理歷史舊訊號
    seed = get_messages()
    last_id: str | None = seed[0]["id"] if seed else None
    print(f"✅ 監聽中（起始訊息 ID: {last_id}）...")

    busy = False   # 防止同時觸發多次

    while True:
        time.sleep(POLL_INTERVAL)

        if busy:
            continue

        new_msgs = get_messages(after_id=last_id)
        if not new_msgs:
            continue

        # Discord 回傳順序是「最新在前」，反轉為時間正序
        for msg in reversed(new_msgs):
            last_id = msg["id"]

            if not is_trigger(msg):
                continue

            # ── 觸發 ──
            busy = True
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{ts}] 🔔 偵測到下載觸發訊號！")
            post_to_channel("🖥️ **本機監聽器已收到觸發！** 正在下載音檔，請稍候…")

            ok, output = run_download()
            ts2 = datetime.now().strftime("%H:%M:%S")

            # 印出輸出的最後幾行
            for line in output.splitlines()[-8:]:
                print(f"  {line}")

            if ok:
                print(f"[{ts2}] ✅ 下載 + 上傳完成")
                post_to_channel(
                    "✅ **音檔已下載並上傳至 VM！**\n"
                    "👉 請到 Discord 控制面板按「⚙️ 僅重新分析（不下載）」繼續流程。"
                )
            else:
                print(f"[{ts2}] ❌ 失敗")
                snippet = "\n".join(output.splitlines()[-6:])
                post_to_channel(
                    f"❌ **音檔下載失敗**\n```\n{snippet[:400]}\n```"
                )

            busy = False
            break    # 每次只處理第一個觸發，避免重複


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✋ 監聽器已停止")
