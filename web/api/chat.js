/**
 * Vercel Serverless Function — AI Chat Proxy
 * POST /api/chat
 * Body: { question: string, context: string }
 * Returns: { answer: string }
 */

import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

const SYSTEM_PROMPT = `你是「財經雷達」的 AI 分析助手，協助用戶深入理解財經報告與市場動態。

你可以回答：
- 本站財經報告的內容解析（優先根據提供的 Context 回答）
- 財經術語、指標的定義說明（如 EPS、費半、殖利率等）
- 台股、美股市場結構與運作機制的一般性說明
- 對報告中提及的趨勢進行延伸討論

注意事項：
1. 優先根據用戶提供的報告內容（Context）回答，無相關 Context 時可用一般財經知識輔助。
2. 超出財經範疇的問題（天氣、娛樂、閒聊）請婉拒：「我是財經雷達的 AI 助手，主要協助財經相關問題。」
3. 不提供具體買賣建議、目標價或持股推薦，回答結尾加上「⚠️ 僅供參考，非投資建議」。
4. 使用繁體中文，術語精確，回答 150-250 字為宜。`;

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { question, context } = req.body || {};

  if (!question || typeof question !== 'string') {
    return res.status(400).json({ error: 'question is required' });
  }

  const userMsg = context
    ? `【今日報告內容】\n${context}\n\n【問題】\n${question}`
    : question;

  try {
    const message = await client.messages.create({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 512,
      system: SYSTEM_PROMPT,
      messages: [{ role: 'user', content: userMsg }],
    });

    const answer = message.content.find(b => b.type === 'text')?.text || '無法取得回覆';
    res.status(200).json({ answer });
  } catch (err) {
    console.error('Claude API error:', err);
    res.status(500).json({ error: 'AI service error' });
  }
}
