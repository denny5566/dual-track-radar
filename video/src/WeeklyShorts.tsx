import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  Series,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import weeklyData from "./data/weekly_short.json";
import weeklyDurationsRaw from "./data/weekly_durations.json";
import { fontEn, fontTC } from "./theme";

type WeeklyEvent = {
  title: string;
  news_sentence: string;
  market_variable: string;
  importance_reason?: string;
  watch_point?: string;
  bridge_sentence?: string;
  image_url?: string;
  image_source?: string;
};

type WeeklyShortData = {
  meta: { week_start: string; week_end: string };
  events: WeeklyEvent[];
  calendar_line: string;
  storyline?: string;
  weekly_summary: string;
  cta: string;
};

const data = weeklyData as WeeklyShortData;
const durations = weeklyDurationsRaw as Record<string, number>;
const FPS = 30;
const MIN_SCENE_FRAMES = 120;
const BUFFER_FRAMES = 18;

const palette = {
  bg: "#0a0a0a",
  surface: "#111111",
  surface2: "#181818",
  border: "rgba(255,255,255,0.13)",
  text: "#f2f2f2",
  muted: "#b8b8b8",
  red: "#e5402a",
  green: "#00c98d",
  blue: "#7db1ff",
  gold: "#f4a621",
};

const firstMarketVariable = (event: WeeklyEvent) => event.market_variable.split("、")[0] || "市場情緒";

const storyline =
  data.storyline ||
  `本週主線是${data.events
    .slice(0, 4)
    .map(firstMarketVariable)
    .join("、")}如何一起影響台股與美股的資金情緒。`;

function framesFor(key: string, fallbackSeconds: number) {
  return Math.max(MIN_SCENE_FRAMES, Math.ceil((durations[key] ?? fallbackSeconds) * FPS) + BUFFER_FRAMES);
}

function fade(frame: number, start: number, end: number) {
  return interpolate(frame, [start, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
}

const Header: React.FC = () => (
  <div
    style={{
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
      height: 118,
      borderBottom: `1px solid ${palette.border}`,
      background: "rgba(10,10,10,0.96)",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "0 66px",
      fontFamily: fontTC,
      zIndex: 10,
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
      <div
        style={{
          width: 42,
          height: 42,
          borderRadius: "50%",
          border: `2px solid ${palette.red}`,
          position: "relative",
        }}
      >
        <div style={{ position: "absolute", inset: 11, borderRadius: "50%", background: palette.red }} />
      </div>
      <div style={{ fontSize: 40, fontWeight: 900, color: palette.text }}>財經雷達</div>
    </div>
    <div style={{ fontFamily: fontEn, color: palette.muted, fontSize: 27, fontWeight: 800 }}>
      {data.meta.week_start.replace(/-/g, ".")} - {data.meta.week_end.replace(/-/g, ".")}
    </div>
  </div>
);

const Ticker: React.FC = () => (
  <div
    style={{
      position: "absolute",
      bottom: 0,
      left: 0,
      right: 0,
      height: 70,
      background: palette.red,
      color: "white",
      display: "flex",
      alignItems: "center",
      overflow: "hidden",
      fontFamily: fontEn,
      fontWeight: 800,
      fontSize: 20,
      letterSpacing: "0.04em",
      zIndex: 10,
    }}
  >
    <div style={{ paddingLeft: 34, whiteSpace: "nowrap" }}>
      WEEKLY MARKET RADAR • TAIWAN + US MARKETS • RESEARCH BRIEF
    </div>
  </div>
);

const Background: React.FC = () => (
  <AbsoluteFill style={{ background: palette.bg }}>
    <div
      style={{
        position: "absolute",
        inset: 0,
        background:
          "linear-gradient(180deg, rgba(255,255,255,0.03), transparent 28%), repeating-linear-gradient(90deg, rgba(255,255,255,0.035) 0 1px, transparent 1px 76px), repeating-linear-gradient(0deg, rgba(255,255,255,0.025) 0 1px, transparent 1px 64px)",
      }}
    />
    <svg viewBox="0 0 1080 1920" style={{ position: "absolute", inset: 0, opacity: 0.38 }}>
      <path
        d="M80 1330 C210 1280 320 1370 450 1260 C580 1150 700 1225 815 1080 C910 960 995 1010 1080 880"
        fill="none"
        stroke={palette.blue}
        strokeWidth="4"
      />
      <path
        d="M0 1440 C250 1330 480 1510 720 1280 C870 1130 1000 1160 1080 1040"
        fill="none"
        stroke={palette.green}
        strokeWidth="3"
        opacity="0.55"
      />
    </svg>
  </AbsoluteFill>
);

const OpeningScene: React.FC = () => {
  const frame = useCurrentFrame();
  const op = fade(frame, 0, 18);
  const y = interpolate(frame, [0, 28], [28, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  return (
    <AbsoluteFill>
      <Background />
      <Header />
      <div
        style={{
          position: "absolute",
          left: 64,
          right: 64,
          top: 385,
          opacity: op,
          transform: `translateY(${y}px)`,
          fontFamily: fontTC,
        }}
      >
        <div
          style={{
            display: "inline-flex",
            background: "rgba(229,64,42,0.16)",
            border: "1px solid rgba(229,64,42,0.38)",
            color: palette.red,
            padding: "10px 20px",
            borderRadius: 6,
            fontFamily: fontEn,
            fontSize: 26,
            fontWeight: 800,
            letterSpacing: "0.08em",
            marginBottom: 36,
          }}
        >
          WEEKLY SHORTS
        </div>
        <h1 style={{ margin: 0, color: palette.text, fontSize: 105, lineHeight: 1.12, fontWeight: 900 }}>
          本週市場雷達
        </h1>
        <div style={{ width: 132, height: 6, background: palette.red, margin: "42px 0", borderRadius: 4 }} />
        <p style={{ margin: 0, color: "#d8d8d8", fontSize: 50, lineHeight: 1.38, fontWeight: 780 }}>
          不是五則新聞，是一條市場主線
        </p>
        <div
          style={{
            marginTop: 54,
            borderLeft: `8px solid ${palette.red}`,
            background: "rgba(255,255,255,0.055)",
            padding: "28px 30px",
            borderRadius: 6,
            color: palette.text,
            fontSize: 42,
            lineHeight: 1.38,
            fontWeight: 820,
          }}
        >
          {storyline}
        </div>
      </div>
      <Ticker />
    </AbsoluteFill>
  );
};

const eventWatchPoint = (event: WeeklyEvent) =>
  event.watch_point || `下週觀察 ${event.market_variable.split("、")[0] || "資金流向"} 是否延續。`;

const eventBridge = (event: WeeklyEvent, index: number) => {
  if (event.bridge_sentence) return event.bridge_sentence;
  const variable = firstMarketVariable(event);
  const templates = [
    `先從${variable}看起，這會決定市場願意承擔多少風險。`,
    `接著看${variable}，它是成長股能否接棒的關鍵。`,
    `第三步看${variable}，它會回頭影響通膨與利率想像。`,
    `再來看${variable}，資金流向會放大前面幾個變數。`,
    `最後看${variable}，確認主線是否外溢到亞洲市場。`,
  ];
  return templates[index] || `接著看${variable}。`;
};

const StoryBlock: React.FC<{ label: string; value: string; accent: string; muted?: boolean }> = ({
  label,
  value,
  accent,
  muted = false,
}) => (
  <div
    style={{
      display: "grid",
      gridTemplateColumns: "124px 1fr",
      columnGap: 24,
      alignItems: "start",
      borderTop: `1px solid ${palette.border}`,
      paddingTop: 20,
    }}
  >
    <div
      style={{
        color: accent,
        fontFamily: fontEn,
        fontSize: 19,
        fontWeight: 900,
        letterSpacing: "0.08em",
        lineHeight: 1.3,
      }}
    >
      {label}
    </div>
    <div style={{ color: muted ? "#d6d6d6" : palette.text, fontSize: 34, lineHeight: 1.38, fontWeight: muted ? 720 : 820 }}>
      {value}
    </div>
  </div>
);

const EventScene: React.FC<{ event: WeeklyEvent; index: number }> = ({ event, index }) => {
  const frame = useCurrentFrame();
  const op = fade(frame, 0, 16);
  const y = interpolate(frame, [0, 20], [34, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const colors = [palette.blue, palette.green, palette.gold, palette.red, palette.blue];
  const accent = colors[index % colors.length];

  return (
    <AbsoluteFill>
      <Background />
      <Header />
      <div
        style={{
          position: "absolute",
          top: 178,
          left: 64,
          right: 64,
          opacity: op,
          transform: `translateY(${y}px)`,
          fontFamily: fontTC,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 22 }}>
          <div style={{ color: accent, fontFamily: fontEn, fontSize: 26, fontWeight: 850 }}>
            CHAPTER 0{index + 1}
          </div>
          <div style={{ color: palette.muted, fontFamily: fontEn, fontSize: 24, fontWeight: 800 }}>MARKET THREAD</div>
        </div>
        <div
          style={{
            background: "rgba(17,17,17,0.95)",
            border: `1px solid ${palette.border}`,
            borderLeft: `7px solid ${accent}`,
            borderRadius: 8,
            padding: 34,
            minHeight: 1170,
            boxShadow: "0 22px 70px rgba(0,0,0,0.42)",
          }}
        >
          <div
            style={{
              position: "relative",
              height: 390,
              borderRadius: 6,
              overflow: "hidden",
              marginBottom: 30,
              background: palette.surface2,
              border: `1px solid ${palette.border}`,
            }}
          >
            {event.image_url ? (
              <Img src={staticFile(event.image_url)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            ) : null}
            <div
              style={{
                position: "absolute",
                inset: 0,
                background:
                  "linear-gradient(180deg, rgba(0,0,0,0.1), rgba(0,0,0,0.68)), linear-gradient(90deg, rgba(10,10,10,0.56), transparent)",
              }}
            />
            <div
              style={{
                position: "absolute",
                left: 26,
                bottom: 22,
                color: "rgba(255,255,255,0.8)",
                fontFamily: fontEn,
                fontSize: 18,
                fontWeight: 800,
                letterSpacing: "0.07em",
              }}
            >
              IMAGE: {event.image_source || "PEXELS"}
            </div>
          </div>

          <div
            style={{
              color: accent,
              fontSize: 36,
              lineHeight: 1.35,
              fontWeight: 850,
              marginBottom: 22,
            }}
          >
            {eventBridge(event, index)}
          </div>
          <h2 style={{ margin: "0 0 30px", color: palette.text, fontSize: 56, lineHeight: 1.18, fontWeight: 900 }}>
            {event.title}
          </h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 20 }}>
            <StoryBlock label="EVENT" value={event.news_sentence} accent={accent} />
            <StoryBlock
              label="LINK"
              value={event.importance_reason || `這一段會牽動${event.market_variable}，並影響整體市場主線。`}
              accent={palette.gold}
              muted
            />
            <StoryBlock label="WATCH" value={eventWatchPoint(event)} accent={palette.green} muted />
          </div>
        </div>
      </div>
      <Ticker />
    </AbsoluteFill>
  );
};

const ClosingScene: React.FC = () => {
  const frame = useCurrentFrame();
  const op = fade(frame, 0, 18);
  return (
    <AbsoluteFill>
      <Background />
      <Header />
      <div style={{ position: "absolute", left: 64, right: 64, top: 315, opacity: op, fontFamily: fontTC }}>
        <div style={{ color: palette.red, fontFamily: fontEn, fontSize: 28, fontWeight: 850, marginBottom: 36 }}>
          WEEKLY CONTEXT
        </div>
        <div style={{ color: palette.text, fontSize: 60, lineHeight: 1.45, fontWeight: 850, marginBottom: 54 }}>
          {storyline}
        </div>
        <div
          style={{
            background: palette.surface,
            border: `1px solid ${palette.border}`,
            borderRadius: 8,
            padding: "42px 44px",
            marginBottom: 42,
          }}
        >
          <div style={{ color: palette.gold, fontSize: 48, lineHeight: 1.4, fontWeight: 850 }}>{data.calendar_line}</div>
        </div>
        <div style={{ color: "#d8d8d8", fontSize: 45, lineHeight: 1.45, fontWeight: 760 }}>{data.cta}</div>
      </div>
      <Ticker />
    </AbsoluteFill>
  );
};

export const WeeklyShorts: React.FC = () => (
  <AbsoluteFill>
    <Series>
      <Series.Sequence durationInFrames={framesFor("opening", 5.2)}>
        <Audio src={staticFile("weekly_audio/opening.mp3")} />
        <OpeningScene />
      </Series.Sequence>
      {data.events.slice(0, 5).map((event, index) => {
        const key = `event_${String(index + 1).padStart(2, "0")}`;
        return (
          <Series.Sequence key={event.title} durationInFrames={framesFor(key, 10.2)}>
            <Audio src={staticFile(`weekly_audio/${key}.mp3`)} />
            <EventScene event={event} index={index} />
          </Series.Sequence>
        );
      })}
      <Series.Sequence durationInFrames={framesFor("closing", 10.5)}>
        <Audio src={staticFile("weekly_audio/closing.mp3")} />
        <ClosingScene />
      </Series.Sequence>
    </Series>
  </AbsoluteFill>
);
