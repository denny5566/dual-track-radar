"""
download_helper.py — 本機下載音檔並上傳至 Oracle VM

背景說明：
  Oracle Cloud VM 的 IP 被 YouTube 列為資料中心 IP，即使有 cookies 也無法下載。
  此腳本在你的本機（家用 IP）執行，繞過封鎖，下載後透過 SCP 上傳至 VM。

每日流程：
  1. 在本機執行：  python download_helper.py
  2. 上傳完成後：  到 Discord 按「⚙️ 僅重新分析（不下載）」

進階用法（指定特定影片 URL）：
  python download_helper.py --cap "https://www.youtube.com/watch?v=..." --yu "https://www.youtube.com/watch?v=..."
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# ── VM 連線設定 ───────────────────────────────────────────────────────────────
VM_HOST     = "opc@129.150.39.175"
VM_KEY      = "C:/Users/user/ssh/ssh-key-2026-04-16.key"
VM_AUDIO_DIR = "/home/opc/NTUAI_project/output/audio"

# ── 工具 ─────────────────────────────────────────────────────────────────────

def _scp(local_path: str, remote_path: str) -> bool:
    """SCP 單一檔案到 VM。"""
    cmd = [
        "scp",
        "-i", VM_KEY,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=30",
        str(local_path),
        f"{VM_HOST}:{remote_path}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  SCP 錯誤：{result.stderr.strip()[:200]}")
    return result.returncode == 0


def _ensure_remote_dir() -> None:
    """確保 VM 上的目標目錄存在。"""
    subprocess.run(
        ["ssh", "-i", VM_KEY, "-o", "StrictHostKeyChecking=no",
         VM_HOST, f"mkdir -p {VM_AUDIO_DIR}"],
        capture_output=True,
    )


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main() -> bool:
    parser = argparse.ArgumentParser(description="本機下載 YouTube 音檔並上傳至 VM")
    parser.add_argument("--cap", metavar="URL", help="群益期貨指定影片 URL（留空自動抓最新）")
    parser.add_argument("--yu",  metavar="URL", help="游庭澔指定影片 URL（留空自動抓最新）")
    args = parser.parse_args()

    # 必須在專案目錄執行，才能 import config / monitor
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))

    try:
        from monitor import run_dual_monitor
        from config  import AUDIO_DIR
    except ImportError as e:
        print(f"❌ 無法載入專案模組：{e}")
        print("   請確認在 NTUAI_project 目錄下執行此腳本，且已安裝 yt-dlp。")
        return False

    url_overrides: dict[str, str] = {}
    if args.cap:
        url_overrides["capital_futures"] = args.cap.strip()
    if args.yu:
        url_overrides["yu_ting_hao"]     = args.yu.strip()

    print("=" * 60)
    print("  雙軌財經雷達 — 本機音檔下載工具")
    print("=" * 60)
    print(f"  目標 VM：{VM_HOST}")
    print(f"  上傳路徑：{VM_AUDIO_DIR}")
    print()

    # Step 1: 下載
    print("🔍 搜尋並下載音檔（使用本機 IP）...")
    try:
        results = run_dual_monitor(url_overrides=url_overrides or None)
    except Exception as e:
        print(f"❌ 下載失敗：{e}")
        return False

    # Step 2: 確認 VM 目錄存在
    _ensure_remote_dir()

    # Step 3: SCP 上傳
    success_count = 0
    for key, res in results.items():
        if res.get("success") and res.get("audio_path"):
            local_path = Path(res["audio_path"])
            title      = res.get("title", "（未知標題）")[:60]
            print(f"\n⬆️  上傳 {local_path.name}...")
            print(f"   標題：{title}")
            if _scp(str(local_path), f"{VM_AUDIO_DIR}/{local_path.name}"):
                print(f"   ✅ 上傳成功")
                success_count += 1
            else:
                print(f"   ❌ 上傳失敗")
        else:
            ch_name = {"capital_futures": "群益期貨", "yu_ting_hao": "游庭澔"}.get(key, key)
            print(f"\n❌ {ch_name}：下載失敗（請確認影片是否存在或 yt-dlp 已安裝）")

    print()
    print("=" * 60)
    if success_count == 2:
        print("✅ 兩個頻道音檔已上傳 VM！")
        print()
        print("👉 下一步：到 Discord 控制面板")
        print("   按「⚙️ 僅重新分析（不下載）」開始分析")
    elif success_count == 1:
        print(f"⚠️  只有 {success_count}/2 個頻道成功")
        print("   可按「⚙️ 僅重新分析」，分析會使用成功上傳的那個頻道")
    else:
        print("❌ 所有頻道下載失敗")
        print("   請確認：1) yt-dlp 已安裝  2) 網路正常  3) YouTube 可正常開啟")
    print("=" * 60)
    return success_count > 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
