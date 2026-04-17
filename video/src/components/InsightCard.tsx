import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import { COLORS, fontTC, fontEn } from "../theme";

interface Props {
  clashOrSync: string;
  investorReminder: string;
}

export const InsightCard: React.FC<Props> = ({ clashOrSync, investorReminder }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headerOpacity = interpolate(frame, [0, fps * 0.5], [0, 1], { extrapolateRight: "clamp" });
  const headerY = interpolate(frame, [0, fps * 0.5], [24, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const insightOpacity = interpolate(frame, [fps * 0.5, fps * 1.0], [0, 1], { extrapolateRight: "clamp" });
  const insightY = interpolate(frame, [fps * 0.5, fps * 1.0], [20, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const reminderOpacity = interpolate(frame, [fps * 1.1, fps * 1.6], [0, 1], { extrapolateRight: "clamp" });
  const reminderY = interpolate(frame, [fps * 1.1, fps * 1.6], [20, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  return (
    <div style={{ width: "100%", height: "100%", background: COLORS.bg, position: "relative", overflow: "hidden" }}>
      {/* 頂部紅條 */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 6, background: COLORS.accent }} />

      {/* 背景裝飾 */}
      <div
        style={{
          position: "absolute", top: "30%", right: -80,
          width: 400, height: 400, borderRadius: "50%",
          background: `radial-gradient(circle, ${COLORS.accentBlue}18 0%, transparent 70%)`,
        }}
      />

      <div
        style={{
          position: "absolute", inset: 0,
          display: "flex", flexDirection: "column",
          padding: "72px 56px 72px", boxSizing: "border-box",
          justifyContent: "center", gap: 36,
        }}
      >
        {/* 標題 */}
        <div style={{ opacity: headerOpacity, transform: `translateY(${headerY}px)` }}>
          <div
            style={{
              fontSize: 13, color: COLORS.accent,
              fontFamily: fontEn, fontWeight: 700,
              letterSpacing: "0.2em", marginBottom: 10,
            }}
          >
            MARKET ANALYSIS
          </div>
          <div
            style={{
              fontSize: 44, color: COLORS.white,
              fontFamily: fontTC, fontWeight: 700, lineHeight: 1.2,
            }}
          >
            綜合洞察
          </div>
        </div>

        {/* 分隔線 */}
        <div
          style={{
            width: "100%", height: 1,
            background: `linear-gradient(90deg, ${COLORS.accent}, ${COLORS.accentBlue}, transparent)`,
            opacity: headerOpacity,
          }}
        />

        {/* 觀點分析 */}
        <div
          style={{
            opacity: insightOpacity,
            transform: `translateY(${insightY}px)`,
            background: COLORS.bgCard,
            border: `1px solid ${COLORS.border}`,
            borderLeft: `4px solid ${COLORS.accentBlue}`,
            borderRadius: "0 12px 12px 0",
            padding: "28px 32px",
          }}
        >
          <div
            style={{
              fontSize: 13, color: COLORS.accentBlue,
              fontFamily: fontEn, fontWeight: 700,
              letterSpacing: "0.12em", marginBottom: 14,
            }}
          >
            DUAL PERSPECTIVE
          </div>
          <div
            style={{
              fontSize: 24, color: COLORS.offWhite,
              fontFamily: fontTC, lineHeight: 1.8,
            }}
          >
            {clashOrSync}
          </div>
        </div>

        {/* 投資人提醒 */}
        <div
          style={{
            opacity: reminderOpacity,
            transform: `translateY(${reminderY}px)`,
            background: "#1a0e05",
            border: `1px solid #3a2010`,
            borderLeft: `4px solid ${COLORS.accentGold}`,
            borderRadius: "0 12px 12px 0",
            padding: "24px 32px",
          }}
        >
          <div
            style={{
              fontSize: 13, color: COLORS.accentGold,
              fontFamily: fontEn, fontWeight: 700,
              letterSpacing: "0.12em", marginBottom: 14,
              display: "flex", alignItems: "center", gap: 8,
            }}
          >
            <span>▲</span> INVESTOR REMINDER
          </div>
          <div
            style={{
              fontSize: 24, color: COLORS.offWhite,
              fontFamily: fontTC, lineHeight: 1.8,
            }}
          >
            {investorReminder}
          </div>
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
          FINANCIAL RADAR  ●  MARKET ANALYSIS  ●  FOR REFERENCE ONLY
        </div>
      </div>
    </div>
  );
};
