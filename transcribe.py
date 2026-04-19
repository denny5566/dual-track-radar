"""
Step 2 — 語音轉文字（faster-whisper 本地 + Groq Whisper API 備援）
將音檔切片後分段轉錄為純文字逐字稿，儲存至 output/transcripts/。

後端選擇（WHISPER_BACKEND 環境變數）：
  auto  → 優先嘗試 Groq API，失敗時 fallback 到 faster-whisper（預設）
  groq  → 強制使用 Groq API（無 GROQ_API_KEY 時報錯）
  local → 強制使用 faster-whisper（本地）

關鍵設定（PRD v2 § 2.2）：
  - faster-whisper：vad_filter=True 啟用 Silero VAD，language="zh"
  - Groq：model="whisper-large-v3-turbo"，語言指定 zh，2000 次/日免費
  - 超過 CHUNK_DURATION_MS 的音檔會先用 pydub 切片再逐段轉錄
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from pydub import AudioSegment

from config import (
    AUDIO_DIR,
    CHANNELS,
    CHUNK_DURATION_MS,
    GROQ_API_KEY,
    TRANSCRIPT_DIR,
    WHISPER_BACKEND,
    WHISPER_COMPUTE,
    WHISPER_DEVICE,
    WHISPER_MODEL,
)

log = logging.getLogger(__name__)

# ── 本地 faster-whisper（懶載入）────────────────────────────────────────────
_local_model = None


def _get_local_model():
    global _local_model
    if _local_model is None:
        from faster_whisper import WhisperModel
        log.info(
            "載入 faster-whisper 模型：%s（device=%s, compute=%s）",
            WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE,
        )
        _local_model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE,
        )
    return _local_model


# ── 音檔切片（共用）─────────────────────────────────────────────────────────
def _chunk_audio(audio_path: Path) -> list[Path]:
    """
    若音檔超過 CHUNK_DURATION_MS，以 pydub 切成多段並存入暫存目錄。
    回傳切片路徑列表（僅一段時直接回傳原始路徑）。
    """
    audio = AudioSegment.from_mp3(str(audio_path))
    duration_ms = len(audio)

    if duration_ms <= CHUNK_DURATION_MS:
        return [audio_path]

    chunks_dir = audio_path.parent / f"{audio_path.stem}_chunks"
    chunks_dir.mkdir(exist_ok=True)
    chunk_paths: list[Path] = []

    for i, start in enumerate(range(0, duration_ms, CHUNK_DURATION_MS)):
        chunk = audio[start: start + CHUNK_DURATION_MS]
        chunk_path = chunks_dir / f"chunk_{i:03d}.mp3"
        chunk.export(str(chunk_path), format="mp3")
        chunk_paths.append(chunk_path)

    log.info(
        "音檔已切割為 %d 片段（每段 %d 分鐘）：%s",
        len(chunk_paths), CHUNK_DURATION_MS // 60000, chunks_dir,
    )
    return chunk_paths


def _cleanup_chunks(chunk_paths: list[Path]) -> None:
    """清除切片暫存目錄（若有切片的話）。"""
    if len(chunk_paths) > 1:
        chunks_dir = chunk_paths[0].parent
        for p in chunk_paths:
            p.unlink(missing_ok=True)
        chunks_dir.rmdir()


# ── Groq Whisper 後端 ────────────────────────────────────────────────────────
def _transcribe_file_groq(audio_file: Path) -> str:
    """
    以 Groq Whisper API 轉錄單一音檔，回傳純文字。
    使用 whisper-large-v3-turbo（速度快，繁中準確率佳）。
    """
    import groq  # pip install groq

    client = groq.Groq(api_key=GROQ_API_KEY)
    with open(audio_file, "rb") as f:
        response = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=f,
            language="zh",
            response_format="text",
        )
    # Groq SDK 回傳的 response 在 text 模式下直接是字串
    return response.strip() if isinstance(response, str) else response.text.strip()


def _transcribe_chunks_groq(chunk_paths: list[Path], channel_name: str) -> list[str]:
    """逐片段使用 Groq 轉錄，遇速率限制時退避重試（最多 3 次）。"""
    texts: list[str] = []
    total = len(chunk_paths)
    for i, chunk_path in enumerate(chunk_paths, 1):
        log.info("[%s] Groq 轉錄 %d/%d：%s", channel_name, i, total, chunk_path.name)
        for attempt in range(3):
            try:
                part = _transcribe_file_groq(chunk_path)
                if part:
                    texts.append(part)
                break
            except Exception as e:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                log.warning(
                    "[%s] Groq 轉錄失敗（第 %d 次）：%s；%d 秒後重試",
                    channel_name, attempt + 1, e, wait,
                )
                if attempt < 2:
                    time.sleep(wait)
                else:
                    raise
    return texts


# ── faster-whisper 後端 ───────────────────────────────────────────────────────
def _transcribe_file_local(audio_file: Path) -> str:
    """
    以 faster-whisper 轉錄單一音檔，回傳純文字。
    啟用 vad_filter=True 以過濾無人聲片段（防止 Whisper 幻覺文字）。
    """
    model = _get_local_model()
    segments, _info = model.transcribe(
        str(audio_file),
        language="zh",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )
    return "".join(seg.text for seg in segments).strip()


def _transcribe_chunks_local(chunk_paths: list[Path], channel_name: str) -> list[str]:
    """逐片段使用 faster-whisper 轉錄。"""
    texts: list[str] = []
    total = len(chunk_paths)
    for i, chunk_path in enumerate(chunk_paths, 1):
        log.info("[%s] 本地轉錄 %d/%d：%s", channel_name, i, total, chunk_path.name)
        part = _transcribe_file_local(chunk_path)
        if part:
            texts.append(part)
    return texts


# ── 主要轉錄入口 ─────────────────────────────────────────────────────────────
def transcribe_audio(channel_key: str, audio_path: str | Path | None = None) -> str | None:
    """
    轉錄指定頻道的音檔，回傳純文字逐字稿。
    同時將結果儲存為 output/transcripts/<channel_key>.txt。

    後端優先順序（由 WHISPER_BACKEND 控制）：
      auto  → Groq 優先，失敗 fallback 到 faster-whisper
      groq  → 僅 Groq
      local → 僅 faster-whisper
    """
    ch = CHANNELS[channel_key]
    audio_file = Path(audio_path) if audio_path else AUDIO_DIR / ch["audio_filename"]

    if not audio_file.exists():
        existing = load_transcript(channel_key)
        if existing:
            log.info("[%s] 無音檔，沿用既有逐字稿：%s", ch["name"], TRANSCRIPT_DIR / f"{channel_key}.txt")
            return existing
        log.error("[%s] 音檔不存在：%s", channel_key, audio_file)
        return None

    log.info("[%s] 開始轉錄（backend=%s）：%s", ch["name"], WHISPER_BACKEND, audio_file)

    chunk_paths = _chunk_audio(audio_file)
    texts: list[str] = []

    try:
        if WHISPER_BACKEND == "groq":
            if not GROQ_API_KEY:
                raise RuntimeError("GROQ_API_KEY 未設定，無法使用 Groq 後端")
            texts = _transcribe_chunks_groq(chunk_paths, ch["name"])

        elif WHISPER_BACKEND == "local":
            texts = _transcribe_chunks_local(chunk_paths, ch["name"])

        else:  # auto
            if GROQ_API_KEY:
                try:
                    log.info("[%s] 嘗試 Groq 後端...", ch["name"])
                    texts = _transcribe_chunks_groq(chunk_paths, ch["name"])
                    log.info("[%s] Groq 轉錄成功", ch["name"])
                except Exception as groq_err:
                    log.warning(
                        "[%s] Groq 失敗，切換 faster-whisper：%s", ch["name"], groq_err
                    )
                    texts = _transcribe_chunks_local(chunk_paths, ch["name"])
            else:
                log.info("[%s] 無 GROQ_API_KEY，使用 faster-whisper", ch["name"])
                texts = _transcribe_chunks_local(chunk_paths, ch["name"])

    finally:
        _cleanup_chunks(chunk_paths)

    text = " ".join(texts)

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    out_txt = TRANSCRIPT_DIR / f"{channel_key}.txt"
    out_txt.write_text(text, encoding="utf-8")
    log.info("[%s] 逐字稿已儲存：%s（%d 字）", ch["name"], out_txt, len(text))

    return text


def transcribe_both() -> dict[str, str | None]:
    """依序轉錄兩個頻道（faster-whisper 本身已多執行緒，不需額外並行）。"""
    return {key: transcribe_audio(key) for key in CHANNELS}


def load_transcript(channel_key: str) -> str | None:
    """從磁碟讀取已儲存的逐字稿（避免重複轉錄）。"""
    path = TRANSCRIPT_DIR / f"{channel_key}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def load_cleaned_transcript(channel_key: str) -> str | None:
    """從磁碟讀取前處理後的清洗逐字稿。"""
    path = TRANSCRIPT_DIR / f"{channel_key}_cleaned.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


if __name__ == "__main__":
    results = transcribe_both()
    for key, text in results.items():
        status = "[OK]" if text else "[FAIL]"
        chars = len(text) if text else 0
        print(f"{status} {CHANNELS[key]['name']}：{chars} 字")
