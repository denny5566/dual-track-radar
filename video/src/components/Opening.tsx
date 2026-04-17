import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing, Img, staticFile } from "remotion";
import { COLORS, fontTC, fontEn } from "../theme";

// ── 雷達上的固定訊號點（角度從正上方起，順時針） ────────────────────────────
const BLIPS = [
  { angle: 42,  r: 0.62 },
  { angle: 118, r: 0.41 },
  { angle: 197, r: 0.78 },
  { angle: 253, r: 0.50 },
  { angle: 315, r: 0.33 },
];

interface RadarProps { frame: number; fps: number }

const Radar: React.FC<RadarProps> = ({ frame, fps }) => {
  const size  = 620;
  const cx    = size / 2;
  const cy    = size / 2;
  const maxR  = size / 2 - 24;

  // 每 4 秒轉一圈
  const rotation = (frame / fps / 4) * 360;

  // 掃描扇形尾跡路徑（從正上方往逆時針拉 80°）
  const trailDeg = 80;
  const trailRad = (-trailDeg * Math.PI) / 180;
  const ex = cx + maxR * Math.sin(trailRad);
  const ey = cy - maxR * Math.cos(trailRad);
  const trailPath = `M ${cx} ${cy} L ${cx} ${cy - maxR} A ${maxR} ${maxR} 0 0 0 ${ex.toFixed(2)} ${ey.toFixed(2)} Z`;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* 外圓 */}
      <circle cx={cx} cy={cy} r={maxR}        fill="none" stroke="rgba(0,200,255,0.28)" strokeWidth={1.5} />
      {/* 內圓 × 2 */}
      <circle cx={cx} cy={cy} r={maxR * 0.66} fill="none" stroke="rgba(0,200,255,0.18)" strokeWidth={1} />
      <circle cx={cx} cy={cy} r={maxR * 0.33} fill="none" stroke="rgba(0,200,255,0.18)" strokeWidth={1} />

      {/* 十字準線 */}
      <line x1={cx} y1={cy - maxR - 6} x2={cx} y2={cy + maxR + 6} stroke="rgba(0,200,255,0.14)" strokeWidth={1} />
      <line x1={cx - maxR - 6} y1={cy} x2={cx + maxR + 6} y2={cy} stroke="rgba(0,200,255,0.14)" strokeWidth={1} />

      {/* 訊號點：掃描線經過後亮起，然後衰減 */}
      {BLIPS.map((blip, i) => {
        const diff    = ((rotation - blip.angle) % 360 + 360) % 360;
        const decay   = 100; // 衰減範圍（度）
        const opacity = diff < decay ? (1 - diff / decay) * 0.95 : 0;
        // 掃描剛過時稍微放大
        const dotR    = diff < 15 ? 4 + (1 - diff / 15) * 4 : 4;
        const rad     = ((blip.angle - 90) * Math.PI) / 180;
        const bx      = cx + maxR * blip.r * Math.cos(rad);
        const by      = cy + maxR * blip.r * Math.sin(rad);
        return (
          <circle
            key={i}
            cx={bx} cy={by} r={dotR}
            fill={`rgba(0,255,160,${opacity.toFixed(3)})`}
          />
        );
      })}

      {/* 旋轉掃描群組 */}
      <g transform={`rotate(${rotation.toFixed(2)}, ${cx}, ${cy})`}>
        {/* 尾跡扇形 */}
        <path d={trailPath} fill="rgba(0,255,160,0.07)" />
        {/* 掃描線 */}
        <line
          x1={cx} y1={cy}
          x2={cx} y2={cy - maxR}
          stroke="rgba(0,255,160,0.85)"
          strokeWidth={2}
          strokeLinecap="round"
        />
        {/* 掃描線頂端光點 */}
        <circle cx={cx} cy={cy - maxR} r={4} fill="rgba(0,255,160,0.9)" />
      </g>

      {/* 中心點 */}
      <circle cx={cx} cy={cy} r={5} fill="rgba(0,220,255,0.9)" />
    </svg>
  );
};

// ── Opening 主元件 ────────────────────────────────────────────────────────────

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

  // 雷達淡入
  const radarOpacity = interpolate(frame, [0, fps * 0.8], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{ width: "100%", height: "100%", background: COLORS.bg, position: "relative", overflow: "hidden" }}>
      {/* 背景圖 */}
      <div style={{ position: "absolute", inset: 0, opacity: bgOpacity * 0.45 }}>
        <Img
          src={staticFile("opening_bg.jpg")}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
          onError={() => {}}
        />
      </div>
      {/* 深色遮罩 */}
      <div style={{ position: "absolute", inset: 0, background: "rgba(11,14,23,0.65)" }} />
      {/* 斜線裝飾 */}
      <div
        style={{
          position: "absolute", inset: 0, opacity: bgOpacity * 0.04,
          background: "repeating-linear-gradient(135deg, #ffffff 0px, #ffffff 1px, transparent 1px, transparent 40px)",
        }}
      />

      {/* ── 雷達動畫（右側背景層）─────────────────────────────────────────── */}
      <div
        style={{
          position: "absolute",
          right: -60, top: "50%",
          transform: "translateY(-50%)",
          opacity: radarOpacity * 0.55,
          pointerEvents: "none",
        }}
      >
        <Radar frame={frame} fps={fps} />
      </div>

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
        <div style={{ opacity: logoOpacity, display: "flex", alignItems: "center", gap: 10, marginBottom: 40 }}>
          <div
            style={{
              opacity: liveOpacity,
              background: COLORS.accent, color: COLORS.white,
              fontSize: 18, fontFamily: fontEn, fontWeight: 700,
              letterSpacing: "0.15em", padding: "6px 18px", borderRadius: 4,
            }}
          >
            LIVE
          </div>
          <div style={{ color: COLORS.muted, fontSize: 20, fontFamily: fontEn, letterSpacing: "0.1em" }}>
            FINANCIAL BRIEFING
          </div>
        </div>

        {/* 品牌名 */}
        <div style={{ opacity: logoOpacity, transform: `translateY(${logoY}px)`, textAlign: "center", marginBottom: 32 }}>
          <div style={{ fontSize: 96, color: COLORS.white, fontFamily: fontTC, fontWeight: 700, letterSpacing: "0.08em", lineHeight: 1.2 }}>
            雙軌財經情報雷達
          </div>
          <div style={{ fontSize: 24, color: COLORS.muted, fontFamily: fontEn, letterSpacing: "0.2em", marginTop: 10, fontWeight: 300 }}>
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
        <div style={{ opacity: logoOpacity, fontSize: 24, color: COLORS.accentGold, fontFamily: fontEn, letterSpacing: "0.15em", marginBottom: 48, fontWeight: 600 }}>
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
          <div style={{ fontSize: 17, color: COLORS.accent, fontFamily: fontEn, fontWeight: 700, letterSpacing: "0.15em", marginBottom: 14 }}>
            TODAY'S FOCUS
          </div>
          <div style={{ fontSize: 46, color: COLORS.offWhite, fontFamily: fontTC, lineHeight: 1.7, fontWeight: 500 }}>
            {dailyFocus}
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
        <div style={{ fontSize: 19, color: COLORS.white, fontFamily: fontEn, fontWeight: 700, letterSpacing: "0.1em" }}>
          FINANCIAL RADAR  ●  DAILY REPORT  ●  {date.replace(/-/g, ".")}
        </div>
      </div>
    </div>
  );
};
