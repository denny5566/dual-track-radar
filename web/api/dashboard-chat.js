/**
 * Vercel Serverless Function — 儀表板 AI 分析聊天
 * POST /api/dashboard-chat
 * Body (mode=chat):   { mode: 'chat', question: string, statsContext?: object }
 * Body (mode=mining): { mode: 'mining', platform: string, comments: string[] }
 * Returns: { answer: string }
 */

import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

const CHAT_SYSTEM = `你是「財經雷達」頻道主的個人 AI 分析助手，專精於數位內容創作與社群媒體行銷。

你可以協助分析：
- YouTube、Instagram、Threads 的流量數據與趨勢
- 內容策略優化、發布時機建議
- 受眾特性分析與成長策略
- 競品分析與市場定位
- 財經內容的創作方向建議

回答風格：
- 使用繁體中文，語氣專業但不過分正式
- 給出具體可行的建議，而非空泛的原則
- 當有統計數據時，要引用數據支持論點
- 回答長度以 200-400 字為宜，複雜問題可適度延長`;

const MINING_SYSTEM = `你是社群媒體留言分析專家，擅長從大量用戶留言中提取洞察。

分析報告格式（請嚴格遵守）：
## 情感分析
[正面 / 負面 / 中性的比例與描述]

## 熱門主題（前 5 名）
[條列用戶最常討論的主題]

## 常見問題類型
[用戶最常提出的問題分類]

## 關鍵詞雲
[高頻關鍵詞，以「、」分隔]

## 用戶需求洞察
[從留言中發現的隱性需求或改進機會]

## 建議行動
[基於分析結果，給頻道主的 3 點具體建議]

請用繁體中文回答，分析要客觀且基於實際留言內容。`;

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { mode, question, statsContext, platform, comments } = req.body || {};

  try {
    if (mode === 'mining') {
      if (!comments?.length) {
        return res.status(400).json({ error: 'comments array is required' });
      }

      const commentsText = comments
        .slice(0, 100)
        .map((c, i) => `${i + 1}. ${c}`)
        .join('\n');

      const platformLabel = { youtube: 'YouTube', instagram: 'Instagram', threads: 'Threads' }[platform] || platform;

      const message = await client.messages.create({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 1200,
        system: MINING_SYSTEM,
        messages: [{
          role: 'user',
          content: `以下是來自 ${platformLabel} 的 ${comments.length} 則用戶留言，請進行文字探勘分析：\n\n${commentsText}`,
        }],
      });

      const answer = message.content.find(b => b.type === 'text')?.text || '分析失敗';
      return res.status(200).json({ answer });

    } else {
      // mode === 'chat'
      if (!question || typeof question !== 'string') {
        return res.status(400).json({ error: 'question is required' });
      }

      let contextStr = '';
      if (statsContext && Object.keys(statsContext).length) {
        contextStr = `\n\n【當前頻道統計數據】\n${JSON.stringify(statsContext, null, 2)}\n\n請根據以上數據回答問題。`;
      }

      const message = await client.messages.create({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 800,
        system: CHAT_SYSTEM,
        messages: [{
          role: 'user',
          content: contextStr ? `${contextStr}\n\n【問題】${question}` : question,
        }],
      });

      const answer = message.content.find(b => b.type === 'text')?.text || '無法取得回覆';
      return res.status(200).json({ answer });
    }
  } catch (err) {
    console.error('Dashboard chat error:', err);
    return res.status(500).json({ error: 'AI service error' });
  }
}
