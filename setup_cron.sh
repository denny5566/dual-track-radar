#!/bin/bash
# Oracle Cloud VM 部署腳本（Ubuntu 22.04）
# 用法：chmod +x setup_cron.sh && ./setup_cron.sh
#
# 效果：
#   - 週一至週五 09:00 自動跑完整管線（docker compose run radar）
#   - Discord Bot 常駐（docker compose up -d discord-bot）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "[setup_cron] 專案目錄：$SCRIPT_DIR"

# ── 安裝 Docker（若尚未安裝）────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "[setup_cron] 安裝 Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "[setup_cron] Docker 已安裝，請重新登入後再執行本腳本"
    exit 1
fi

# ── Build 映像 ───────────────────────────────────────────────────────────────
echo "[setup_cron] 建立 Docker 映像..."
docker compose -f "$SCRIPT_DIR/docker-compose.yml" build

# ── 啟動 Discord Bot 常駐服務 ────────────────────────────────────────────────
echo "[setup_cron] 啟動 Discord Bot..."
docker compose -f "$SCRIPT_DIR/docker-compose.yml" up -d discord-bot

# ── 設定 crontab（週一至週五 09:00）────────────────────────────────────────
CRON_CMD="0 9 * * 1-5 docker compose -f $SCRIPT_DIR/docker-compose.yml run --rm radar >> $LOG_DIR/radar.log 2>&1"

# 避免重複寫入
(crontab -l 2>/dev/null | grep -v "docker-compose.yml"; echo "$CRON_CMD") | crontab -

echo ""
echo "[setup_cron] 完成！crontab 已設定："
crontab -l | grep radar
echo ""
echo "手動測試管線："
echo "  docker compose -f $SCRIPT_DIR/docker-compose.yml run --rm radar python main.py --no-email --no-cleanup"
echo ""
echo "查看 Discord Bot 狀態："
echo "  docker compose -f $SCRIPT_DIR/docker-compose.yml logs -f discord-bot"
