import React from "react";
import { AbsoluteFill, Series } from "remotion";
import { Opening } from "./components/Opening";
import { NewsItem } from "./components/NewsItem";
import { InsightCard } from "./components/InsightCard";
import { Ending } from "./components/Ending";
import { RadarData } from "./types";

interface Props {
  data: RadarData;
}

// 各段時長（單位：frame，30fps）
const SCENE = {
  opening: 90,       //  3 秒
  newsItem: 240,     //  8 秒 × 5 = 40 秒
  insight: 450,      // 15 秒
  ending: 150,       //  5 秒
  // 合計 = 90 + 1200 + 450 + 150 = 1890 frames = 63 秒
};

export const RadarVideo: React.FC<Props> = ({ data }) => {
  const { meta, daily_focus, top5_news, clash_or_sync, investor_reminder } = data;

  return (
    <AbsoluteFill>
      <Series>
        {/* Scene 1 — Opening */}
        <Series.Sequence durationInFrames={SCENE.opening}>
          <Opening date={meta.date} dailyFocus={daily_focus} />
        </Series.Sequence>

        {/* Scene 2 — 本日 5 大新聞 */}
        {top5_news.map((item, i) => (
          <Series.Sequence key={i} durationInFrames={SCENE.newsItem}>
            <NewsItem item={item} index={i} total={top5_news.length} />
          </Series.Sequence>
        ))}

        {/* Scene 3 — 綜合洞察 + 投資人提醒 */}
        <Series.Sequence durationInFrames={SCENE.insight}>
          <InsightCard clashOrSync={clash_or_sync} investorReminder={investor_reminder} />
        </Series.Sequence>

        {/* Scene 4 — Ending */}
        <Series.Sequence durationInFrames={SCENE.ending}>
          <Ending date={meta.date} />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};
