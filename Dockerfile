# ── Oracle Cloud VM.Standard.A1.Flex（ARM64 / Ubuntu 22.04）────────────────
# python:3.12-slim 官方映像支援 linux/arm64，可直接在 Oracle VM 上跑
FROM python:3.12-slim

# 系統依賴：ffmpeg（yt-dlp + pydub）、Chromium（Playwright）、Node.js 20（Remotion 渲染）、build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        git \
        gcc \
        g++ \
        libsndfile1 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先複製 requirements 利用 Docker 快取層
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安裝 Playwright Chromium（渲染 EDM Banner / PDF 用）
RUN playwright install chromium --with-deps

# 安裝 Remotion 相依套件（video/ 子目錄）
COPY video/package*.json video/
RUN cd video && npm install --prefer-offline

# 安裝 Web server runtime 相依套件（Express + API SDK）
COPY web/package*.json web/
RUN cd web && npm install --omit=dev

# 複製專案程式碼
COPY . .

# 建立必要目錄（output/*、data/）
RUN mkdir -p output/audio output/transcripts output/analysis output/cards data

# 預設執行完整管線
CMD ["python", "main.py"]
