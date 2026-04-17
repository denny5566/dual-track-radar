import { loadFont as loadNotoSansTC } from "@remotion/google-fonts/NotoSansTC";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";

export const { fontFamily: fontTC } = loadNotoSansTC();
export const { fontFamily: fontEn } = loadInter();

export const COLORS = {
  bg: "#0b0e17",           // 深藍黑（主背景）
  bgCard: "#111827",       // 卡片背景
  bgStrip: "#141a27",      // 條帶背景
  accent: "#e63946",       // 新聞紅
  accentBlue: "#1d6dff",   // 新聞藍
  accentGold: "#f4a621",   // 數據金
  white: "#ffffff",
  offWhite: "#e8eaf0",
  muted: "#8892a4",
  border: "#1e2537",
  ticker: "#e63946",
};
