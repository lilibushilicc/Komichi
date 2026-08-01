#!/usr/bin/env bash
# Komichi 远程爬虫一键安装脚本（Linux VPS）
#
# 用法:
#   bash deploy/install.sh                      # 装到 /opt/komichi-crawler
#   INSTALL_DIR=/home/me/komichi bash deploy/install.sh  # 自定义目录
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="${INSTALL_DIR:-/opt/komichi-crawler}"

echo "=== Komichi 远程爬虫安装 ==="
echo "源码目录:   $SOURCE_DIR"
echo "安装目录:   $INSTALL_DIR"
echo ""

# 1. 检查 Python
if ! command -v python3 &>/dev/null; then
  echo "[X] 未找到 python3，请先安装 Python 3.9+"
  echo "    Debian/Ubuntu: sudo apt install -y python3 python3-venv"
  exit 1
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
echo "[OK] Python $PY_VER"

# 2. 创建安装目录
sudo mkdir -p "$INSTALL_DIR"
sudo chown -R "$USER":"$USER" "$INSTALL_DIR"

# 3. 复制代码
cp -r "$SOURCE_DIR"/komichi_crawler "$INSTALL_DIR/"
cp "$SOURCE_DIR"/requirements.txt "$INSTALL_DIR/"
cp "$SOURCE_DIR"/config.example.json "$INSTALL_DIR/config.json"
cp "$SCRIPT_DIR"/crawler.env.example "$INSTALL_DIR/crawler.env"
cp -r "$SCRIPT_DIR" "$INSTALL_DIR/deploy"
mkdir -p "$INSTALL_DIR/logs"

# 4. 虚拟环境 + 依赖
echo ""
echo "=== 创建虚拟环境并安装依赖 ==="
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip --quiet
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet
echo "[OK] Python 依赖已安装"

# 5. Playwright Chromium
echo ""
echo "=== 安装 Chromium ==="
echo "    (install-deps 需要 sudo 安装系统库)"
"$INSTALL_DIR/.venv/bin/python" -m playwright install chromium
sudo "$INSTALL_DIR/.venv/bin/python" -m playwright install-deps chromium || {
  echo "[!] install-deps 失败，请手动执行:"
  echo "    sudo $INSTALL_DIR/.venv/bin/python -m playwright install-deps chromium"
}

# 6. 创建专用用户（systemd 用）
if ! id "komichi" &>/dev/null; then
  sudo useradd -r -s /usr/sbin/nologin -d "$INSTALL_DIR" komichi 2>/dev/null || true
fi
sudo chown -R komichi:komichi "$INSTALL_DIR"

# 7. 完成提示
echo ""
echo "=========================================="
echo "  安装完成"
echo "=========================================="
echo ""
echo "下一步:"
echo "  1. 编辑配置 (二选一):"
echo "     a) 环境变量:  nano $INSTALL_DIR/crawler.env"
echo "     b) JSON 文件: nano $INSTALL_DIR/config.json"
echo "     填入 Worker URL / 用户名 / 密码"
echo ""
echo "  2. 验证 Playwright:"
echo "     sudo -u komichi $INSTALL_DIR/.venv/bin/python -m komichi_crawler check-playwright"
echo ""
echo "  3. 测试运行:"
echo "     cd $INSTALL_DIR && sudo -u komichi .venv/bin/python -m komichi_crawler list"
echo ""
echo "  4. 启用定时 (二选一):"
echo "     A) systemd timer (推荐):"
echo "        sudo cp $INSTALL_DIR/deploy/komichi-crawler.service /etc/systemd/system/"
echo "        sudo cp $INSTALL_DIR/deploy/komichi-crawler.timer /etc/systemd/system/"
echo "        sudo systemctl daemon-reload"
echo "        sudo systemctl enable --now komichi-crawler.timer"
echo "        # 查看: systemctl list-timers | grep komichi"
echo "        # 日志: journalctl -u komichi-crawler -f"
echo ""
echo "     B) cron:"
echo "        crontab $INSTALL_DIR/deploy/crontab.example"
echo "        # 注意修改 crontab 里的路径"
echo ""
