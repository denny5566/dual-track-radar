import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing, Img, staticFile } from "remotion";
import { NewsItem as NewsItemType } from "../types";
import { COLORS, fontTC, fontEn } from "../theme";

interface Props {
  item: NewsItemType;
  index: number;
  total: number;
}

const BG_GRADIENTS = [
  "linear-gradient(160deg, #0d1f3c 0%, #0b0e17 100%)",
  "linear-gradient(160deg, #1a0d0d 0%, #0b0e17 100%)",
  "linear-gradient(160deg, #0d1a14 0%, #0b0e17 100%)",
  "linear-gradient(160deg, #1a1200 0%, #0b0e17 100%)",
  "linear-gradient(160deg, #130d1a 0%, #0b0e17 100%)",
];

export const NewsItem: React.FC<Props> = ({ item, index, total }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const slideY = interpolate(frame, [0, fps * 0.5], [40, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const opacity = interpolate(frame, [0, fps * 0.4], [0, 1], { extrapolateRight: "clamp" });

  const textOpacity = interpolate(frame, [fps * 0.35, fps * 0.8], [0, 1], { extrapolateRight: "clamp" });
  const textY = interpolate(frame, [fps * 0.35, fps * 0.8], [16, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const lowerOpacity = interpolate(frame, [fps * 0.6, fps * 1.0], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{ width: "100%", height: "100%", background: COLORS.bg, position: "relative", overflow: "hidden" }}>
      {/* 頂部紅條 */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 6, background: COLORS.accent }} />

      {/* 圖片區（上半 55%）*/}
      <div
        style={{
          position: "absolute", top: 6, left: 0, right: 0,
          height: "55%", overflow: "hidden",
          transform: `translateY(${slideY * 0.5}px)`, opacity,
        }}
      >
        {item.image_url ? (
          <Img src={staticFile(item.image_url)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <div
            style={{
              width: "100%", height: "100%",
              background: BG_GRADIENTS[index % BG_GRADIENTS.length],
              display: "flex", alignItems: "center", justifyContent: "center",
            }}
          >
            {/* 佔位：大號碼 */}
            <div
              style={{
                fontSize: 180, fontFamily: fontEn, fontWeight: 900,
                color: "#ffffff08", lineHeight: 1, userSelect: "none",
              }}
            >
              {String(index + 1).padStart(2, "0")}
            </div>
          </div>
        )}

        {/* 漸層遮罩 */}
        <div
          style={{
            position: "absolute", bottom: 0, left: 0, right: 0, height: "25%",
            background: `linear-gradient(to bottom, transparent, ${COLORS.bg})`,
          }}
        />
      </div>

      {/* 文字區（下半，從 55% 處開始往下填滿）*/}
      <div
        style={{
          position: "absolute", top: "55%", left: 0, right: 0, bottom: 60,
          padding: "40px 52px 20px",
          display: "flex", flexDirection: "column", justifyContent: "center",
          opacity: textOpacity, transform: `translateY(${textY}px)`,
        }}
      >
        {/* 新聞編號標籤 */}
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 24 }}>
          <div
            style={{
              background: COLORS.accent, color: COLORS.white,
              fontSize: 34, fontFamily: fontTC, fontWeight: 700,
              padding: "8px 24px", borderRadius: 4, letterSpacing: "0.05em",
            }}
          >
            {["第一篇", "第二篇", "第三篇", "第四篇", "第五篇"][index] ?? `第${index + 1}篇`}
          </div>
          <div style={{ flex: 1, height: 1, background: COLORS.border }} />
        </div>

        {/* 標題 */}
        <div
          style={{
            fontSize: 64, color: COLORS.white,
            fontFamily: fontTC, fontWeight: 700,
            lineHeight: 1.4, marginBottom: 28,
          }}
        >
          {item.headline}
        </div>

        {/* 摘要 */}
        <div
          style={{
            opacity: lowerOpacity,
            fontSize: 40, color: COLORS.muted,
            fontFamily: fontTC, lineHeight: 1.7,
          }}
        >
          {item.summary}
        </div>
      </div>

      {/* 底部 ticker */}
      <div
        style={{
          position: "absolute", bottom: 0, left: 0, right: 0,
          height: 52, background: COLORS.accentBlue,
          display: "flex", alignItems: "center", padding: "0 28px",
          gap: 24,
        }}
      >
        <div style={{ fontSize: 13, color: COLORS.white, fontFamily: fontEn, fontWeight: 700, letterSpacing: "0.1em", flexShrink: 0 }}>
          BREAKING
        </div>
        <div style={{ width: 1, height: 20, background: "rgba(255,255,255,0.3)" }} />
        <div style={{ fontSize: 14, color: COLORS.white, fontFamily: fontTC, opacity: 0.9 }}>
          {item.headline}
        </div>
      </div>
    </div>
  );
};
