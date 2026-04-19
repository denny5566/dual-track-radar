/**
 * /api/market-data — 市場即時數據代理
 *
 * 資料來源：Stooq.com（免 API Key，適合伺服器端呼叫）
 * 快取策略：將最新有效數據寫入 public/data/market-cache.json，
 *           盤後 / 週末返回快取資料，確保介面不顯示空值。
 */

import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CACHE_PATH = join(__dirname, '../public/data/market-cache.json');
const MAX_HISTORY = 7; // 最多保留幾天的收盤價（用於 sparkline）

// ── Stooq symbol 對照 ─────────────────────────────────────────────────────────

const MACRO_CONFIGS = [
  { key: 'vix',   symbol: '^vix',   decimals: 2 },
  { key: 'us10y', symbol: '10usy.b', decimals: 3 },
  { key: 'dxy',   symbol: 'dxy.fx', decimals: 2 },
  { key: 'gold',  symbol: 'xauusd', decimals: 1 },
  { key: 'wti',   symbol: 'cl.f',   decimals: 2 },
];

const TICKER_CONFIGS = [
  { symbol: '^twii',  name: '台股加權' },
  { symbol: '^spx',   name: 'S&P 500'  },
  { symbol: '^ndx',   name: 'Nasdaq'   },
  { symbol: '^dji',   name: '道瓊'     },
  { symbol: 'tsm.us', name: '台積電ADR'},
  { symbol: 'xauusd', name: '黃金'     },
  { symbol: 'cl.f',   name: 'WTI'      },
];

// ── Stooq 即時報價（CSV 格式）────────────────────────────────────────────────

/**
 * 抓取 Stooq 即時報價。
 * 回傳 { close, open } 或 null（若數據為 N/D 或抓取失敗）。
 */
async function fetchStooqQuote(symbol) {
  const url =
    `https://stooq.com/q/l/?s=${encodeURIComponent(symbol)}&f=sd2t2ohlcv&h&e=csv`;

  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; StockRadar/1.0)' },
    signal: AbortSignal.timeout(8000),
  });

  if (!res.ok) return null;
  const text = await res.text();

  // 格式：Symbol,Date,Time,Open,High,Low,Close,Volume
  const lines = text.trim().split('\n');
  if (lines.length < 2) return null;

  const cols = lines[1].split(',');
  // N/D 代表市場休市或無數據
  if (cols[1] === 'N/D' || cols[6] === 'N/D') return null;

  const close = parseFloat(cols[6]);
  const open  = parseFloat(cols[3]);
  const date  = cols[1]; // "YYYY-MM-DD"
  if (isNaN(close)) return null;

  return { close, open, date };
}

// ── 快取 ─────────────────────────────────────────────────────────────────────

function loadCache() {
  try {
    return JSON.parse(readFileSync(CACHE_PATH, 'utf-8'));
  } catch {
    return { macro: {}, ticker: [], closesHistory: {}, ts: 0 };
  }
}

function saveCache(data) {
  try {
    mkdirSync(join(__dirname, '../public/data'), { recursive: true });
    writeFileSync(CACHE_PATH, JSON.stringify(data), 'utf-8');
  } catch { /* 不影響 API 回應 */ }
}

/**
 * 更新 sparkline 歷史（最多保留 MAX_HISTORY 天的收盤價）。
 * @param {object} history   { [key]: { closes: number[], dates: string[] } }
 * @param {string} key       macro key（vix / us10y / …）
 * @param {number} close     今天收盤價
 * @param {string} date      YYYY-MM-DD
 */
function pushHistory(history, key, close, date) {
  if (!history[key]) history[key] = { closes: [], dates: [] };
  const h = history[key];
  // 同一天不重複加
  if (h.dates[h.dates.length - 1] === date) {
    h.closes[h.closes.length - 1] = close; // 更新最新一筆
    return;
  }
  h.closes.push(close);
  h.dates.push(date);
  if (h.closes.length > MAX_HISTORY) {
    h.closes.shift();
    h.dates.shift();
  }
}

// ── Handler ──────────────────────────────────────────────────────────────────

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'public, max-age=300');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');

  const cache = loadCache();
  const closesHistory = cache.closesHistory || {};

  // 並行抓取所有 symbol
  const allSymbols = [
    ...new Set([
      ...MACRO_CONFIGS.map(c => c.symbol),
      ...TICKER_CONFIGS.map(c => c.symbol),
    ]),
  ];

  const quotes = {};
  await Promise.allSettled(
    allSymbols.map(async sym => {
      try {
        quotes[sym] = await fetchStooqQuote(sym);
      } catch {
        quotes[sym] = null;
      }
    })
  );

  let anyFresh = false; // 是否有任何新鮮數據

  // ── 組裝 macro ───────────────────────────────────────────────────────────────
  const macro = {};
  for (const cfg of MACRO_CONFIGS) {
    const q = quotes[cfg.symbol];
    const cached = cache.macro?.[cfg.key];

    if (q) {
      // 有新數據：計算 change（以開盤為基準，若無前收可用）
      const prevClose = cached?.price ?? q.open;
      const change    = q.close - prevClose;
      const changePct = prevClose ? (change / prevClose) * 100 : 0;

      // 更新 sparkline 歷史
      pushHistory(closesHistory, cfg.key, q.close, q.date);

      macro[cfg.key] = {
        price:     q.close,
        change,
        changePct,
        closes:    closesHistory[cfg.key]?.closes ?? [q.close],
        decimals:  cfg.decimals,
        fresh:     true,
        date:      q.date,
      };
      anyFresh = true;

    } else if (cached) {
      // 無新數據：回傳快取（標記 stale）
      macro[cfg.key] = {
        ...cached,
        closes: closesHistory[cfg.key]?.closes ?? cached.closes ?? [cached.price],
        fresh: false,
      };
    }
  }

  // ── 組裝 ticker ──────────────────────────────────────────────────────────────
  let ticker;
  const freshTicker = TICKER_CONFIGS.map(cfg => {
    const q = quotes[cfg.symbol];
    if (!q) return null;
    const prevClose = q.open; // 用今日開盤近似前收
    const change    = q.close - prevClose;
    const changePct = prevClose ? (change / prevClose) * 100 : 0;
    return { name: cfg.name, symbol: cfg.symbol, price: q.close, change, changePct };
  }).filter(Boolean);

  if (freshTicker.length > 0) {
    ticker = freshTicker;
    anyFresh = true;
  } else {
    ticker = cache.ticker ?? [];
  }

  // ── 更新快取（只有獲得新數據時才覆寫）──────────────────────────────────────
  if (anyFresh) {
    // 儲存 macro（僅含最新一筆，sparkline 在 closesHistory 裡）
    const macroToCache = {};
    for (const [k, v] of Object.entries(macro)) {
      macroToCache[k] = { price: v.price, change: v.change, changePct: v.changePct, decimals: v.decimals, date: v.date };
    }
    saveCache({
      macro: macroToCache,
      ticker,
      closesHistory,
      ts: Date.now(),
    });
  }

  const ts = anyFresh ? Date.now() : (cache.ts ?? 0);

  res.end(JSON.stringify({ macro, ticker, ts, stale: !anyFresh }));
}
