import React from "react";
import { Composition } from "remotion";
import { RadarVideo } from "./RadarVideo";
import sampleData from "./data/sample.json";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* 直式（IG / TikTok）*/}
      <Composition
        id="RadarVideo"
        component={RadarVideo}
        durationInFrames={90 * 30}   // 90 秒 × 30fps
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{ data: sampleData }}
      />
      {/* 橫式（YouTube）*/}
      <Composition
        id="RadarVideoHorizontal"
        component={RadarVideo}
        durationInFrames={90 * 30}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{ data: sampleData }}
      />
    </>
  );
};
