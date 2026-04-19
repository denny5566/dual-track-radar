import { resolve } from 'path';
import { defineConfig } from 'vite';

/**
 * Vite dev server plugin — handles /api/chat in local development.
 * In production (Vercel), api/chat.js is a serverless function.
 */
function devApiPlugin() {
  return {
    name: 'dev-api',
    configureServer(server) {
      server.middlewares.use('/api/chat', async (req, res) => {
        if (req.method !== 'POST') {
          res.statusCode = 405;
          res.end(JSON.stringify({ error: 'Method not allowed' }));
          return;
        }

        let body = '';
        req.on('data', chunk => { body += chunk.toString(); });
        req.on('end', async () => {
          try {
            const { question, context: _context } = JSON.parse(body);
            const { loadEnv } = await import('vite');
            const envDir = resolve(__dirname, '..'); // project root .env
            const env = loadEnv('', envDir, '');
            const apiKey = env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_API_KEY;

            if (!apiKey) {
              res.statusCode = 200;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({
                answer: `（Dev 模式：環境變數 ANTHROPIC_API_KEY 未設定）\n問題：${question}`,
              }));
              return;
            }

            // RAG context（模組已移除，保留空字串供後續擴充）
            const ragContext = '';

            // 直接呼叫 Anthropic REST API（不依賴 SDK，免安裝額外套件）
            const { default: https } = await import('https');
            const payload = JSON.stringify({
              model: 'claude-haiku-4-5-20251001',
              max_tokens: 512,
              system: '你是財經雷達 AI 分析助手，請根據每日報告內容回答用戶問題。【嚴格限制】只回答與報告相關之問題，否則堅定拒絕。回答最後必須空一行並加上：[分類: 標籤]，標籤請從(大盤趨勢/個股分析/總編觀點/閒聊)四選一。使用繁體中文。',
              messages: [{
                role: 'user',
                content: ragContext ? `【相關報告檢索結果】\n${ragContext}\n\n【問題】\n${question}` : question,
              }],
            });

            const options = {
              hostname: 'api.anthropic.com',
              path: '/v1/messages',
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'x-api-key': apiKey,
                'anthropic-version': '2023-06-01',
                'Content-Length': Buffer.byteLength(payload),
              },
            };

            const apiReq = https.request(options, apiRes => {
              let data = '';
              apiRes.on('data', c => { data += c; });
              apiRes.on('end', () => {
                try {
                  const parsed = JSON.parse(data);
                  let rawAnswer = parsed.content?.find(b => b.type === 'text')?.text || '無法取得回覆';

                  // 移除 [分類: ...] 標籤，不回傳給使用者
                  rawAnswer = rawAnswer.replace(/\n*\[分類:\s*.+?\]\n*/g, '').trim();

                  res.statusCode = 200;
                  res.setHeader('Content-Type', 'application/json');
                  res.end(JSON.stringify({ answer: rawAnswer }));
                } catch {
                  res.statusCode = 500;
                  res.end(JSON.stringify({ error: 'Parse error' }));
                }
              });
            });
            apiReq.on('error', err => {
              res.statusCode = 500;
              res.end(JSON.stringify({ error: err.message }));
            });
            apiReq.write(payload);
            apiReq.end();

          } catch (err) {
            res.statusCode = 500;
            res.end(JSON.stringify({ error: err.message }));
          }
        });
      });
    },
  };
}

export default defineConfig({
  plugins: [devApiPlugin()],
  build: {
    rollupOptions: {
      input: {
        main:      resolve(__dirname, 'index.html'),
        article:   resolve(__dirname, 'article.html'),
        dashboard: resolve(__dirname, 'd.html'),
      },
    },
  },
});
