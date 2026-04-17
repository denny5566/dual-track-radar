import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import { COLORS, fontTC, fontEn } from "../theme";

interface Props {
  date: string;
  dailyFocus: string;
}

export const Opening: React.FC<Props> = ({ date, dailyFocus }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const bgOpacity = interpolate(frame, [0, fps * 0.3], [0, 1], { extrapolateRight: "clamp" });

  const logoOpacity = interpolate(frame, [fps * 0.2, fps * 0.6], [0, 1], { extrapolateRight: "clamp" });
  const logoY = interpolate(frame, [fps * 0.2, fps * 0.6], [24, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const lineW = interpolate(frame, [fps * 0.5, fps * 0.9], [0, 100], { extrapolateRight: "clamp" });

  const focusOpacity = interpolate(frame, [fps * 0.7, fps * 1.2], [0, 1], { extrapolateRight: "clamp" });
  const focusY = interpolate(frame, [fps * 0.7, fps * 1.2], [20, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const liveOpacity = interpolate(
    frame % (fps * 1.2),
    [0, fps * 0.5, fps * 0.6, fps * 1.1],
    [1, 1, 0.2, 0.2],
    { extrapolateRight: "clamp" }
  );

  return (
    <div style={{ width: "100%", height: "100%", background: COLORS.bg, position: "relative", overflow: "hidden" }}>
      {/* 背景斜線裝飾 */}
      <div
        style={{
          position: "absolute", inset: 0, opacity: bgOpacity * 0.07,
          background: "repeating-linear-gradient(135deg, #ffffff 0px, #ffffff 1px, transparent 1px, transparent 40px)",
        }}
      />

      {/* 頂部紅色條 */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 6, background: COLORS.accent }} />

      {/* 主內容 */}
      <div
        style={{
          position: "absolute", inset: 0,
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          padding: "80px 64px", boxSizing: "border-box",
        }}
      >
        {/* LIVE 標籤 */}
        <div
          style={{
            opacity: logoOpacity,
            display: "flex", alignItems: "center", gap: 10,
            marginBottom: 40,
          }}
        >
          <div
            style={{
              opacity: liveOpacity,
              background: COLORS.accent,
              color: COLORS.white,
              fontSize: 14, fontFamily: fontEn, fontWeight: 700,
              letterSpacing: "0.15em",
              padding: "5px 14px", borderRadius: 4,
            }}
          >
            LIVE
          </div>
          <div style={{ color: COLORS.muted, fontSize: 15, fontFamily: fontEn, letterSpacing: "0.1em" }}>
            FINANCIAL BRIEFING
          </div>
        </div>

        {/* 品牌名 */}
        <div
          style={{
            opacity: logoOpacity,
            transform: `translateY(${logoY}px)`,
            textAlign: "center", marginBottom: 32,
          }}
        >
          <div
            style={{
              fontSize: 56, color: COLORS.white,
              fontFamily: fontTC, fontWeight: 700,
              letterSpacing: "0.08em", lineHeight: 1.2,
            }}
          >
            雙軌財經情報雷達
          </div>
          <div
            style={{
              fontSize: 18, color: COLORS.muted,
              fontFamily: fontEn, letterSpacing: "0.2em",
              marginTop: 10, fontWeight: 300,
            }}
          >
            DUAL TRACK FINANCIAL RADAR
          </div>
        </div>

        {/* 分隔線 */}
        <div
          style={{
            width: `${lineW}%`, height: 2,
            background: `linear-gradient(90deg, transparent, ${COLORS.accent}, transparent)`,
            marginBottom: 32,
          }}
        />

        {/* 日期 */}
        <div
          style={{
            opacity: logoOpacity,
            fontSize: 18, color: COLORS.accentGold,
            fontFamily: fontEn, letterSpacing: "0.15em",
            marginBottom: 48, fontWeight: 600,
          }}
        >
          {date.replace(/-/g, ".")}
        </div>

        {/* 今日焦點 */}
        <div
          style={{
            opacity: focusOpacity,
            transform: `translateY(${focusY}px)`,
            width: "100%",
            background: COLORS.bgCard,
            border: `1px solid ${COLORS.border}`,
            borderLeft: `4px solid ${COLORS.accent}`,
            borderRadius: "0 12px 12px 0",
            padding: "28px 36px",
          }}
        >
          <div
            style={{
              fontSize: 13, color: COLORS.accent,
              fontFamily: fontEn, fontWeight: 700,
              letterSpacing: "0.15em", marginBottom: 14,
            }}
          >
            TODAY'S FOCUS
          </div>
          <div
            style={{
              fontSize: 28, color: COLORS.offWhite,
              fontFamily: fontTC, lineHeight: 1.7, fontWeight: 500,
            }}
          >
            {dailyFocus}
          </div>
        </div>
      </div>

      {/* 底部 ticker 條 */}
      <div
        style={{
          position: "absolute", bottom: 0, left: 0, right: 0,
          height: 52, background: COLORS.accent,
          display: "flex", alignItems: "center", padding: "0 28px",
        }}
      >
        <div style={{ fontSize: 15, color: COLORS.white, fontFamily: fontEn, fontWeight: 700, letterSpacing: "0.1em" }}>
          FINANCIAL RADAR  ●  DAILY REPORT  ●  {date.replace(/-/g, ".")}
        </div>
      </div>
    </div>
  );
};
