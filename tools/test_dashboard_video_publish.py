import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import dashboard_video_publish as publish


def sample_weekly_data(youtube_video_id="", threads_id=""):
    payload = {
        "meta": {"week_start": "2026-05-25", "week_end": "2026-05-31"},
        "storyline": "本週主線是利率與 AI 需求牽動台股與美股。",
        "events": [{"title": f"事件 {i}", "market_variable": "利率預期"} for i in range(1, 6)],
        "calendar_line": "下週留意：FOMC。",
    }
    if youtube_video_id:
        payload["youtube_video_id"] = youtube_video_id
    if threads_id:
        payload["threads_id"] = threads_id
    return payload


class DashboardVideoPublishTests(unittest.TestCase):
    def test_status_reports_missing_video_when_latest_report_exists_but_no_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            report = {"meta": {"date": "2026-05-31"}}

            with patch.object(publish, "load_latest_report", return_value=report), \
                 patch.object(publish, "_load_weekly_pending", return_value=None), \
                 patch.object(publish, "VIDEO_PATH", tmp_path / "weekly_short.mp4"), \
                 patch.object(publish, "RENDER_STATUS_PATH", tmp_path / "render_status.json"):
                status = publish.get_status()

        self.assertEqual(status["state"], "missing_video")
        self.assertEqual(status["date"], "2026-05-31")
        self.assertFalse(status["video_exists"])
        self.assertFalse(status["published"])
        self.assertEqual(status["threads_text"], "")

    def test_status_includes_weekly_threads_text_when_pending_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video_path = tmp_path / "weekly_short.mp4"
            video_path.write_bytes(b"fake mp4")
            data = sample_weekly_data()

            with patch.object(publish, "VIDEO_PATH", video_path), \
                 patch.object(publish, "RENDER_STATUS_PATH", tmp_path / "render_status.json"), \
                 patch.object(publish, "_load_weekly_pending", return_value={"data": data, "video_path": video_path}), \
                 patch.object(publish, "_build_threads_text", return_value="Threads 預覽文字"):
                status = publish.get_status()

            self.assertEqual(status["state"], "ready")
            self.assertEqual(status["preview_url"], "/generated-videos/weekly_short.mp4")
            self.assertEqual(status["threads_text"], "Threads 預覽文字")
            self.assertFalse(status["youtube_published"])
            self.assertFalse(status["threads_published"])

    def test_status_uses_weekly_data_file_when_video_exists_without_pending_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video_path = tmp_path / "weekly_short.mp4"
            video_path.write_bytes(b"fake mp4")
            data = sample_weekly_data()

            with patch.object(publish, "VIDEO_PATH", video_path), \
                 patch.object(publish, "RENDER_STATUS_PATH", tmp_path / "render_status.json"), \
                 patch.object(publish, "_load_weekly_pending", return_value=None), \
                 patch.object(publish, "_load_weekly_data_file", return_value=data), \
                 patch.object(publish, "_build_threads_text", return_value="Threads 檔案草稿"):
                status = publish.get_status()

            self.assertEqual(status["state"], "ready")
            self.assertEqual(status["date"], "2026-05-31")
            self.assertEqual(status["threads_text"], "Threads 檔案草稿")

    def test_status_tracks_individual_youtube_and_threads_publish_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video_path = tmp_path / "weekly_short.mp4"
            video_path.write_bytes(b"fake mp4")
            data = sample_weekly_data(youtube_video_id="yt999", threads_id="thread123")

            with patch.object(publish, "VIDEO_PATH", video_path), \
                 patch.object(publish, "RENDER_STATUS_PATH", tmp_path / "render_status.json"), \
                 patch.object(publish, "_load_weekly_pending", return_value={"data": data, "video_path": video_path}), \
                 patch.object(publish, "_build_threads_text", return_value="Threads 預覽文字"):
                status = publish.get_status()

            self.assertEqual(status["state"], "published")
            self.assertTrue(status["youtube_published"])
            self.assertTrue(status["threads_published"])
            self.assertEqual(status["youtube_url"], "https://www.youtube.com/watch?v=yt999")

    def test_render_latest_uses_weekly_draft_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_path = tmp_path / "render_status.json"
            video_path = tmp_path / "weekly_short.mp4"
            data = sample_weekly_data()

            def fake_run_weekly_draft():
                video_path.write_bytes(b"fake mp4")
                return {"data": data, "video_path": video_path}

            fake_weekly = types.SimpleNamespace(run_weekly_draft=fake_run_weekly_draft)

            with patch.object(publish, "VIDEO_PATH", video_path), \
                 patch.object(publish, "RENDER_STATUS_PATH", status_path), \
                 patch.object(publish, "_load_weekly_pending", return_value={"data": data, "video_path": video_path}), \
                 patch.object(publish, "_build_threads_text", return_value="Threads 草稿"), \
                 patch.dict(sys.modules, {"weekly_shorts": fake_weekly}):
                result = publish.render_latest()

            saved = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertTrue(result["ok"])
            self.assertEqual(result["render"]["percent"], 100)
            self.assertEqual(saved["stage"], "影片與 Threads 草稿可預覽")
            self.assertEqual(result["threads_text"], "Threads 草稿")

    def test_publish_youtube_updates_pending_and_videos_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir = tmp_path / "web" / "public" / "data"
            data_dir.mkdir(parents=True)
            video_path = tmp_path / "weekly_short.mp4"
            video_path.write_bytes(b"fake mp4")
            data = sample_weekly_data()

            fake_weekly = types.SimpleNamespace(publish_weekly_youtube=lambda _path, _data: "yt999")

            with patch.object(publish, "WEB_DATA_DIR", data_dir), \
                 patch.object(publish, "_load_weekly_pending", return_value={"data": data, "video_path": video_path}), \
                 patch.object(publish, "_save_pending") as save_pending, \
                 patch.object(publish, "_build_threads_text", return_value="Threads 草稿"), \
                 patch.dict(sys.modules, {"weekly_shorts": fake_weekly}):
                result = publish.publish_latest()

            save_pending.assert_called_once()
            self.assertEqual(data["youtube_video_id"], "yt999")
            videos = json.loads((data_dir / "videos.json").read_text(encoding="utf-8"))
            self.assertEqual(videos["videos"][0]["video_id"], "yt999")
            self.assertEqual(videos["videos"][0]["date"], "2026-05-31")
            self.assertEqual(videos["videos"][0]["title"], "本週市場雷達 Shorts｜2026-05-31")
            self.assertTrue(result["ok"])

    def test_publish_threads_uses_pending_weekly_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "weekly_short.mp4"
            video_path.write_bytes(b"fake mp4")
            data = sample_weekly_data()
            fake_weekly = types.SimpleNamespace(publish_weekly_threads=lambda payload: "thread123")

            with patch.object(publish, "_load_weekly_pending", return_value={"data": data, "video_path": video_path}), \
                 patch.object(publish, "_save_pending") as save_pending, \
                 patch.object(publish, "_build_threads_text", return_value="Threads 草稿"), \
                 patch.dict(sys.modules, {"weekly_shorts": fake_weekly}):
                result = publish.publish_threads_latest()

            save_pending.assert_called_once()
            self.assertTrue(result["ok"])
            self.assertEqual(result["threads_id"], "thread123")
            self.assertEqual(data["threads_id"], "thread123")

    def test_publish_threads_can_use_weekly_data_file_without_pending_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "weekly_short.mp4"
            video_path.write_bytes(b"fake mp4")
            data = sample_weekly_data()
            fake_weekly = types.SimpleNamespace(publish_weekly_threads=lambda payload: "thread123")

            with patch.object(publish, "VIDEO_PATH", video_path), \
                 patch.object(publish, "_load_weekly_pending", return_value=None), \
                 patch.object(publish, "_load_weekly_data_file", return_value=data), \
                 patch.object(publish, "_save_pending") as save_pending, \
                 patch.object(publish, "_build_threads_text", return_value="Threads 草稿"), \
                 patch.dict(sys.modules, {"weekly_shorts": fake_weekly}):
                result = publish.publish_threads_latest()

            save_pending.assert_called_once()
            self.assertTrue(result["ok"])
            self.assertEqual(result["threads_id"], "thread123")


if __name__ == "__main__":
    unittest.main()
