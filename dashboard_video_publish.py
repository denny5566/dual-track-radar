from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
WEB_DATA_DIR = BASE_DIR / "web" / "public" / "data"
VIDEO_PATH = BASE_DIR / "video" / "out" / "weekly_short.mp4"
RENDER_STATUS_PATH = BASE_DIR / "data" / "dashboard_video_render_status.json"
PREVIEW_URL = "/generated-videos/weekly_short.mp4"


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
            "stage": "影片與 Threads 草稿可預覽" if VIDEO_PATH.exists() else "尚未生成短影音",
            "percent": 100 if VIDEO_PATH.exists() else 0,
            "error": "",
        }
    try:
        return json.loads(RENDER_STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"state": "unknown", "stage": "狀態讀取失敗", "percent": 0, "error": ""}


def _load_weekly_pending() -> dict[str, Any] | None:
    import weekly_shorts

    return weekly_shorts.load_pending_weekly_short()


def _load_weekly_data_file() -> dict[str, Any] | None:
    import weekly_shorts

    path = getattr(weekly_shorts, "WEEKLY_DATA_PATH", BASE_DIR / "video" / "src" / "data" / "weekly_short.json")
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _build_threads_text(data: dict[str, Any]) -> str:
    import weekly_shorts

    return weekly_shorts.build_threads_post_text(data)


def load_latest_report() -> dict[str, Any] | None:
    from database import list_reports, load_report

    reports = list_reports(limit=1)
    if reports:
        return load_report(reports[0]["date"])

    latest_path = WEB_DATA_DIR / "latest.json"
    if latest_path.exists():
        return json.loads(latest_path.read_text(encoding="utf-8"))
    return None


def _weekly_title(data: dict[str, Any]) -> str:
    meta = data.get("meta") or {}
    week_end = meta.get("week_end") or ""
    return f"本週市場雷達 Shorts{f'｜{week_end}' if week_end else ''}"


def get_status() -> dict[str, Any]:
    render = _read_render_status()
    pending = _load_weekly_pending()
    video_exists = VIDEO_PATH.exists()

    if pending or video_exists:
        data = (pending or {}).get("data") or _load_weekly_data_file() or {}
        video_path = Path((pending or {}).get("video_path") or VIDEO_PATH)
        video_exists = video_path.exists()
        youtube_video_id = data.get("youtube_video_id") or (pending or {}).get("youtube_video_id") or ""
        threads_id = data.get("threads_id") or (pending or {}).get("threads_id") or ""
        threads_text = _build_threads_text(data) if data else ""

        if render.get("state") == "rendering":
            state = "rendering"
        elif not video_exists:
            state = "missing_video"
        elif youtube_video_id and threads_id:
            state = "published"
        else:
            state = "ready"

        return {
            "state": state,
            "date": data.get("meta", {}).get("week_end", ""),
            "title": _weekly_title(data),
            "published": bool(youtube_video_id and threads_id),
            "youtube_published": bool(youtube_video_id),
            "threads_published": bool(threads_id),
            "youtube_video_id": youtube_video_id,
            "youtube_url": f"https://www.youtube.com/watch?v={youtube_video_id}" if youtube_video_id else "",
            "threads_id": threads_id,
            "threads_text": threads_text,
            "video_exists": video_exists,
            "video_path": str(video_path),
            "preview_url": PREVIEW_URL if video_exists else "",
            "render": render,
        }

    latest_report = load_latest_report()
    if not latest_report:
        return {
            "state": "no_report",
            "published": False,
            "youtube_published": False,
            "threads_published": False,
            "threads_text": "",
            "video_exists": video_exists,
            "video_path": str(VIDEO_PATH),
            "preview_url": PREVIEW_URL if video_exists else "",
            "render": render,
        }

    date_str = latest_report.get("meta", {}).get("date", "")
    if render.get("state") == "rendering":
        state = "rendering"
    elif video_exists:
        state = "ready"
    else:
        state = "missing_video"

    return {
        "state": state,
        "date": date_str,
        "title": "本週市場雷達 Shorts",
        "published": False,
        "youtube_published": False,
        "threads_published": False,
        "youtube_video_id": "",
        "youtube_url": "",
        "threads_id": "",
        "threads_text": "",
        "video_exists": video_exists,
        "video_path": str(VIDEO_PATH),
        "preview_url": PREVIEW_URL if video_exists else "",
        "render": render,
    }


def render_latest() -> dict[str, Any]:
    _write_render_status("rendering", "抓取市場新聞與經濟日曆", 10)
    _write_render_status("rendering", "整理 5 個重大事件", 30)
    _write_render_status("rendering", "產生 Threads 文章草稿", 45)
    _write_render_status("rendering", "生成旁白與短影音素材", 65)
    _write_render_status("rendering", "Remotion 渲染 YouTube Shorts", 85)

    import weekly_shorts

    payload = weekly_shorts.run_weekly_draft()
    video_path = Path(payload.get("video_path") or VIDEO_PATH)
    if not video_path.exists():
        render = _write_render_status("failed", "影片生成失敗", 85, "Remotion 未產出 weekly_short.mp4")
        return {"ok": False, **get_status(), "state": "render_failed", "render": render, "error": render["error"]}

    render = _write_render_status("ready", "影片與 Threads 草稿可預覽", 100)
    return {"ok": True, **get_status(), "state": "ready", "render": render, "preview_url": PREVIEW_URL}


def update_videos_json(data: dict[str, Any], youtube_video_id: str) -> None:
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    videos_path = WEB_DATA_DIR / "videos.json"
    payload = json.loads(videos_path.read_text(encoding="utf-8")) if videos_path.exists() else {"videos": []}

    date_str = data.get("meta", {}).get("week_end", "")
    entry = {
        "video_id": youtube_video_id,
        "date": date_str,
        "title": _weekly_title(data),
    }
    existing = payload.get("videos") or []
    payload["videos"] = [
        item for item in existing
        if item.get("video_id") != youtube_video_id and item.get("date") != date_str
    ]
    payload["videos"].insert(0, entry)
    videos_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_pending(data: dict[str, Any], video_path: Path) -> None:
    import weekly_shorts

    weekly_shorts.save_pending_weekly_short({"data": data, "video_path": video_path})


def _load_publish_draft() -> dict[str, Any] | None:
    pending = _load_weekly_pending()
    if pending:
        return pending
    data = _load_weekly_data_file()
    if data and VIDEO_PATH.exists():
        return {"data": data, "video_path": VIDEO_PATH}
    return None


def publish_latest() -> dict[str, Any]:
    import weekly_shorts

    pending = _load_publish_draft()
    if not pending:
        return {"ok": False, **get_status(), "state": "no_draft", "error": "請先生成短影音與 Threads 草稿"}

    data = pending.get("data") or {}
    video_path = Path(pending.get("video_path") or VIDEO_PATH)
    if data.get("youtube_video_id"):
        return {"ok": True, **get_status(), "state": "already_published"}
    if not video_path.exists():
        return {"ok": False, **get_status(), "state": "missing_video", "error": "找不到 YouTube Shorts 影片，請先生成"}

    youtube_video_id = weekly_shorts.publish_weekly_youtube(video_path, data)
    if not youtube_video_id:
        return {"ok": False, **get_status(), "state": "failed", "error": "YouTube 上傳失敗，請查看 VM log"}

    data["youtube_video_id"] = youtube_video_id
    _save_pending(data, video_path)
    update_videos_json(data, youtube_video_id)

    return {"ok": True, **get_status(), "state": "published"}


def publish_threads_latest() -> dict[str, Any]:
    import weekly_shorts

    pending = _load_publish_draft()
    if not pending:
        return {"ok": False, **get_status(), "state": "no_draft", "error": "請先生成 Threads 草稿"}

    data = pending.get("data") or {}
    video_path = Path(pending.get("video_path") or VIDEO_PATH)
    if data.get("threads_id"):
        return {"ok": True, **get_status(), "state": "already_published"}

    threads_id = weekly_shorts.publish_weekly_threads(data)
    if not threads_id:
        return {"ok": False, **get_status(), "state": "failed", "error": "Threads 發布失敗，請查看 VM log"}

    data["threads_id"] = threads_id
    _save_pending(data, video_path)

    return {"ok": True, **get_status(), "state": "published"}


def _run_cli(action: str) -> int:
    try:
        if action == "status":
            result = {"ok": True, **get_status()}
        elif action == "render-youtube":
            result = render_latest()
        elif action == "publish-youtube":
            result = publish_latest()
        elif action == "publish-threads":
            result = publish_threads_latest()
        else:
            result = {"ok": False, "state": "bad_action", "error": f"unknown action: {action}"}
    except Exception as exc:
        render = _write_render_status("failed", "流程執行失敗", 0, str(exc)) if action == "render-youtube" else _read_render_status()
        result = {
            "ok": False,
            "state": "error",
            "render": render,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def main_cli() -> int:
    parser = argparse.ArgumentParser(description="Dashboard weekly shorts publish helper")
    parser.add_argument("action", choices=["status", "render-youtube", "publish-youtube", "publish-threads"])
    args = parser.parse_args()
    return _run_cli(args.action)


if __name__ == "__main__":
    raise SystemExit(main_cli())
