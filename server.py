"""
FastAPI HTTP server for the SenseVoice STT engine.

Provides two endpoints:
  - POST /v1/audio/transcriptions  (OpenAI Whisper API compatible)
  - POST /recognition              (legacy)

Used when running `transcribe.py --server`.
"""

import logging
import os
import uuid
from typing import Optional

import aiofiles
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import Response

from stt_engine import STTEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAI-compatible response formatting helpers
# ---------------------------------------------------------------------------


def _format_srt_time(seconds: float) -> str:
    if seconds is None:
        return "00:00:10,000"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_vtt_time(seconds: float) -> str:
    if seconds is None:
        return "00:00:10.000"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _format_srt(text: str, duration: float | None = None) -> str:
    start = "00:00:00,000"
    end = _format_srt_time(duration) if duration else "00:00:10,000"
    return f"1\n{start} --> {end}\n{text}\n"


def _format_vtt(text: str, duration: float | None = None) -> str:
    start = "00:00:00.000"
    end = _format_vtt_time(duration) if duration else "00:00:10.000"
    return f"WEBVTT\n\n1\n{start} --> {end}\n{text}\n"


def _format_transcription_response(
    text: str,
    response_format: str = "json",
    duration: float | None = None,
    language: str | None = None,
):
    if response_format == "text":
        return text
    elif response_format == "json":
        return {"text": text}
    elif response_format == "verbose_json":
        return {
            "task": "transcribe",
            "language": language or "zh",
            "duration": duration,
            "text": text,
        }
    elif response_format == "srt":
        return _format_srt(text, duration)
    elif response_format == "vtt":
        return _format_vtt(text, duration)
    else:
        return {"text": text}


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------


def create_app(engine: STTEngine, temp_dir: str = "temp_dir/") -> FastAPI:
    """Create and return the FastAPI application bound to an STTEngine."""

    os.makedirs(temp_dir, exist_ok=True)
    app = FastAPI(title="Meeting-Transcriber STT Server")

    # ---- Legacy endpoint --------------------------------------------------

    @app.post("/recognition")
    async def api_recognition(audio: UploadFile = File(..., description="audio file")):
        content = await audio.read()
        try:
            suffix = audio.filename.split(".")[-1] if "." in audio.filename else "wav"
            audio_path = f"{temp_dir}/{uuid.uuid1()}.{suffix}"
            async with aiofiles.open(audio_path, "wb") as out_file:
                await out_file.write(content)

            result = engine.transcribe(content)

            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as exc:
            logger.error("Audio read error: %s", exc)
            return {"msg": f"Audio read error: {exc}", "code": 1}

        return {"text": result.get("text", ""), "code": 0}

    # ---- OpenAI-compatible endpoint ---------------------------------------

    @app.post("/v1/audio/transcriptions")
    async def openai_transcriptions(
        file: UploadFile = File(..., description="audio file"),
        model_name: Optional[str] = Form("sensevoice", alias="model"),
        language: Optional[str] = Form(None),
        prompt: Optional[str] = Form(None),
        response_format: Optional[str] = Form("json"),
        temperature: Optional[float] = Form(0),
    ):
        content = await file.read()

        try:
            suffix = file.filename.split(".")[-1] if "." in file.filename else "wav"
            audio_path = f"{temp_dir}/{uuid.uuid1()}.{suffix}"
            async with aiofiles.open(audio_path, "wb") as out_file:
                await out_file.write(content)

            result = engine.transcribe(content)

            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as exc:
            logger.error("Audio processing error: %s", exc)
            return {"error": {"message": "Audio file processing failed", "type": "invalid_request_error"}}

        try:
            text = result.get("text", "")
            formatted = _format_transcription_response(
                text=text,
                response_format=response_format or "json",
                language=language,
            )

            if response_format in ("text", "srt", "vtt"):
                return Response(content=formatted, media_type="text/plain")
            return formatted
        except Exception as exc:
            logger.error("Formatting error: %s", exc)
            return {"error": {"message": str(exc), "type": "server_error"}}

    return app


# ---------------------------------------------------------------------------
# Standalone runner (called from transcribe.py)
# ---------------------------------------------------------------------------


def run_server(
    model_dir: str,
    host: str = "0.0.0.0",
    port: int = 8000,
    device: str = "cpu",
    language: str = "auto",
    vad_model: str = "fsmn-vad",
    use_itn: bool = True,
    merge_vad: bool = True,
    merge_length_s: int = 15,
    ncpu: int = 4,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
    temp_dir: str = "temp_dir/",
):
    """Build the STT engine and start the HTTP server."""
    engine = STTEngine(
        model_dir=model_dir,
        device=device,
        language=language,
        vad_model=vad_model,
        use_itn=use_itn,
        merge_vad=merge_vad,
        merge_length_s=merge_length_s,
        ncpu=ncpu,
    )
    app = create_app(engine, temp_dir=temp_dir)
    uvicorn.run(app, host=host, port=port, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile)
