import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from weekly_shorts import (
    build_threads_post_text,
    build_youtube_description,
    build_audio_segments,
    build_storyline,
    create_weekly_short_data,
    dedupe_news_items,
    fallback_select_events,
    format_calendar_line,
    load_recent_daily_news,
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
        self.assertIn("五個事件", segments[0]["text"])
        self.assertIn("第1件", segments[1]["text"])
        self.assertIn("牽動", segments[1]["text"])
        self.assertIn("下週看", segments[1]["text"])
        self.assertLess(len(segments[1]["text"]), 120)
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
            "events": [
                {"title": "台股市值躍升全球第五大股市，融資水位偏高", "market_variable": "台股資金行情、籌碼風險"},
                {"title": "10 年期美債殖利率跌破 4.5%，科技股回溫", "market_variable": "美債殖利率、科技股估值"},
                {"title": "費半指數續創高點，半導體族群成為資金主軸", "market_variable": "半導體供應鏈、AI 需求"},
                {"title": "中東局勢推升油價波動，能源價格受到關注", "market_variable": "能源價格、通膨預期"},
                {"title": "SpaceX IPO 帶動被動資金買盤想像", "market_variable": "IPO 資金流向、市場風險偏好"},
            ],
            "calendar_line": "下週留意：FOMC / Core PCE。",
        }

        text = build_threads_post_text(data)

        self.assertIn("【本週市場焦點】", text)
        self.assertIn("台股市值躍升", text)
        self.assertIn("美債殖利率", text)
        self.assertIn("SpaceX IPO", text)
        self.assertIn("下週留意", text)
        self.assertIn("Core PCE。僅供", text)
        self.assertIn("非投資建議", text)
        self.assertNotIn("5 個觀察變數", text)
        self.assertNotIn("1.", text)
        self.assertGreaterEqual(len(text), 250)
        self.assertLessEqual(len(text), 350)
        self.assertGreaterEqual(text.count("\n\n"), 3)

    def test_create_weekly_short_data_falls_back_to_daily_news_without_market_api(self):
        daily_news = [
            {"title": f"Fed rate story {i}", "description": "Rates and yields move markets", "source": "Daily"}
            for i in range(1, 7)
        ]

        with patch("weekly_shorts.fetch_market_news", side_effect=RuntimeError("missing key")), \
             patch("weekly_shorts.fetch_economic_calendar", return_value=[]), \
             patch("weekly_shorts.load_recent_daily_news", return_value=daily_news), \
             patch("weekly_shorts.prepare_event_images", side_effect=lambda events: events), \
             patch("weekly_shorts._llm_select_events", return_value=None):
            data = create_weekly_short_data(today=date(2026, 5, 31))

        self.assertEqual(data["meta"]["week_end"], "2026-05-31")
        self.assertGreaterEqual(len(data["events"]), 5)
        self.assertIn("narration", data)
        self.assertIn("下週留意", data["calendar_line"])

    def test_load_recent_daily_news_reads_web_public_reports(self):
        report = {
            "meta": {"date": "2026-05-29"},
            "top5_news": [
                {"headline": "台股躍升全球第五大股市", "summary": "資金流向股市但融資滿水位。"}
            ],
        }

        with patch("weekly_shorts.BASE_DIR") as base_dir:
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                base_dir.__truediv__.side_effect = lambda other: root / other
                data_dir = root / "web" / "public" / "data"
                data_dir.mkdir(parents=True)
                (data_dir / "latest.json").write_text(
                    __import__("json").dumps(report, ensure_ascii=False),
                    encoding="utf-8",
                )

                items = load_recent_daily_news()

        self.assertEqual(items[0]["title"], "台股躍升全球第五大股市")
        self.assertEqual(items[0]["source"], "財經雷達每日報告")

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
