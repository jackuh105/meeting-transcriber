"""
Speaker diarization using PyAnnote.audio.

Detects speakers and segments the audio into per-speaker turns.
"""

import logging
import os

import pyannote.audio.core.task
import torch
from pyannote.audio import Pipeline
from pyannote.audio.pipelines.utils.hook import ProgressHook

logger = logging.getLogger(__name__)

# Register PyAnnote types for torch safe loading (required on torch >= 2.6)
torch.serialization.add_safe_globals(
    [
        pyannote.audio.core.task.Specifications,
        pyannote.audio.core.task.Problem,
        pyannote.audio.core.task.Resolution,
    ]
)


class MeetingDiarizer:
    """Wrapper around PyAnnote speaker-diarization pipeline."""

    def __init__(
        self,
        hf_token: str | None = None,
        device: torch.device | None = None,
        max_gap: float = 2.0,
    ):
        token = hf_token or os.getenv("HF_TOKEN")
        if not token:
            raise ValueError(
                "HuggingFace token is required. Set HF_TOKEN in .env or pass hf_token=."
            )

        logger.info("Loading PyAnnote speaker-diarization pipeline...")
        self.pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-community-1",
            token=token,
        )

        if device is None:
            device = torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu")
        self.pipeline.to(device)
        self.device = device
        self.max_gap = max_gap
        logger.info("Diarization pipeline ready (device=%s).", device)

    def diarize(self, audio_path: str) -> list[dict]:
        """
        Run speaker diarization on an audio file.

        Returns a sorted list of segments:
            [{"start": float, "end": float, "speaker": str}, ...]
        """
        logger.info("Running diarization on %s ...", audio_path)
        with ProgressHook() as hook:
            output = self.pipeline(audio_path, hook=hook)

        speaker_tracks = self._get_speaker_tracks(output)
        merged = self._merge_segments(speaker_tracks, max_gap=self.max_gap)
        merged.sort(key=lambda s: s["start"])
        logger.info("Diarization complete: %d segments detected.", len(merged))
        return merged

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_speaker_tracks(output) -> dict[str, list[dict]]:
        speaker_tracks: dict[str, list[dict]] = {}
        for turn, speaker in output.speaker_diarization:
            speaker_tracks.setdefault(speaker, []).append(
                {
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker,
                }
            )
        return speaker_tracks

    @staticmethod
    def _merge_segments(
        speaker_tracks: dict[str, list[dict]], max_gap: float = 2.0
    ) -> list[dict]:
        """Merge nearby segments from the same speaker."""
        merged: list[dict] = []
        for _speaker, segments in speaker_tracks.items():
            segments.sort(key=lambda x: x["start"])
            if not segments:
                continue

            current = segments[0]
            for nxt in segments[1:]:
                gap = nxt["start"] - current["end"]
                if gap <= max_gap:
                    current["end"] = max(current["end"], nxt["end"])
                else:
                    merged.append(current)
                    current = nxt
            merged.append(current)
        return merged
