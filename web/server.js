/**
 * Production server for Oracle ARM VM.
 * Replaces Vercel serverless functions with Express routes.
 *
 * Serves:
 *   /api/chat             → api/chat.js
 *   /api/dashboard-chat   → api/dashboard-chat.js
 *   /api/social-stats     → api/social-stats.js
 *   /d                    → dist/d.html
 *   /data/*               → public/data/ (volume mount, pipeline 每次更新)
 *   /images/*             → public/images/ (volume mount)
 *   /*                    → dist/ (Vite build)
 */

import express from 'express';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

import chatHandler          from './api/chat.js';
import dashboardChatHandler from './api/dashboard-chat.js';
import socialStatsHandler   from './api/social-stats.js';
import marketDataHandler    from './api/market-data.js';
import videoPublishHandler  from './api/video-publish.js';
import { loadRootEnv }     from './env-loader.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = join(__dirname, '..');
loadRootEnv(ROOT_DIR);

const app  = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// ── API routes ────────────────────────────────────────────────────────────────
app.post('/api/chat',           chatHandler);
app.post('/api/dashboard-chat', dashboardChatHandler);
app.get ('/api/social-stats',   socialStatsHandler);
app.get ('/api/market-data',    marketDataHandler);
app.post('/api/video-publish/:action', videoPublishHandler);
app.get ('/api/video-publish',  videoPublishHandler);
app.post('/api/video-publish',  videoPublishHandler);

// ── /d route（等同 vercel.json rewrites）──────────────────────────────────────
app.get('/d', (_req, res) => res.sendFile(join(__dirname, 'dist', 'd.html')));

// ── 動態資料（pipeline 寫入，volume mount 保持最新）────────────────────────────
app.use('/data',   express.static(join(__dirname, 'public', 'data')));
app.use('/images', express.static(join(__dirname, 'public', 'images')));
app.use('/videos', express.static(join(__dirname, 'public', 'videos')));
app.use('/generated-videos', express.static(join(ROOT_DIR, 'video', 'out')));

// ── Vite build 靜態檔案 ───────────────────────────────────────────────────────
app.use(express.static(join(__dirname, 'dist')));

// ── SPA fallback ─────────────────────────────────────────────────────────────
app.get('*', (_req, res) => res.sendFile(join(__dirname, 'dist', 'index.html')));

app.listen(PORT, () => console.log(`[web] listening on :${PORT}`));
