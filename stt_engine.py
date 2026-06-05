"""
In-process SenseVoice STT engine.

Wraps FunASR's AutoModel for direct (non-HTTP) transcription.
"""

import gc
import io
import logging
from pathlib import Path
from typing import Union

import ffmpeg
import numpy as np
import soundfile as sf
import torch
import torchaudio
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from opencc import OpenCC

logger = logging.getLogger(__name__)


class STTEngine:
    """In-process speech-to-text engine using SenseVoice via FunASR."""

    def __init__(
        self,
        model_dir: str = "iic/SenseVoiceSmall",
        remote_code: str = "./model.py",
        device: str = "cpu",
        ncpu: int = 4,
        language: str = "auto",
        vad_model: str = "fsmn-vad",
        vad_kwargs: int = 30000,
        use_itn: bool = True,
        merge_vad: bool = True,
        merge_length_s: int = 15,
    ):
        logger.info("Loading SenseVoice model (dir=%s, device=%s, vad=%s)...", model_dir, device, vad_model)
        # When vad_model is None or empty, skip VAD entirely.
        init_kwargs: dict = dict(
            model=model_dir,
            trust_remote_code=True,
            remote_code=remote_code,
            device=device,
            ncpu=ncpu,
            disable_pbar=True,
            disable_log=True,
        )
        if vad_model:
            init_kwargs["vad_model"] = vad_model
            init_kwargs["vad_kwargs"] = {"max_single_segment_time": vad_kwargs}
        self.model = AutoModel(**init_kwargs)
        self._device = device
        self._is_funasr_nano = "Fun-ASR-Nano" in model_dir
        self.param_dict = {
            "language": language,
            "use_itn": use_itn,
            "merge_vad": merge_vad,
            "merge_length_s": merge_length_s,
            "output_dir": None,
        }
        self.s2t = OpenCC("s2t")
        logger.info("Model loaded successfully.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe(self, audio_input: Union[str, bytes, np.ndarray]) -> dict:
        """
        Transcribe audio and return the result text.

        Args:
            audio_input:
                - str: file path to an audio file
                - bytes: raw audio file bytes (will be decoded in-memory)
                - np.ndarray: pre-processed 16 kHz mono float32 samples

        Returns:
            {"text": "..."} with the post-processed transcript.
        """
        rec_results = None
        try:
            audio_array = None
            if isinstance(audio_input, str):
                # File path – let FunASR handle loading
                rec_results = self.model.generate(
                    input=[audio_input], cache={}, batch_size=1, is_final=True, **self.param_dict
                )
            elif isinstance(audio_input, bytes):
                audio_array = self._process_bytes(audio_input)
                # Match reference server: pass numpy array without cache/batch_size
                rec_results = self.model.generate(
                    input=audio_array, is_final=True, **self.param_dict
                )
            elif isinstance(audio_input, np.ndarray):
                rec_results = self.model.generate(
                    input=audio_input, is_final=True, **self.param_dict
                )
            else:
                raise TypeError(f"Unsupported audio_input type: {type(audio_input)}")
        except Exception as exc:
            logger.error("Transcription error: %s", exc)
            return {"text": "", "error": str(exc)}

        # Extract text before cleanup so rec_results can be freed
        result = self._format_result(rec_results)

        # Release intermediate arrays and flush MPS cache to prevent
        # memory accumulation across consecutive generate() calls.
        del rec_results, audio_array
        gc.collect()
        if self._device == "mps" and torch.backends.mps.is_available():
            torch.mps.empty_cache()

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_bytes(self, audio_bytes: bytes) -> np.ndarray:
        """Decode audio bytes to a 16 kHz mono float32 numpy array."""
        try:
            return _process_audio_bytes_torchaudio(audio_bytes)
        except Exception as exc:
            logger.warning("torchaudio decoding failed (%s), falling back to ffmpeg", exc)
            # Write to a temp buffer file for ffmpeg
            import tempfile, os

            with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            try:
                pcm_bytes = _process_audio_bytes_ffmpeg(tmp_path)
                audio_array = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                return audio_array
            finally:
                os.unlink(tmp_path)

    def _format_result(self, rec_results) -> dict:
        if not rec_results:
            return {"text": ""}
        rec = rec_results[0]
        raw_text = rec.get("text", "")
        if not raw_text:
            return {"text": ""}
        text = rich_transcription_postprocess(raw_text)
        text = self.s2t.convert(text)
        return {"text": text}


# ---------------------------------------------------------------------------
# Module-level audio processing utilities
# ---------------------------------------------------------------------------


def _process_audio_bytes_torchaudio(audio_bytes: bytes) -> np.ndarray:
    """
    Decode audio bytes in memory using soundfile + torchaudio.

    Returns a 16 kHz mono float32 numpy array.
    """
    audio_buffer = io.BytesIO(audio_bytes)
    waveform, sample_rate = sf.read(audio_buffer, dtype="float32")

    if waveform.ndim == 1:
        waveform = waveform[np.newaxis, :]
    else:
        waveform = waveform.T

    waveform_tensor = torch.from_numpy(waveform)

    if waveform_tensor.shape[0] > 1:
        waveform_tensor = torch.mean(waveform_tensor, dim=0, keepdim=True)

    if sample_rate != 16000:
        resampler = torchaudio.transforms.Resample(sample_rate, 16000)
        waveform_tensor = resampler(waveform_tensor)

    return waveform_tensor.squeeze().numpy()


def _process_audio_bytes_ffmpeg(audio_path: str) -> bytes:
    """
    Decode audio using ffmpeg as a fallback.

    Returns PCM audio bytes (16 kHz, mono, s16le).
    """
    audio_bytes, _ = (
        ffmpeg.input(audio_path, threads=0)
        .output("-", format="s16le", acodec="pcm_s16le", ac=1, ar=16000)
        .run(cmd=["ffmpeg", "-nostdin"], capture_stdout=True, capture_stderr=True)
    )
    return audio_bytes
