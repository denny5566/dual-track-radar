"""
Weekly Market Shorts pipeline.

Creates a YouTube Shorts-oriented weekly market brief:
API news/calendar collection -> event selection -> Chinese script -> Remotion render
-> Discord-reviewed YouTube unlisted publish.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from mutagen.mp3 import MP3

from config import BASE_DIR

load_dotenv()

log = logging.getLogger(__name__)

WEEKLY_DATA_PATH = BASE_DIR / "video" / "src" / "data" / "weekly_short.json"
WEEKLY_AUDIO_PATH = BASE_DIR / "video" / "public" / "audio" / "weekly_short.mp3"
WEEKLY_AUDIO_DIR = BASE_DIR / "video" / "public" / "weekly_audio"
WEEKLY_DURATIONS_PATH = BASE_DIR / "video" / "src" / "data" / "weekly_durations.json"
WEEKLY_OUTPUT_PATH = BASE_DIR / "video" / "out" / "weekly_short.mp4"
WEEKLY_PENDING_FILE = BASE_DIR / "data" / "pending_weekly_short.json"
WEEKLY_PUBLISH_LOG = BASE_DIR / "data" / "weekly_short_publish_log.json"
WEEKLY_IMAGE_DIR = BASE_DIR / "video" / "public" / "weekly"

CTA_TEXT = "完整事件整理與下週經濟日曆，放在說明欄。"
DISCLAIMER = "本內容僅供市場資訊整理與作品集展示，非投資建議。"


MARKET_VARIABLE_RULES = [
    (("fed", "rate", "yield", "treasury", "inflation", "cpi", "pce", "fomc"), "利率預期、美債殖利率、科技股估值"),
    (("nvidia", "ai", "semiconductor", "chip", "tsmc", "asml"), "AI 需求、半導體供應鏈、台股電子權值股"),
    (("oil", "energy", "middle east", "iran", "shipping", "red sea"), "能源價格、通膨預期、風險資產情緒"),
    (("dollar", "currency", "yen", "exchange", "fx"), "美元走勢、匯率壓力、外資風險偏好"),
    (("china", "tariff", "trade", "geopolitical"), "地緣政治、供應鏈風險、亞洲股市情緒"),
    (("earnings", "guidance", "profit", "revenue"), "企業財報、產業景氣、指數權重股表現"),
]

IMPORTANCE_KEYWORDS = {
    "fed": 9,
    "fomc": 9,
    "inflation": 8,
    "cpi": 8,
    "pce": 8,
    "rate": 7,
    "yield": 7,
    "nvidia": 8,
    "ai": 7,
    "semiconductor": 8,
    "tsmc": 8,
    "nasdaq": 7,
    "s&p": 7,
    "oil": 6,
    "middle east": 7,
    "dollar": 6,
    "china": 6,
    "tariff": 7,
    "earnings": 5,
}


def _now_tw() -> datetime:
    return datetime.now()


def week_window(today: date | None = None) -> tuple[date, date]:
    today = today or _now_tw().date()
    end = today
    start = end - timedelta(days=6)
    return start, end


def next_week_window(today: date | None = None) -> tuple[date, date]:
    today = today or _now_tw().date()
    start = today + timedelta(days=1)
    return start, start + timedelta(days=6)


def _normalize_title(title: str) -> str:
    text = title.lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def dedupe_news_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        title = str(item.get("title") or item.get("headline") or "").strip()
        if not title:
            continue
        key = _normalize_title(title).replace(" rate cut ", " ratecut ").replace("rate cut", "ratecut")
        if key in seen:
            continue
        seen.add(key)
        deduped.append({**item, "title": title})
    return deduped


def _score_news_item(item: dict[str, Any]) -> int:
    text = f"{item.get('title', '')} {item.get('description', '')} {item.get('summary', '')}".lower()
    score = 0
    for keyword, weight in IMPORTANCE_KEYWORDS.items():
        if keyword in text:
            score += weight
    if item.get("source"):
        score += 1
    if item.get("published_at"):
        score += 1
    return score


def _market_variable_for(text: str) -> str:
    low = text.lower()
    for keywords, variable in MARKET_VARIABLE_RULES:
        if any(k in low for k in keywords):
            return variable
    return "主要指數、資金流向、市場風險偏好"


def _image_query_for(text: str) -> str:
    low = text.lower()
    if any(k in low for k in ("fed", "fomc", "rate", "yield", "inflation", "cpi", "pce")):
        return "federal reserve financial market"
    if any(k in low for k in ("nvidia", "ai", "chip", "semiconductor", "tsmc")):
        return "semiconductor chip technology"
    if any(k in low for k in ("oil", "energy", "middle east", "iran")):
        return "oil energy market"
    if any(k in low for k in ("dollar", "currency", "yen", "exchange", "fx")):
        return "currency exchange trading"
    if any(k in low for k in ("china", "tariff", "trade", "geopolitical")):
        return "global trade shipping"
    if any(k in low for k in ("earnings", "guidance", "profit", "revenue")):
        return "corporate earnings finance"
    return "stock market trading screen"


def _first_market_variable(event: dict[str, Any]) -> str:
    variable = str(event.get("market_variable") or "").strip()
    return variable.split("、")[0] if variable else "市場風險偏好"


def build_storyline(events: list[dict[str, Any]]) -> str:
    variables = []
    for event in events[:5]:
        variable = _first_market_variable(event)
        if variable and variable not in variables:
            variables.append(variable)
        if len(variables) >= 4:
            break
    if not variables:
        return "本週主線是市場重新整理風險、估值與資金方向。"
    if len(variables) == 1:
        thread = variables[0]
    else:
        thread = "、".join(variables[:-1]) + f"與{variables[-1]}"
    return f"本週主線是{thread}如何一起影響台股與美股的資金情緒。"


def _event_bridge(idx: int, event: dict[str, Any], data: dict[str, Any]) -> str:
    variable = _first_market_variable(event)
    if idx == 1:
        return f"先從{variable}看起，因為它會決定市場給風險資產多少空間。"
    if idx == 2:
        return f"接著看{variable}，這是在利率框架之外，市場願不願意追成長的關鍵。"
    if idx == 3:
        return f"第三步看{variable}，它會回頭影響通膨與降息想像。"
    if idx == 4:
        return f"再來看{variable}，因為資金流向會放大前面幾個變數。"
    return f"最後看{variable}，用它確認這條主線會不會外溢到亞洲市場。"


def fallback_select_events(news_items: list[dict[str, Any]], max_events: int = 3) -> list[dict[str, Any]]:
    ranked = sorted(dedupe_news_items(news_items), key=_score_news_item, reverse=True)
    events: list[dict[str, Any]] = []
    for item in ranked[:max_events]:
        title = str(item.get("title", "")).strip()
        description = str(item.get("description") or item.get("summary") or "").strip()
        market_variable = _market_variable_for(f"{title} {description}")
        image_query = _image_query_for(f"{title} {description}")
        events.append(
            {
                "title": title[:40],
                "news_sentence": _english_to_neutral_zh_sentence(title),
                "market_variable": market_variable,
                "importance_reason": f"此事件牽動{market_variable}。",
                "image_query": image_query,
                "image_source": "Pexels",
                "sources": [
                    {
                        "name": str(item.get("source") or item.get("source_name") or "Market news"),
                        "url": str(item.get("url") or ""),
                        "published_at": str(item.get("published_at") or ""),
                    }
                ],
            }
        )
    return events


def _english_to_neutral_zh_sentence(title: str) -> str:
    low = title.lower()
    if any(k in low for k in ("fed", "fomc", "rate", "yield", "inflation", "cpi", "pce")):
        return f"{title}，市場重新評估利率與通膨路徑。"
    if any(k in low for k in ("nvidia", "ai", "chip", "semiconductor", "tsmc")):
        return f"{title}，AI 與半導體供應鏈成為市場焦點。"
    if any(k in low for k in ("oil", "energy", "middle east", "iran")):
        return f"{title}，能源與地緣政治風險升溫。"
    return f"{title}，市場關注後續對台股與美股的影響。"


def format_calendar_line(calendar_items: list[dict[str, Any]]) -> str:
    if not calendar_items:
        return "下週留意主要經濟數據與央行訊號。"

    high = [
        str(item.get("event") or item.get("Event") or "").strip()
        for item in calendar_items
        if str(item.get("importance") or item.get("Importance") or "").lower() in {"high", "3", "重要"}
    ]
    names = high or [str(item.get("event") or item.get("Event") or "").strip() for item in calendar_items]
    compact = []
    for name in names:
        if "Core PCE" in name or "PCE" in name:
            label = "Core PCE"
        elif "FOMC" in name:
            label = "FOMC"
        elif "CPI" in name:
            label = "CPI"
        elif "Non Farm" in name or "Payroll" in name or "NFP" in name:
            label = "NFP"
        elif "GDP" in name:
            label = "GDP"
        else:
            label = name[:18]
        if label and label not in compact:
            compact.append(label)
        if len(compact) >= 3:
            break
    if not compact:
        return "下週留意主要經濟數據與央行訊號。"
    return f"下週留意：{' / '.join(compact)}。"


def build_narration(data: dict[str, Any]) -> str:
    storyline = str(data.get("storyline") or build_storyline(data.get("events", [])))
    lines = [f"本週市場雷達。{storyline} 接下來用五個事件，把這條主線串起來。"]
    for idx, event in enumerate(data.get("events", [])[:5], start=1):
        lines.append(_event_segment_text(idx, event, data))
    if data.get("weekly_summary"):
        lines.append(str(data["weekly_summary"]))
    lines.append(format_calendar_line(data.get("next_week_events", [])))
    lines.append(CTA_TEXT)
    return "".join(lines)


def _event_watch_point(event: dict[str, Any], data: dict[str, Any]) -> str:
    calendar_line = str(data.get("calendar_line") or format_calendar_line(data.get("next_week_events", []))).rstrip("。")
    variable = str(event.get("market_variable") or "資金流向與市場風險偏好")
    first_variable = variable.split("、")[0]
    return f"下週先看{calendar_line}，以及{first_variable}是否延續。"


def _event_segment_text(idx: int, event: dict[str, Any], data: dict[str, Any]) -> str:
    news = str(event.get("news_sentence") or event.get("title") or "").strip()
    reason = str(event.get("importance_reason") or "").strip()
    if not reason:
        reason = f"這會牽動{event.get('market_variable', '資金流向與市場風險偏好')}。"
    watch_point = str(event.get("watch_point") or _event_watch_point(event, data)).strip()
    bridge = str(event.get("bridge_sentence") or _event_bridge(idx, event, data)).strip()
    return f"{bridge} 事件是：{news} 為什麼重要：{reason} 下週觀察：{watch_point}"


def build_audio_segments(data: dict[str, Any]) -> list[dict[str, str]]:
    storyline = str(data.get("storyline") or build_storyline(data.get("events", [])))
    segments = [
        {
            "key": "opening",
            "text": f"本週市場雷達。用五個事件看懂這條主線：{storyline}",
        }
    ]
    for idx, event in enumerate(data.get("events", [])[:5], start=1):
        title = str(event.get("title") or event.get("news_sentence") or "").strip()
        variable = _first_market_variable(event)
        watch_point = str(event.get("watch_point") or _event_watch_point(event, data)).strip()
        segments.append(
            {
                "key": f"event_{idx:02d}",
                "text": f"第{idx}件：{title}。牽動{variable}。下週看：{watch_point}",
            }
        )
    closing = " ".join([format_calendar_line(data.get("next_week_events", [])), CTA_TEXT, DISCLAIMER]).strip()
    segments.append({"key": "closing", "text": closing})
    return segments


def build_youtube_description(data: dict[str, Any]) -> str:
    meta = data.get("meta", {})
    lines = [
        f"完整事件整理：{meta.get('week_start', '')} - {meta.get('week_end', '')}",
        "",
        "本週 5 個重大市場事件：",
    ]
    image_sources: set[str] = set()
    for idx, event in enumerate(data.get("events", [])[:5], start=1):
        lines.append(f"{idx}. {event.get('title', '')}")
        lines.append(f"   牽動變數：{event.get('market_variable', '')}")
        if event.get("image_source"):
            image_sources.add(str(event["image_source"]))
    lines += ["", "下週經濟日曆："]
    for item in data.get("next_week_events", [])[:6]:
        lines.append(f"- {item.get('date', '')} {item.get('event', '')}")
    lines += ["", "來源："]
    seen_sources: set[str] = set()
    for event in data.get("events", []):
        for src in event.get("sources", []):
            name = str(src.get("name") or "Source")
            url = str(src.get("url") or "")
            key = f"{name}|{url}"
            if key in seen_sources:
                continue
            seen_sources.add(key)
            lines.append(f"- {name}: {url}" if url else f"- {name}")
    if image_sources:
        lines += ["", f"圖片來源：{', '.join(sorted(image_sources))}"]
    lines += ["", DISCLAIMER, "#台股 #美股 #財經雷達 #Shorts"]
    return "\n".join(lines)


def build_threads_post_text(data: dict[str, Any]) -> str:
    storyline = str(data.get("storyline") or build_storyline(data.get("events", [])))
    lines = [
        "本週市場雷達",
        storyline,
        "",
        "5 個觀察變數：",
    ]
    for idx, event in enumerate(data.get("events", [])[:5], start=1):
        title = str(event.get("title") or event.get("news_sentence") or "").strip()
        variable = _first_market_variable(event)
        lines.append(f"{idx}. {title}｜{variable}")
    lines += [
        "",
        str(data.get("calendar_line") or format_calendar_line(data.get("next_week_events", []))),
        DISCLAIMER,
        "#台股 #美股 #財經雷達",
    ]
    text = "\n".join(line for line in lines if line is not None).strip()
    return text[:500]


def fetch_market_news(start: date, end: date) -> list[dict[str, Any]]:
    api_key = os.getenv("MARKETAUX_API_KEY") or os.getenv("MARKET_NEWS_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 MARKETAUX_API_KEY 或 MARKET_NEWS_API_KEY，無法抓取英文市場新聞 API")

    params = {
        "api_token": api_key,
        "language": "en",
        "limit": 25,
        "published_after": f"{start.isoformat()}T00:00",
        "published_before": f"{end.isoformat()}T23:59",
        "filter_entities": "true",
        "industries": "Financial Services,Technology,Energy",
    }
    resp = requests.get("https://api.marketaux.com/v1/news/all", params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    items = []
    for raw in payload.get("data", []):
        items.append(
            {
                "title": raw.get("title", ""),
                "description": raw.get("description", ""),
                "url": raw.get("url", ""),
                "source": (raw.get("source") or ""),
                "published_at": raw.get("published_at", ""),
            }
        )
    return dedupe_news_items(items)


def fetch_economic_calendar(start: date, end: date) -> list[dict[str, Any]]:
    client = os.getenv("TRADING_ECONOMICS_CLIENT", "guest:guest")
    url = f"https://api.tradingeconomics.com/calendar/country/all/{start.isoformat()}/{end.isoformat()}"
    resp = requests.get(url, params={"c": client, "format": "json"}, timeout=30)
    resp.raise_for_status()
    raw_items = resp.json()
    items = []
    for raw in raw_items if isinstance(raw_items, list) else []:
        country = raw.get("Country", "")
        event = raw.get("Event", "")
        if not event:
            continue
        if country and country not in {"United States", "Taiwan", "China", "Japan", "Euro Area"}:
            continue
        items.append(
            {
                "date": str(raw.get("Date", ""))[:10],
                "country": country,
                "event": event,
                "importance": str(raw.get("Importance", "")),
            }
        )
    return items


def _daily_report_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    date_str = str(data.get("meta", {}).get("date", ""))
    items: list[dict[str, Any]] = []
    for item in data.get("top5_news", []):
        title = item.get("headline") or item.get("title")
        if not title:
            continue
        items.append(
            {
                "title": title,
                "description": item.get("summary", ""),
                "source": "財經雷達每日報告",
                "url": "",
                "published_at": date_str,
            }
        )
    return items


def load_recent_daily_news(limit_files: int = 5) -> list[dict[str, Any]]:
    analysis_dir = BASE_DIR / "output" / "analysis"
    items: list[dict[str, Any]] = []
    for path in sorted(analysis_dir.glob("analysis_*.json"), reverse=True)[:limit_files]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        items.extend(_daily_report_items(data))

    web_data_dir = BASE_DIR / "web" / "public" / "data"
    candidate_paths: list[Path] = []
    latest_path = web_data_dir / "latest.json"
    if latest_path.exists():
        candidate_paths.append(latest_path)
    index_path = web_data_dir / "index.json"
    if index_path.exists():
        try:
            index_data = json.loads(index_path.read_text(encoding="utf-8"))
            articles = index_data.get("articles") if isinstance(index_data, dict) else index_data
            for article in (articles or [])[:limit_files]:
                date_key = str(article.get("date") or "").replace("-", "")
                path = web_data_dir / f"{date_key}.json"
                if path.exists():
                    candidate_paths.append(path)
        except Exception:
            pass

    for path in candidate_paths[:limit_files + 1]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        items.extend(_daily_report_items(data))
    return items


def _pexels_download(query: str, output_path: Path) -> bool:
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        log.warning("PEXELS_API_KEY 未設定，Weekly Shorts 將不下載事件圖片")
        return False
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key},
            params={"query": query, "orientation": "portrait", "per_page": 1},
            timeout=20,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            return False
        src = photos[0].get("src", {})
        image_url = src.get("portrait") or src.get("large2x") or src.get("large")
        if not image_url:
            return False
        img = requests.get(image_url, timeout=30)
        img.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(img.content)
        return True
    except Exception as exc:
        log.warning("Pexels 圖片下載失敗（%s）：%s", query, exc)
        return False


def prepare_event_images(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    WEEKLY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    prepared: list[dict[str, Any]] = []
    for idx, event in enumerate(events[:5], start=1):
        query = str(
            event.get("image_query")
            or _image_query_for(f"{event.get('title', '')} {event.get('news_sentence', '')}")
        )
        filename = f"event_{idx:02d}.jpg"
        output_path = WEEKLY_IMAGE_DIR / filename
        if not output_path.exists():
            _pexels_download(query, output_path)
        prepared.append(
            {
                **event,
                "image_query": query,
                "image_source": "Pexels",
                "image_url": f"weekly/{filename}" if output_path.exists() else event.get("image_url", ""),
            }
        )
    return prepared


def create_weekly_short_data(today: date | None = None) -> dict[str, Any]:
    start, end = week_window(today)
    next_start, next_end = next_week_window(today)

    daily_news = load_recent_daily_news()
    try:
        api_news = fetch_market_news(start, end)
    except Exception as exc:
        log.warning("英文市場新聞 API 無法使用，改用既有每日新聞資料：%s", exc)
        api_news = []

    try:
        calendar = fetch_economic_calendar(next_start, next_end)
    except Exception as exc:
        log.warning("經濟日曆 API 無法使用，改用空日曆：%s", exc)
        calendar = []

    candidates = dedupe_news_items(api_news + daily_news)
    if not candidates:
        raise RuntimeError("找不到可用新聞資料，請先產生每日報告或設定市場新聞 API")

    events = _llm_select_events(candidates, calendar) or fallback_select_events(candidates, max_events=5)
    events = prepare_event_images(events[:5])
    storyline = build_storyline(events)
    weekly_summary = _build_weekly_summary(events)
    data = {
        "meta": {
            "week_start": start.isoformat(),
            "week_end": end.isoformat(),
            "generated_at": _now_tw().isoformat(timespec="seconds"),
            "platform": "youtube_shorts",
        },
        "events": events[:5],
        "next_week_events": calendar[:8],
        "calendar_line": format_calendar_line(calendar),
        "storyline": storyline,
        "weekly_summary": weekly_summary,
        "cta": CTA_TEXT,
    }
    data["narration"] = build_narration(data)
    return data


def _llm_select_events(candidates: list[dict[str, Any]], calendar: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        from config import CLAUDE_MODEL

        compact_candidates = [
            {
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "published_at": item.get("published_at", ""),
            }
            for item in candidates[:30]
        ]
        prompt = f"""
你是冷靜、快速、研究助理型的市場編輯。請從候選新聞中選出 5 個牽動台股/美股的重大市場事件。

規則：
- 每個事件用繁體中文輸出。
- 不要投資建議，不要使用布局、買點、明牌、可關注標的。
- 每個事件固定包含：title, news_sentence, market_variable, importance_reason, image_query, image_source, sources。
- news_sentence 一句話說明新聞，market_variable 一句列出牽動變數。
- image_query 必須是 3-5 個英文單字，用於 Pexels 搜圖；image_source 固定填 Pexels。
- sources 必須保留來源 name/url/published_at。
- 只輸出 JSON array，不要 markdown。

候選新聞：
{json.dumps(compact_candidates, ensure_ascii=False)}

下週經濟日曆參考：
{json.dumps(calendar[:8], ensure_ascii=False)}
"""
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = next((block.text for block in msg.content if block.type == "text"), "[]").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].replace("json", "", 1).strip()
        events = json.loads(raw)
        if isinstance(events, list) and len(events) >= 5:
            for event in events:
                event.setdefault("image_query", _image_query_for(f"{event.get('title', '')} {event.get('news_sentence', '')}"))
                event["image_source"] = "Pexels"
            return events[:5]
    except Exception as exc:
        log.warning("LLM 選題失敗，改用 heuristic fallback：%s", exc)
    return None


def _build_weekly_summary(events: list[dict[str, Any]]) -> str:
    variables = "、".join(str(e.get("market_variable", "")).split("、")[0] for e in events[:5] if e.get("market_variable"))
    return f"本週市場主線集中在{variables}，投資人更需要先理解脈絡，而不是追逐單一訊號。"


def write_weekly_data(data: dict[str, Any], path: Path = WEEKLY_DATA_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def get_audio_duration(path: Path) -> float:
    try:
        return MP3(str(path)).info.length
    except Exception:
        return 55.0


async def _speak_weekly(text: str, output_path: Path) -> None:
    import edge_tts

    output_path.parent.mkdir(parents=True, exist_ok=True)
    voices = ["zh-TW-YunJheNeural", "zh-TW-HsiaoChenNeural"]
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            communicate = edge_tts.Communicate(text, voices[(attempt - 1) % len(voices)], rate="+8%")
            await communicate.save(str(output_path))
            if output_path.stat().st_size < 1024:
                raise RuntimeError("Edge TTS produced an empty audio file")
            return
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(1.2 * attempt)
    raise RuntimeError(f"Weekly Shorts 語音合成失敗：{last_error}")


def generate_weekly_audio(data: dict[str, Any], output_path: Path = WEEKLY_AUDIO_PATH) -> Path:
    segments = build_audio_segments(data)
    WEEKLY_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    durations: dict[str, float] = {}
    combined_text_parts = []
    for segment in segments:
        key = segment["key"]
        text = segment["text"]
        path = WEEKLY_AUDIO_DIR / f"{key}.mp3"
        asyncio.run(_speak_weekly(text, path))
        durations[key] = round(get_audio_duration(path), 3)
        combined_text_parts.append(text)

    # Keep the legacy single-file path useful for quick manual previews.
    asyncio.run(_speak_weekly("".join(combined_text_parts), output_path))
    WEEKLY_DURATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEEKLY_DURATIONS_PATH.write_text(json.dumps(durations, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def render_weekly_video(data: dict[str, Any]) -> Path:
    write_weekly_data(data)
    generate_weekly_audio(data)
    WEEKLY_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["npx", "remotion", "render", "WeeklyShorts", str(WEEKLY_OUTPUT_PATH)]
    proc = subprocess.run(
        cmd,
        cwd=str(BASE_DIR / "video"),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Weekly Shorts 渲染失敗：{proc.stderr[-1000:]}")
    return WEEKLY_OUTPUT_PATH


def save_pending_weekly_short(payload: dict[str, Any] | None) -> None:
    WEEKLY_PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not payload:
        if WEEKLY_PENDING_FILE.exists():
            WEEKLY_PENDING_FILE.unlink()
        return
    serializable = {
        **payload,
        "video_path": str(payload.get("video_path")) if payload.get("video_path") else "",
        "saved_at": _now_tw().isoformat(timespec="seconds"),
    }
    WEEKLY_PENDING_FILE.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")


def load_pending_weekly_short() -> dict[str, Any] | None:
    if not WEEKLY_PENDING_FILE.exists():
        return None
    raw = json.loads(WEEKLY_PENDING_FILE.read_text(encoding="utf-8"))
    video_path = Path(raw.get("video_path", ""))
    if not video_path.exists():
        return None
    raw["video_path"] = video_path
    return raw


def publish_weekly_youtube(video_path: Path, data: dict[str, Any]) -> str | None:
    from publish_video import upload_to_youtube

    week_end = data.get("meta", {}).get("week_end", "")
    title = f"本週市場雷達｜5 個牽動台股與美股的重大事件 {week_end} #Shorts"
    return upload_to_youtube(
        video_path,
        title=title[:100],
        description=build_youtube_description(data),
        category="25",
        privacy="unlisted",
    )


def publish_weekly_threads(data: dict[str, Any]) -> str | None:
    from publish_video import upload_text_to_threads

    return upload_text_to_threads(build_threads_post_text(data))


def save_weekly_publish_log(result: dict[str, Any], path: Path = WEEKLY_PUBLISH_LOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        **result,
        "video_path": str(result.get("video_path") or ""),
        "saved_at": _now_tw().isoformat(timespec="seconds"),
    }
    history: list[dict[str, Any]] = []
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                history = loaded
        except Exception:
            history = []
    history.append(serializable)
    path.write_text(json.dumps(history[-50:], ensure_ascii=False, indent=2), encoding="utf-8")


def run_weekly_auto_publish(today: date | None = None) -> dict[str, Any]:
    data = create_weekly_short_data(today=today)
    video_path = render_weekly_video(data)
    youtube_video_id = publish_weekly_youtube(video_path, data)
    threads_id = publish_weekly_threads(data)
    result = {
        "data": data,
        "video_path": video_path,
        "youtube_video_id": youtube_video_id,
        "threads_id": threads_id,
        "status": "succeeded" if youtube_video_id and threads_id else "partial_failed",
        "generated_at": _now_tw().isoformat(timespec="seconds"),
    }
    save_weekly_publish_log(result)
    if not youtube_video_id or not threads_id:
        raise RuntimeError(
            f"Weekly auto publish incomplete: youtube={youtube_video_id or 'FAILED'}, "
            f"threads={threads_id or 'FAILED'}"
        )
    save_pending_weekly_short(None)
    return result


def run_weekly_draft(today: date | None = None) -> dict[str, Any]:
    data = create_weekly_short_data(today=today)
    video_path = render_weekly_video(data)
    payload = {"data": data, "video_path": video_path}
    save_pending_weekly_short(payload)
    return payload


def build_review_text(data: dict[str, Any], video_path: Path | None = None) -> str:
    meta = data.get("meta", {})
    lines = [f"週期：{meta.get('week_start')} - {meta.get('week_end')}", ""]
    for idx, event in enumerate(data.get("events", [])[:5], start=1):
        lines.append(f"{idx}. {event.get('title', '')}")
        lines.append(f"   牽動：{event.get('market_variable', '')}")
    lines.append("")
    lines.append(data.get("calendar_line") or format_calendar_line(data.get("next_week_events", [])))
    if video_path:
        lines.append(f"影片：{video_path.name}")
    return "\n".join(lines)


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Generate or publish Weekly Market Shorts")
    parser.add_argument("--draft", action="store_true", help="Create data, audio, and mp4 draft")
    parser.add_argument("--publish-pending", action="store_true", help="Publish pending draft to YouTube as unlisted")
    parser.add_argument("--auto-publish", action="store_true", help="Create weekly video, upload YouTube unlisted, and publish Threads text")
    args = parser.parse_args()

    if args.auto_publish:
        result = run_weekly_auto_publish()
        print(f"YouTube: https://www.youtube.com/watch?v={result['youtube_video_id']}")
        print(f"Threads id: {result['threads_id']}")
        return

    if args.publish_pending:
        pending = load_pending_weekly_short()
        if not pending:
            raise SystemExit("沒有待發布 Weekly Shorts")
        video_id = publish_weekly_youtube(pending["video_path"], pending["data"])
        print(f"https://www.youtube.com/watch?v={video_id}" if video_id else "發布失敗")
        if video_id:
            save_pending_weekly_short(None)
        return

    payload = run_weekly_draft()
    print(build_review_text(payload["data"], payload["video_path"]))


if __name__ == "__main__":
    main()
