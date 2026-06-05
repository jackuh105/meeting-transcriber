"""
Output format generators for meeting transcription results.

Supports: SRT, VTT, plain text (TXT), and structured JSON.
"""

import json
import logging
import os
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Time formatting helpers
# ---------------------------------------------------------------------------


def _format_time_srt(seconds: float) -> str:
    """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_time_vtt(seconds: float) -> str:
    """Format seconds as WebVTT timestamp: HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


# ---------------------------------------------------------------------------
# Format generators
# ---------------------------------------------------------------------------


def generate_srt(segments: list[dict]) -> str:
    """
    Generate SRT subtitle content.

    Each segment dict must contain: start, end, speaker, text.
    """
    blocks: list[str] = []
    for i, seg in enumerate(segments, 1):
        start = _format_time_srt(seg["start"])
        end = _format_time_srt(seg["end"])
        text = f"[{seg['speaker']}] {seg['text']}"
        blocks.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(blocks)


def generate_vtt(segments: list[dict]) -> str:
    """
    Generate WebVTT subtitle content.

    Each segment dict must contain: start, end, speaker, text.
    """
    lines: list[str] = ["WEBVTT\n"]
    for i, seg in enumerate(segments, 1):
        start = _format_time_vtt(seg["start"])
        end = _format_time_vtt(seg["end"])
        text = f"[{seg['speaker']}] {seg['text']}"
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def generate_txt(segments: list[dict]) -> str:
    """
    Generate plain text transcript.

    Format per line: [HH:MM:SS --> HH:MM:SS] [SPEAKER] text
    """
    lines: list[str] = []
    for seg in segments:
        start = _format_time_srt(seg["start"])
        end = _format_time_srt(seg["end"])
        lines.append(f"[{start} --> {end}] [{seg['speaker']}] {seg['text']}")
    return "\n".join(lines)


def generate_json(segments: list[dict]) -> dict:
    """
    Generate structured JSON output.

    Returns a dict with a top-level "segments" list.
    """
    return {
        "segments": [
            {
                "start": seg["start"],
                "end": seg["end"],
                "speaker": seg["speaker"],
                "text": seg["text"],
            }
            for seg in segments
        ]
    }


# ---------------------------------------------------------------------------
# Output persistence
# ---------------------------------------------------------------------------

_FORMAT_MAP = {
    "srt": (generate_srt, ".srt"),
    "vtt": (generate_vtt, ".vtt"),
    "txt": (generate_txt, ".txt"),
    "json": (generate_json, ".json"),
}


def save_outputs(
    segments: list[dict],
    output_dir: str,
    base_name: str,
    formats: Iterable[str],
) -> list[str]:
    """
    Save transcription results in the requested formats.

    Args:
        segments: list of segment dicts (start, end, speaker, text)
        output_dir: directory to write output files
        base_name: filename stem (without extension)
        formats: iterable of format strings, e.g. ["srt", "vtt", "txt", "json"]

    Returns:
        List of file paths that were written.
    """
    os.makedirs(output_dir, exist_ok=True)
    written: list[str] = []

    for fmt in formats:
        fmt = fmt.strip().lower()
        if fmt not in _FORMAT_MAP:
            logger.warning("Unknown output format '%s', skipping.", fmt)
            continue

        generator, ext = _FORMAT_MAP[fmt]
        content = generator(segments)
        filepath = os.path.join(output_dir, f"{base_name}{ext}")

        if fmt == "json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        written.append(filepath)
        logger.info("Saved %s output: %s", fmt.upper(), filepath)

    return written
