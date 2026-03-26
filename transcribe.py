"""
Step 1b — 語音轉文字（Whisper）
將兩支 mp3 分別轉錄為純文字逐字稿，儲存至 output/transcripts/。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import whisper

from config import AUDIO_DIR, CHANNELS, TRANSCRIPT_DIR, WHISPER_MODEL

log = logging.getLogger(__name__)

_model: whisper.Whisper | None = None


def _get_model() -> whisper.Whisper:
    global _model
    if _model is None:
        log.info("載入 Whisper 模型：%s（首次載入需時較長）", WHISPER_MODEL)
        _model = whisper.load_model(WHISPER_MODEL)
    return _model


def transcribe_audio(channel_key: str, audio_path: str | Path | None = None) -> str | None:
    """
    轉錄指定頻道的音檔，回傳純文字逐字稿。
    同時將結果儲存為 output/transcripts/<channel_key>.txt
    """
    ch = CHANNELS[channel_key]
    audio_file = Path(audio_path) if audio_path else AUDIO_DIR / ch["audio_filename"]

    if not audio_file.exists():
        log.error("[%s] 音檔不存在：%s", channel_key, audio_file)
        return None

    log.info("[%s] 開始轉錄：%s", ch["name"], audio_file)
    model = _get_model()

    result = model.transcribe(
        str(audio_file),
        language="zh",
        verbose=False,
        fp16=False,         # CPU 環境請保持 False；GPU 可改 True
    )

    text: str = result["text"].strip()

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    out_txt = TRANSCRIPT_DIR / f"{channel_key}.txt"
    out_txt.write_text(text, encoding="utf-8")
    log.info("[%s] 逐字稿已儲存：%s（%d 字）", ch["name"], out_txt, len(text))

    return text


def transcribe_both() -> dict[str, str | None]:
    """同時轉錄兩個頻道（依序執行，Whisper 本身已多執行緒）。"""
    return {key: transcribe_audio(key) for key in CHANNELS}


def load_transcript(channel_key: str) -> str | None:
    """從磁碟讀取已儲存的逐字稿（避免重複轉錄）。"""
    path = TRANSCRIPT_DIR / f"{channel_key}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


if __name__ == "__main__":
    results = transcribe_both()
    for key, text in results.items():
        status = "✅" if text else "❌"
        chars = len(text) if text else 0
        print(f"{status} {CHANNELS[key]['name']}：{chars} 字")
