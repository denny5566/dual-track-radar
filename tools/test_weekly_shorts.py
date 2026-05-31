import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from weekly_shorts import (
    build_threads_post_text,
    build_youtube_description,
    build_audio_segments,
    build_storyline,
    dedupe_news_items,
    fallback_select_events,
    format_calendar_line,
    run_weekly_auto_publish,
)


class WeeklyShortsTests(unittest.TestCase):
    def test_dedupe_news_items_normalizes_similar_titles(self):
        items = [
            {"title": "Fed rate-cut hopes fade as yields rise", "source": "A"},
            {"title": "Fed rate cut hopes fade as yields rise!", "source": "B"},
            {"title": "TSMC shares climb after AI demand outlook", "source": "C"},
        ]

        deduped = dedupe_news_items(items)

        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["title"], "Fed rate-cut hopes fade as yields rise")

    def test_fallback_select_events_returns_five_structured_events(self):
        news = [
            {"title": "Fed signals rates may stay higher for longer", "source": "Reuters", "url": "https://example.com/1", "published_at": "2026-05-23"},
            {"title": "Nvidia results lift AI chip stocks across Nasdaq", "source": "MarketWatch", "url": "https://example.com/2", "published_at": "2026-05-24"},
            {"title": "Oil jumps as Middle East tensions disrupt shipping", "source": "CNBC", "url": "https://example.com/3", "published_at": "2026-05-24"},
            {"title": "Dollar gains as currency volatility returns", "source": "Newswire", "url": "https://example.com/4", "published_at": "2026-05-24"},
            {"title": "China trade tensions weigh on Asian stocks", "source": "Bloomberg", "url": "https://example.com/5", "published_at": "2026-05-24"},
            {"title": "Small company announces internal award", "source": "Newswire", "url": "https://example.com/6", "published_at": "2026-05-24"},
        ]

        events = fallback_select_events(news, max_events=5)

        self.assertEqual(len(events), 5)
        self.assertTrue(all("market_variable" in event for event in events))
        self.assertTrue(all(event["sources"] for event in events))
        self.assertTrue(all("image_query" in event for event in events))

    def test_format_calendar_line_keeps_short_video_friendly_text(self):
        calendar = [
            {"event": "United States Core PCE Price Index", "date": "2026-05-29", "importance": "High"},
            {"event": "Japan Unemployment Rate", "date": "2026-05-30", "importance": "Low"},
            {"event": "United States FOMC Minutes", "date": "2026-05-28", "importance": "High"},
        ]

        line = format_calendar_line(calendar)

        self.assertIn("下週留意", line)
        self.assertIn("Core PCE", line)
        self.assertIn("FOMC", line)
        self.assertLessEqual(len(line), 80)

    def test_build_youtube_description_includes_disclaimer_sources_and_calendar(self):
        data = {
            "meta": {"week_start": "2026-05-18", "week_end": "2026-05-24"},
            "events": [
                {
                    "title": "Fed 降息預期降溫",
                    "news_sentence": "Fed 降息預期降溫，美債殖利率回升。",
                    "market_variable": "美債殖利率、科技股估值",
                    "image_source": "Pexels",
                    "sources": [{"name": "Reuters", "url": "https://example.com/fed"}],
                }
            ],
            "next_week_events": [{"event": "FOMC Minutes", "date": "2026-05-28"}],
        }

        desc = build_youtube_description(data)

        self.assertIn("完整事件整理", desc)
        self.assertIn("非投資建議", desc)
        self.assertIn("Pexels", desc)
        self.assertIn("Reuters", desc)
        self.assertIn("FOMC Minutes", desc)

    def test_build_audio_segments_creates_opening_five_events_and_closing(self):
        data = {
            "events": [
                {"news_sentence": f"事件 {i}。", "market_variable": "利率預期", "importance_reason": "此事件會影響資金評價。"}
                for i in range(1, 6)
            ],
            "weekly_summary": "本週主線集中在利率與科技股。",
            "next_week_events": [{"event": "FOMC Minutes", "date": "2026-05-28", "importance": "High"}],
        }

        segments = build_audio_segments(data)

        self.assertEqual([s["key"] for s in segments], ["opening", "event_01", "event_02", "event_03", "event_04", "event_05", "closing"])
        self.assertIn("本週主線", segments[0]["text"])
        self.assertIn("串起來", segments[0]["text"])
        self.assertIn("事件是", segments[1]["text"])
        self.assertIn("為什麼重要", segments[1]["text"])
        self.assertIn("下週觀察", segments[1]["text"])
        self.assertIn("接著", segments[2]["text"])
        self.assertIn("完整事件整理", segments[-1]["text"])

    def test_build_storyline_links_events_into_one_market_thread(self):
        events = [
            {"market_variable": "利率預期、美債殖利率"},
            {"market_variable": "AI 需求、半導體供應鏈"},
            {"market_variable": "能源價格、通膨預期"},
        ]

        storyline = build_storyline(events)

        self.assertIn("本週主線", storyline)
        self.assertIn("利率預期", storyline)
        self.assertIn("AI 需求", storyline)
        self.assertIn("能源價格", storyline)

    def test_build_threads_post_text_is_structured_and_compliant(self):
        data = {
            "storyline": "本週主線是利率與 AI 需求牽動台股與美股。",
            "events": [
                {"title": f"事件 {i}", "market_variable": "利率預期、科技股估值"}
                for i in range(1, 6)
            ],
            "calendar_line": "下週留意：FOMC / Core PCE。",
        }

        text = build_threads_post_text(data)

        self.assertIn("本週市場雷達", text)
        self.assertIn("1. 事件 1", text)
        self.assertIn("5. 事件 5", text)
        self.assertIn("下週留意", text)
        self.assertIn("非投資建議", text)
        self.assertLessEqual(len(text), 500)

    def test_run_weekly_auto_publish_generates_video_and_publishes_both_platforms(self):
        data = {
            "meta": {"week_start": "2026-05-18", "week_end": "2026-05-24"},
            "events": [{"title": f"事件 {i}", "market_variable": "利率預期"} for i in range(1, 6)],
            "calendar_line": "下週留意：FOMC。",
        }
        video_path = Path("video/out/test-weekly.mp4")

        with patch("weekly_shorts.create_weekly_short_data", return_value=data), \
             patch("weekly_shorts.render_weekly_video", return_value=video_path), \
             patch("weekly_shorts.publish_weekly_youtube", return_value="yt123") as yt, \
             patch("weekly_shorts.publish_weekly_threads", return_value="th123") as th, \
             patch("weekly_shorts.save_weekly_publish_log") as save_log:
            result = run_weekly_auto_publish()

        yt.assert_called_once_with(video_path, data)
        th.assert_called_once_with(data)
        save_log.assert_called_once()
        self.assertEqual(result["youtube_video_id"], "yt123")
        self.assertEqual(result["threads_id"], "th123")
        self.assertEqual(result["video_path"], video_path)


if __name__ == "__main__":
    unittest.main()
