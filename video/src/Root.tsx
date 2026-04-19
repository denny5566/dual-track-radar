import React from "react";
import { Composition } from "remotion";
import { RadarVideo } from "./RadarVideo";
import sampleData from "./data/sample.json";
import durationsRaw from "./data/durations.json";

const FPS = 30;
const BUFFER_FRAMES = 90; // 與 RadarVideo.tsx 保持一致（3 秒 buffer）

function toFrames(seconds: number): number {
  return Math.ceil(seconds * FPS) + BUFFER_FRAMES;
}

const dur = durationsRaw as Record<string, number>;

// 計算總 frames：opening + news_01~05 + insight + ending
const totalFrames =
  toFrames(dur.opening ?? 7) +
  [1, 2, 3, 4, 5].reduce(
    (sum, i) => sum + toFrames(dur[`news_0${i}`] ?? 9),
    0
  ) +
  toFrames(dur.insight ?? 16) +
  toFrames(dur.ending ?? 6);

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* 直式（IG / TikTok）*/}
      <Composition
        id="RadarVideo"
        component={RadarVideo}
        durationInFrames={totalFrames}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={{ data: sampleData }}
      />
      {/* 橫式（YouTube）*/}
      <Composition
        id="RadarVideoHorizontal"
        component={RadarVideo}
        durationInFrames={totalFrames}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={{ data: sampleData }}
      />
    </>
  );
};
