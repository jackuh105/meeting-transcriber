"""
Audio utility functions shared across the meeting-transcriber project.

- Format conversion (ffmpeg)
- Segment extraction (torchaudio)
- In-memory audio decoding (soundfile / ffmpeg fallback)
"""

import io
import logging
import os
import subprocess
from typing import Optional

import numpy as np
import soundfile as sf
import torch
import torchaudio

logger = logging.getLogger(__name__)


def convert_to_wav(input_path: str) -> str:
    """
    Convert any supported audio/video file to 16 kHz mono WAV using ffmpeg.

    Returns the path of the converted WAV file (same directory, .wav extension).
    Raises subprocess.CalledProcessError on failure.
    """
    filename, _ext = os.path.splitext(input_path)
    output_path = filename + ".wav"
    command = [
        "ffmpeg",
        "-i",
        input_path,
        "-ar",
        "16000",
        "-ac",
        "1",
        "-vn",
        "-y",
        output_path,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True)
        logger.info("Converted to WAV: %s", output_path)
        return output_path
    except subprocess.CalledProcessError as exc:
        logger.error("FFmpeg conversion failed: %s", exc.stderr.decode())
        raise


def prepare_audio_buffer(
    waveform: torch.Tensor,
    start_time: float,
    end_time: float,
    sample_rate: int,
    padding: float = 0.3,
) -> Optional[io.BytesIO]:
    """
    Extract a segment from a waveform and return it as an in-memory WAV buffer.

    Args:
        waveform:  (channels, samples) float tensor
        start_time: segment start in seconds
        end_time: segment end in seconds
        sample_rate: audio sample rate (Hz)
        padding: extra padding in seconds added to each side

    Returns:
        A BytesIO buffer containing the WAV data, or None on error.
    """
    try:
        total_frames = waveform.shape[1]
        s_time = max(0.0, start_time - padding)
        e_time = end_time + padding
        start_frame = int(s_time * sample_rate)
        end_frame = min(int(e_time * sample_rate), total_frames)
        segment_waveform = waveform[:, start_frame:end_frame]

        buffer = io.BytesIO()
        # soundfile supports BytesIO natively; torchaudio.save does not
        # (torchcodec's AudioEncoder requires a real file path).
        segment_np = segment_waveform.numpy()
        # soundfile expects (frames, channels) for multi-channel, or (frames,) for mono
        if segment_np.ndim == 2:
            segment_np = segment_np.T  # (channels, frames) -> (frames, channels)
        sf.write(buffer, segment_np, sample_rate, format="WAV", subtype="PCM_16")
        buffer.seek(0)
        return buffer
    except Exception as exc:
        logger.error("Error in prepare_audio_buffer: %s", exc)
        return None


def process_audio_bytes_torchaudio(audio_bytes: bytes) -> np.ndarray:
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
