import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing, Img, staticFile } from "remotion";
import { COLORS, fontTC, fontEn } from "../theme";

interface Props {
  date: string;
}

export const Ending: React.FC<Props> = ({ date }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const opacity = interpolate(frame, [0, fps * 0.5], [0, 1], { extrapolateRight: "clamp" });
  const scale = interpolate(frame, [0, fps * 0.5], [0.95, 1], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const tagOpacity = interpolate(frame, [fps * 0.6, fps * 1.0], [0, 1], { extrapolateRight: "clamp" });
  const disclaimerOpacity = interpolate(frame, [fps * 1.0, fps * 1.4], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{ width: "100%", height: "100%", background: COLORS.bg, position: "relative", overflow: "hidden" }}>
      {/* 背景圖 */}
      <div style={{ position: "absolute", inset: 0, opacity: 0.2 }}>
        <Img
          src={staticFile("ending_bg.jpg")}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
          onError={() => {}}
        />
      </div>
      {/* 深色遮罩 */}
      <div style={{ position: "absolute", inset: 0, background: "rgba(11,14,23,0.70)" }} />

      {/* 頂部紅條 */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 6, background: COLORS.accent }} />

      <div
        style={{
          position: "absolute", inset: 0,
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          padding: "80px 56px", boxSizing: "border-box",
        }}
      >
        {/* 品牌 */}
        <div
          style={{
            opacity, transform: `scale(${scale})`,
            textAlign: "center", marginBottom: 48,
          }}
        >
          <div
            style={{
              width: 60, height: 4, background: COLORS.accent,
              margin: "0 auto 24px", borderRadius: 2,
            }}
          />
          <div
            style={{
              fontSize: 20, color: COLORS.muted,
              fontFamily: fontEn, letterSpacing: "0.25em",
              marginBottom: 14, fontWeight: 300,
            }}
          >
            DUAL TRACK FINANCIAL RADAR
          </div>
          <div
            style={{
              fontSize: 64, color: COLORS.white,
              fontFamily: fontTC, fontWeight: 700,
              lineHeight: 1.25, marginBottom: 20,
            }}
          >
            雙軌財經情報雷達
          </div>
          <div
            style={{
              fontSize: 16, color: COLORS.accentGold,
              fontFamily: fontEn, letterSpacing: "0.1em", fontWeight: 600,
            }}
          >
            {date.replace(/-/g, ".")}  DAILY REPORT
          </div>
          <div
            style={{
              width: 60, height: 4,
              background: `linear-gradient(90deg, ${COLORS.accentBlue}, ${COLORS.accent})`,
              margin: "24px auto 0", borderRadius: 2,
            }}
          />
        </div>

        {/* Hashtags */}
        <div
          style={{
            opacity: tagOpacity,
            display: "flex", gap: 12,
            flexWrap: "wrap", justifyContent: "center",
            marginBottom: 40,
          }}
        >
          {["#雙軌財經雷達", "#台股", "#投資分析", "#財經"].map((tag) => (
            <div
              key={tag}
              style={{
                background: COLORS.bgCard,
                border: `1px solid ${COLORS.border}`,
                color: COLORS.muted,
                padding: "8px 20px", borderRadius: 20,
                fontSize: 15, fontFamily: fontTC,
              }}
            >
              {tag}
            </div>
          ))}
        </div>

        {/* 免責聲明 */}
        <div
          style={{
            opacity: disclaimerOpacity,
            fontSize: 14, color: "#3a4257",
            fontFamily: fontTC, textAlign: "center", lineHeight: 1.7,
          }}
        >
          本內容僅供參考，非投資建議。投資有風險，請審慎評估。
        </div>
      </div>

      {/* 底部 ticker */}
      <div
        style={{
          position: "absolute", bottom: 0, left: 0, right: 0,
          height: 52, background: COLORS.accent,
          display: "flex", alignItems: "center", padding: "0 28px",
        }}
      >
        <div style={{ fontSize: 14, color: COLORS.white, fontFamily: fontEn, fontWeight: 700, letterSpacing: "0.1em" }}>
          FINANCIAL RADAR  ●  DAILY REPORT  ●  {date.replace(/-/g, ".")}
        </div>
      </div>
    </div>
  );
};
