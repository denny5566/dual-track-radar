export interface NewsItem {
  headline: string;
  summary: string;
  image_url: string | null;
}

export interface RadarData {
  meta: {
    date: string;
    channels: string[];
  };
  daily_focus: string;
  top5_news: NewsItem[];
  comparison: {
    capital_futures: {
      title: string;
      sentiment: string;
      key_levels: string;
      main_points: string[];
      strategy: string;
    };
    yu_ting_hao: {
      title: string;
      sentiment: string;
      macro_indicators: string[];
      main_points: string[];
      strategy: string;
    };
  };
  clash_or_sync: string;
  investor_reminder: string;
  outputs: {
    edm_subject: string;
    social_media_cards: Array<{
      type: string;
      text?: string;
      left?: string;
      right?: string;
    }>;
  };
}
