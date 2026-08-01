# syntax=docker
# Komichi 远程爬虫镜像
#
# 使用微软官方 Playwright 镜像（已预装 Chromium + 系统依赖），
# 省去 playwright install 步骤。
# ARM64 平台（如 Oracle Cloud Ampere）同样支持。
#
# 构建: docker build -t komichi-crawler .
# 运行: docker run --rm -e KOMICHI_WORKER_URL=... komichi-crawler refresh

FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# 安装 supercronic（容器内 cron 调度器，无需宿主机 cron）
# 自动识别 CPU 架构
ARG TARGETARCH
RUN <<'EOF'
set -eux
case "${TARGETARCH:-amd64}" in
  amd64) SC_ARCH=amd64 ;;
  arm64) SC_ARCH=arm64 ;;
  *) echo "unsupported arch: ${TARGETARCH}"; exit 1 ;;
esac
curl -fsSLo /usr/local/bin/supercronic \
  "https://github.com/aptible/supercronic/releases/download/v0.2.30/supercronic-linux-${SC_ARCH}"
chmod +x /usr/local/bin/supercronic
EOF

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY komichi_crawler/ ./komichi_crawler/
COPY config.example.json ./config.json

RUN mkdir -p logs

# 默认: 一次性运行追更
# 定时模式由 docker-compose.yml 的 scheduler 服务通过 entrypoint 覆盖
CMD ["python", "-m", "komichi_crawler", "refresh"]
