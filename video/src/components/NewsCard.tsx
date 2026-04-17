import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";

interface Props {
  title: string;
  sentiment: string;
  accentColor: string;
  keyInfo: string;
  keyInfoLabel: string;
  points: string[];
  strategy: string;
  side: "A" | "B";
}

const sentimentStyle = (sentiment: string): React.CSSProperties => {
  if (sentiment.includes("多") || sentiment.includes("樂觀")) {
    return { background: "#e8f5ee", color: "#1a6637" };
  }
  if (sentiment.includes("空") || sentiment.includes("悲觀")) {
    return { background: "#fce8e8", color: "#8b1a1a" };
  }
  return { background: "#f0ede8", color: "#666" };
};

export const NewsCard: React.FC<Props> = ({
  title,
  sentiment,
  accentColor,
  keyInfo,
  keyInfoLabel,
  points,
  strategy,
  side,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headerOpacity = interpolate(frame, [0, fps * 0.4], [0, 1], { extrapolateRight: "clamp" });
  const headerX = interpolate(frame, [0, fps * 0.4], [side === "A" ? -40 : 40, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const pointDelays = [fps * 0.5, fps * 0.8, fps * 1.1];

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "#f8f7f4",
        display: "flex",
        flexDirection: "column",
        padding: "70px 60px",
        boxSizing: "border-box",
      }}
    >
      {/* Header */}
      <div
        style={{
          opacity: headerOpacity,
          transform: `translateX(${headerX}px)`,
          marginBottom: 36,
        }}
      >
        <div
          style={{
            fontSize: 16,
            color: accentColor,
            fontFamily: "Helvetica Neue, Arial, sans-serif",
            fontWeight: 700,
            letterSpacing: "0.15em",
            marginBottom: 10,
          }}
        >
          {side === "A" ? "SOURCE A" : "SOURCE B"}
        </div>
        <div
          style={{
            fontSize: 42,
            color: "#111",
            fontFamily: "Helvetica Neue, Arial, sans-serif",
            fontWeight: 700,
            lineHeight: 1.2,
            marginBottom: 16,
          }}
        >
          {title}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div
            style={{
              ...sentimentStyle(sentiment),
              padding: "6px 18px",
              borderRadius: 20,
              fontSize: 18,
              fontFamily: "Helvetica Neue, Arial, sans-serif",
              fontWeight: 600,
            }}
          >
            {sentiment}
          </div>
        </div>
      </div>

      {/* 分隔線 */}
      <div
        style={{
          width: "100%",
          height: 2,
          background: accentColor,
          opacity: 0.3,
          marginBottom: 32,
        }}
      />

      {/* 關鍵資訊 */}
      <div
        style={{
          background: "#111",
          borderRadius: 12,
          padding: "20px 28px",
          marginBottom: 32,
          opacity: interpolate(frame, [fps * 0.3, fps * 0.7], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        <div
          style={{
            fontSize: 13,
            color: "#888",
            fontFamily: "Helvetica Neue, Arial, sans-serif",
            letterSpacing: "0.12em",
            marginBottom: 8,
          }}
        >
          {keyInfoLabel}
        </div>
        <div
          style={{
            fontSize: 22,
            color: "#f8f7f4",
            fontFamily: "Helvetica Neue, Arial, sans-serif",
            fontWeight: 600,
          }}
        >
          {keyInfo}
        </div>
      </div>

      {/* 重點列表 */}
      <div style={{ flex: 1, marginBottom: 28 }}>
        <div
          style={{
            fontSize: 14,
            color: accentColor,
            fontFamily: "Helvetica Neue, Arial, sans-serif",
            fontWeight: 700,
            letterSpacing: "0.1em",
            marginBottom: 16,
          }}
        >
          KEY POINTS
        </div>
        {points.map((point, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 14,
              marginBottom: 18,
              opacity: interpolate(frame, [pointDelays[i], pointDelays[i] + fps * 0.4], [0, 1], {
                extrapolateRight: "clamp",
              }),
              transform: `translateX(${interpolate(frame, [pointDelays[i], pointDelays[i] + fps * 0.4], [20, 0], {
                extrapolateRight: "clamp",
                easing: Easing.out(Easing.cubic),
              })}px)`,
            }}
          >
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: accentColor,
                marginTop: 8,
                flexShrink: 0,
              }}
            />
            <div
              style={{
                fontSize: 22,
                color: "#1a1a1a",
                fontFamily: "Helvetica Neue, Arial, sans-serif",
                lineHeight: 1.6,
              }}
            >
              {point}
            </div>
          </div>
        ))}
      </div>

      {/* 策略 */}
      <div
        style={{
          background: accentColor + "15",
          borderLeft: `4px solid ${accentColor}`,
          borderRadius: "0 8px 8px 0",
          padding: "18px 24px",
          opacity: interpolate(frame, [fps * 1.4, fps * 1.8], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        <div
          style={{
            fontSize: 13,
            color: accentColor,
            fontFamily: "Helvetica Neue, Arial, sans-serif",
            fontWeight: 700,
            letterSpacing: "0.1em",
            marginBottom: 8,
          }}
        >
          STRATEGY
        </div>
        <div
          style={{
            fontSize: 20,
            color: "#1a1a1a",
            fontFamily: "Helvetica Neue, Arial, sans-serif",
            lineHeight: 1.6,
          }}
        >
          {strategy}
        </div>
      </div>
    </div>
  );
};
