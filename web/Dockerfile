# ── Stage 1: Build Vite app ────────────────────────────────────────────────────
FROM node:20-slim AS builder

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
# node:20-slim 官方支援 linux/arm64（Oracle VM.Standard.A1.Flex）
FROM node:20-slim

WORKDIR /app

# 只複製 runtime 需要的檔案
COPY --from=builder /app/dist        ./dist
COPY --from=builder /app/api         ./api
COPY --from=builder /app/server.js   ./server.js
COPY --from=builder /app/package*.json ./

# 只安裝 production 依賴（express + @anthropic-ai/sdk）
RUN npm install --omit=dev

# public/data 與 public/images 由 volume mount 注入，不 COPY 進 image
RUN mkdir -p public/data public/images

EXPOSE 3000
CMD ["node", "server.js"]
