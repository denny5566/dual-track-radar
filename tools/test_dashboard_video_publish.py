import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import dashboard_video_publish as publish


def sample_report(youtube_video_id=""):
    return {
        "meta": {"date": "2026-05-31"},
        "daily_focus": "AI 伺服器與利率預期牽動台股",
        "top5_news": [{"headline": "台股關注 AI 供應鏈"}],
        "article": {"title": "台股盤前速報"},
        "outputs": {"edm_subject": "【財經雷達】台股盤前速報"},
        "youtube_video_id": youtube_video_id,
    }


class DashboardVideoPublishTests(unittest.TestCase):
    def test_status_reports_missing_video_for_latest_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            report = sample_report()

            with patch.object(publish, "load_latest_report", return_value=report), \
                 patch.object(publish, "VIDEO_PATH", tmp_path / "video" / "out" / "video_horizontal.mp4"), \
                 patch.object(publish, "RENDER_STATUS_PATH", tmp_path / "render_status.json"):
                status = publish.get_status()

        self.assertEqual(status["state"], "missing_video")
        self.assertEqual(status["date"], "2026-05-31")
        self.assertFalse(status["video_exists"])
        self.assertFalse(status["published"])

    def test_publish_refuses_already_published_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            report = sample_report(youtube_video_id="abc123")

            with patch.object(publish, "load_latest_report", return_value=report), \
                 patch.object(publish, "RENDER_STATUS_PATH", tmp_path / "render_status.json"), \
                 patch.object(publish, "publish_youtube_unlisted") as upload:
                result = publish.publish_latest()

        upload.assert_not_called()
        self.assertEqual(result["state"], "already_published")
        self.assertEqual(result["youtube_video_id"], "abc123")

    def test_publish_updates_report_json_and_videos_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_dir = tmp_path / "web" / "public" / "data"
            data_dir.mkdir(parents=True)
            video_path = tmp_path / "video" / "out" / "video_horizontal.mp4"
            video_path.parent.mkdir(parents=True)
            video_path.write_bytes(b"fake mp4")

            report = sample_report()

            with patch.object(publish, "WEB_DATA_DIR", data_dir), \
                 patch.object(publish, "VIDEO_PATH", video_path), \
                 patch.object(publish, "load_latest_report", return_value=report), \
                 patch.object(publish, "publish_youtube_unlisted", return_value="yt999"), \
                 patch.object(publish, "save_report_outputs") as save_outputs:
                result = publish.publish_latest()

            save_outputs.assert_called_once()
            saved_report = save_outputs.call_args.args[0]
            self.assertEqual(saved_report["youtube_video_id"], "yt999")

            videos = json.loads((data_dir / "videos.json").read_text(encoding="utf-8"))
            self.assertEqual(videos["videos"][0]["video_id"], "yt999")
            self.assertEqual(videos["videos"][0]["date"], "2026-05-31")
            self.assertEqual(videos["videos"][0]["title"], "台股盤前速報")
            self.assertEqual(result["state"], "published")
            self.assertEqual(result["youtube_url"], "https://www.youtube.com/watch?v=yt999")

    def test_render_latest_writes_staged_progress_and_preview_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_path = tmp_path / "render_status.json"
            video_path = tmp_path / "video" / "out" / "video_horizontal.mp4"
            video_path.parent.mkdir(parents=True)
            report = sample_report()

            def fake_render(_data, render_horizontal=True, render_vertical=False):
                self.assertTrue(render_horizontal)
                self.assertFalse(render_vertical)
                video_path.write_bytes(b"fake mp4")
                return {"horizontal": video_path, "vertical": None}

            fake_main = types.SimpleNamespace(step_render_video=fake_render)

            with patch.object(publish, "RENDER_STATUS_PATH", status_path), \
                 patch.object(publish, "VIDEO_PATH", video_path), \
                 patch.object(publish, "load_latest_report", return_value=report), \
                 patch.dict(sys.modules, {"main": fake_main}):
                result = publish.render_latest()

            saved = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertTrue(result["ok"])
            self.assertEqual(result["render"]["state"], "ready")
            self.assertEqual(result["render"]["percent"], 100)
            self.assertEqual(saved["stage"], "影片可預覽")
            self.assertEqual(result["preview_url"], "/generated-videos/video_horizontal.mp4")

    def test_status_includes_running_render_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            status_path = tmp_path / "render_status.json"
            status_path.write_text(
                json.dumps({"state": "rendering", "stage": "Remotion 渲染影片", "percent": 80}, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch.object(publish, "RENDER_STATUS_PATH", status_path), \
                 patch.object(publish, "load_latest_report", return_value=sample_report()), \
                 patch.object(publish, "VIDEO_PATH", tmp_path / "video.mp4"):
                status = publish.get_status()

            self.assertEqual(status["render"]["state"], "rendering")
            self.assertEqual(status["render"]["percent"], 80)


if __name__ == "__main__":
    unittest.main()
