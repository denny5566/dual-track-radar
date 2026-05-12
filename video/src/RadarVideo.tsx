import React from "react";
import { AbsoluteFill, Series, Audio, staticFile } from "remotion";
import { Opening } from "./components/Opening";
import { NewsItem } from "./components/NewsItem";
import { InsightCard } from "./components/InsightCard";
import { Ending } from "./components/Ending";
import { RadarData } from "./types";
import durationsRaw from "./data/durations.json";

export interface RadarVideoProps {
  data: RadarData;
}

const FPS = 30;
// 3 秒 buffer（原為 2 秒）：Edge TTS 實際輸出時長有時比 mutagen 量測略長，
// 加大緩衝確保最後一個字音播完後才切換場景，避免聲音被截斷。
const BUFFER_FRAMES = 90;

/** 將秒數轉為 frames（無條件進位後加 buffer）*/
function toFrames(seconds: number): number {
  return Math.ceil(seconds * FPS) + BUFFER_FRAMES;
}

const dur = durationsRaw as Record<string, number>;

export const RadarVideo: React.FC<RadarVideoProps> = ({ data }) => {
  const { meta, daily_focus, top5_news, clash_or_sync, investor_reminder } = data;

  return (
    <AbsoluteFill>
      <Series>
        {/* Scene 1 — Opening */}
        <Series.Sequence durationInFrames={toFrames(dur.opening ?? 7)}>
          <Audio src={staticFile("audio/opening.mp3")} />
          <Opening date={meta.date} dailyFocus={daily_focus} />
        </Series.Sequence>

        {/* Scene 2 — 本日 5 大新聞 */}
        {top5_news.map((item, i) => {
          const key = `news_${String(i + 1).padStart(2, "0")}`;
          return (
            <Series.Sequence key={i} durationInFrames={toFrames(dur[key] ?? 9)}>
              <Audio src={staticFile(`audio/${key}.mp3`)} />
              <NewsItem item={item} index={i} total={top5_news.length} />
            </Series.Sequence>
          );
        })}

        {/* Scene 3 — 綜合洞察 + 投資人提醒 */}
        <Series.Sequence durationInFrames={toFrames(dur.insight ?? 16)}>
          <Audio src={staticFile("audio/insight.mp3")} />
          <InsightCard clashOrSync={clash_or_sync} investorReminder={investor_reminder} />
        </Series.Sequence>

        {/* Scene 4 — Ending */}
        <Series.Sequence durationInFrames={toFrames(dur.ending ?? 6)}>
          <Audio src={staticFile("audio/ending.mp3")} />
          <Ending date={meta.date} />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};
