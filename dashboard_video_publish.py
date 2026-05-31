from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
WEB_DATA_DIR = BASE_DIR / "web" / "public" / "data"
VIDEO_PATH = BASE_DIR / "video" / "out" / "video_horizontal.mp4"
RENDER_STATUS_PATH = BASE_DIR / "data" / "dashboard_video_render_status.json"
PREVIEW_URL = "/generated-videos/video_horizontal.mp4"


def _write_render_status(state: str, stage: str, percent: int, error: str = "") -> dict[str, Any]:
    payload = {
        "state": state,
        "stage": stage,
        "percent": percent,
        "error": error,
    }
    RENDER_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RENDER_STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _read_render_status() -> dict[str, Any]:
    if not RENDER_STATUS_PATH.exists():
        return {
            "state": "ready" if VIDEO_PATH.exists() else "idle",
            "stage": "影片可預覽" if VIDEO_PATH.exists() else "尚未生成影片",
            "percent": 100 if VIDEO_PATH.exists() else 0,
            "error": "",
        }
    try:
        return json.loads(RENDER_STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"state": "unknown", "stage": "狀態讀取失敗", "percent": 0, "error": ""}


def _date_key(report_date: str) -> str:
    return report_date.replace("-", "")


def load_latest_report() -> dict[str, Any] | None:
    from database import list_reports, load_report

    reports = list_reports(limit=1)
    if reports:
        return load_report(reports[0]["date"])

    latest_path = WEB_DATA_DIR / "latest.json"
    if latest_path.exists():
        return json.loads(latest_path.read_text(encoding="utf-8"))
    return None


def _video_title(data: dict[str, Any], date_str: str) -> str:
    raw_title = (data.get("outputs") or {}).get("edm_subject", "")
    clean = raw_title[raw_title.find("】") + 1:].strip() if "】" in raw_title else raw_title
    return (data.get("article") or {}).get("title") or clean or date_str


def get_status() -> dict[str, Any]:
    data = load_latest_report()
    if not data:
        return {
            "state": "no_report",
            "published": False,
            "video_exists": VIDEO_PATH.exists(),
            "video_path": str(VIDEO_PATH),
        }

    date_str = data.get("meta", {}).get("date", "")
    youtube_video_id = data.get("youtube_video_id") or ""
    video_exists = VIDEO_PATH.exists()

    render = _read_render_status()

    if render.get("state") == "rendering":
        state = "rendering"
    elif youtube_video_id:
        state = "published"
    elif video_exists:
        state = "ready"
    else:
        state = "missing_video"

    return {
        "state": state,
        "date": date_str,
        "title": _video_title(data, date_str),
        "published": bool(youtube_video_id),
        "youtube_video_id": youtube_video_id,
        "youtube_url": f"https://www.youtube.com/watch?v={youtube_video_id}" if youtube_video_id else "",
        "video_exists": video_exists,
        "video_path": str(VIDEO_PATH),
        "preview_url": PREVIEW_URL if video_exists else "",
        "render": render,
    }


def render_latest() -> dict[str, Any]:
    data = load_latest_report()
    if not data:
        render = _write_render_status("failed", "找不到最新報告", 0, "找不到最新報告")
        return {"ok": False, "state": "no_report", "render": render, "error": "找不到最新報告"}

    _write_render_status("rendering", "準備報告資料", 10)
    _write_render_status("rendering", "生成旁白音檔", 30)
    _write_render_status("rendering", "生成影片圖片素材", 50)
    _write_render_status("rendering", "Remotion 渲染影片", 80)

    import main

    video_paths = main.step_render_video(
        data,
        render_horizontal=True,
        render_vertical=False,
    )
    h_path = video_paths.get("horizontal")
    if not h_path or not Path(h_path).exists():
        render = _write_render_status("failed", "影片生成失敗", 80, "Remotion 未產出橫式影片")
        return {"ok": False, **get_status(), "state": "render_failed", "render": render, "error": render["error"]}

    render = _write_render_status("ready", "影片可預覽", 100)
    return {"ok": True, **get_status(), "state": "ready", "render": render, "preview_url": PREVIEW_URL}


def publish_youtube_unlisted(data: dict[str, Any]) -> str | None:
    import main

    return main.step_publish_youtube(VIDEO_PATH, data, privacy="unlisted")


def save_report_outputs(data: dict[str, Any]) -> None:
    import main

    main.step_save_db(data)


def update_videos_json(data: dict[str, Any], youtube_video_id: str) -> None:
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    videos_path = WEB_DATA_DIR / "videos.json"
    payload = json.loads(videos_path.read_text(encoding="utf-8")) if videos_path.exists() else {"videos": []}

    date_str = data.get("meta", {}).get("date", "")
    entry = {
        "video_id": youtube_video_id,
        "date": date_str,
        "title": _video_title(data, date_str),
    }
    existing = payload.get("videos") or []
    payload["videos"] = [
        item for item in existing
        if item.get("video_id") != youtube_video_id and item.get("date") != date_str
    ]
    payload["videos"].insert(0, entry)
    videos_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def publish_latest() -> dict[str, Any]:
    data = load_latest_report()
    if not data:
        return {"ok": False, "state": "no_report", "error": "找不到最新報告"}

    status = get_status()
    if status["state"] == "published":
        return {"ok": True, **status, "state": "already_published"}
    if not VIDEO_PATH.exists():
        return {"ok": False, **status, "error": "找不到橫式影片，請先產生 video/out/video_horizontal.mp4"}

    youtube_video_id = publish_youtube_unlisted(data)
    if not youtube_video_id:
        return {"ok": False, **get_status(), "state": "failed", "error": "YouTube 上傳失敗，請查看 video_publish_jobs 或 VM log"}

    data["youtube_video_id"] = youtube_video_id
    save_report_outputs(data)
    update_videos_json(data, youtube_video_id)

    return {"ok": True, **get_status(), "state": "published"}


def _run_cli(action: str) -> int:
    try:
        if action == "status":
            result = {"ok": True, **get_status()}
        elif action == "render-youtube":
            result = render_latest()
        elif action == "publish-youtube":
            result = publish_latest()
        else:
            result = {"ok": False, "state": "bad_action", "error": f"unknown action: {action}"}
    except Exception as exc:
        result = {
            "ok": False,
            "state": "error",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def main_cli() -> int:
    parser = argparse.ArgumentParser(description="Dashboard YouTube publish helper")
    parser.add_argument("action", choices=["status", "render-youtube", "publish-youtube"])
    args = parser.parse_args()
    return _run_cli(args.action)


if __name__ == "__main__":
    raise SystemExit(main_cli())
