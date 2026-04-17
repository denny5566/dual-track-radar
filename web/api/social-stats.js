/**
 * Vercel Serverless Function — 社群媒體統計 API
 * GET /api/social-stats?platform=youtube|instagram|threads|youtube-comments
 *
 * 環境變數：
 *   YOUTUBE_API_KEY          YouTube Data API v3 金鑰
 *   YOUTUBE_CHANNEL_ID       頻道 ID（UC 開頭）
 *   IG_ACCESS_TOKEN          Instagram Graph API 長效 Token
 *   IG_USER_ID               Instagram 用戶 ID
 *   THREADS_ACCESS_TOKEN     Threads API Token（Meta 開發者）
 *   THREADS_USER_ID          Threads 用戶 ID
 */

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { platform, videoId } = req.query;

  try {
    switch (platform) {
      case 'youtube':
        return res.status(200).json(await fetchYouTubeStats());
      case 'youtube-comments':
        if (!videoId) return res.status(400).json({ error: 'videoId required' });
        return res.status(200).json(await fetchYouTubeComments(videoId));
      case 'instagram':
        return res.status(200).json(await fetchInstagramStats());
      case 'threads':
        return res.status(200).json(await fetchThreadsStats());
      default:
        return res.status(400).json({ error: 'Unknown platform' });
    }
  } catch (err) {
    console.error(`social-stats [${platform}] error:`, err);
    return res.status(500).json({ error: err.message });
  }
}

// ── YouTube ──────────────────────────────────────────────────────────────────
async function fetchYouTubeStats() {
  const apiKey    = process.env.YOUTUBE_API_KEY;
  const channelId = process.env.YOUTUBE_CHANNEL_ID;

  if (!apiKey || !channelId) {
    return { error: 'YOUTUBE_API_KEY or YOUTUBE_CHANNEL_ID not configured' };
  }

  // 頻道基本數據
  const channelUrl = `https://www.googleapis.com/youtube/v3/channels?part=statistics,snippet&id=${channelId}&key=${apiKey}`;
  const chRes  = await fetch(channelUrl);
  const chData = await chRes.json();

  if (!chRes.ok || !chData.items?.length) {
    throw new Error(chData.error?.message || 'YouTube channel not found');
  }

  const stats   = chData.items[0].statistics;
  const snippet = chData.items[0].snippet;

  // 最新 3 支影片
  const videosUrl = `https://www.googleapis.com/youtube/v3/search?part=snippet&channelId=${channelId}&maxResults=3&order=date&type=video&key=${apiKey}`;
  const vRes  = await fetch(videosUrl);
  const vData = await vRes.json();

  const recentVideos = (vData.items || []).map(item => ({
    videoId:     item.id.videoId,
    title:       item.snippet.title,
    publishedAt: item.snippet.publishedAt,
    thumbnail:   item.snippet.thumbnails?.medium?.url,
  }));

  return {
    subscribers:  stats.subscriberCount,
    totalViews:   stats.viewCount,
    videoCount:   stats.videoCount,
    channelTitle: snippet.title,
    latestVideo:  recentVideos[0] || null,
    recentVideos,
  };
}

async function fetchYouTubeComments(videoId) {
  const apiKey = process.env.YOUTUBE_API_KEY;
  if (!apiKey) return { error: 'YOUTUBE_API_KEY not configured', comments: [] };

  const url = `https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&videoId=${videoId}&maxResults=50&order=relevance&key=${apiKey}`;
  const res  = await fetch(url);
  const data = await res.json();

  if (!res.ok) throw new Error(data.error?.message || 'YouTube comments fetch failed');

  const comments = (data.items || []).map(item =>
    item.snippet.topLevelComment.snippet.textDisplay
      .replace(/<[^>]+>/g, '')  // 移除 HTML 標籤
      .trim()
  ).filter(Boolean);

  return { comments, total: data.pageInfo?.totalResults };
}

// ── Instagram ─────────────────────────────────────────────────────────────────
async function fetchInstagramStats() {
  const token  = process.env.IG_ACCESS_TOKEN;
  const userId = process.env.IG_USER_ID;

  if (!token || !userId) {
    return { notConfigured: true };
  }

  const url = `https://graph.instagram.com/${userId}?fields=followers_count,media_count,username&access_token=${token}`;
  const res  = await fetch(url);
  const data = await res.json();

  if (!res.ok || data.error) {
    throw new Error(data.error?.message || 'Instagram API error');
  }

  return {
    followers:  data.followers_count,
    mediaCount: data.media_count,
    username:   data.username,
    reach:      null, // 需要 Instagram Insights API（Business 帳號）
  };
}

// ── Threads ───────────────────────────────────────────────────────────────────
async function fetchThreadsStats() {
  const token  = process.env.THREADS_ACCESS_TOKEN;
  const userId = process.env.THREADS_USER_ID;

  if (!token || !userId) {
    return { notConfigured: true };
  }

  // Threads Graph API (Meta)
  const url = `https://graph.threads.net/${userId}?fields=followers_count,threads_count&access_token=${token}`;
  const res  = await fetch(url);
  const data = await res.json();

  if (!res.ok || data.error) {
    throw new Error(data.error?.message || 'Threads API error');
  }

  return {
    followers:  data.followers_count,
    postCount:  data.threads_count,
    replyCount: null,
  };
}
