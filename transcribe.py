"""
meeting-transcriber: unified CLI for meeting transcription.

Usage:
    # Transcribe a meeting (default mode)
    uv run transcribe.py -i audio/meeting.mp4

    # With options
    uv run transcribe.py -i audio/meeting.mp4 --language yue --device mps --format srt,json -o results/

    # Start STT HTTP server
    uv run transcribe.py --server --port 8100 --device mps --model_dir ./models/sensevoice_small_yue
"""

import argparse
import asyncio
import logging
import os
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

# Suppress noisy warnings from third-party libraries
warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")

# Load .env from current working directory
load_dotenv(Path.cwd() / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("transcribe")


# ---------------------------------------------------------------------------
# Transcription pipeline (default mode)
# ---------------------------------------------------------------------------


async def run_transcription(args: argparse.Namespace) -> None:
    """Run the full meeting transcription pipeline in-process."""
    import torchaudio

    from audio_utils import convert_to_wav, prepare_audio_buffer
    from diarizer import MeetingDiarizer
    from output_formats import save_outputs
    from stt_engine import STTEngine

    if not args.input:
        logger.error("Missing required argument: -i / --input")
        sys.exit(1)

    input_path = args.input
    if not os.path.isfile(input_path):
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    # 1. Convert to WAV if needed
    _filename, ext = os.path.splitext(input_path)
    if ext.lower() != ".wav":
        print("1. Converting audio to WAV...")
        input_path = convert_to_wav(input_path)

    # 2. Speaker diarization
    print("2. Running speaker diarization...")
    import torch

    device = torch.device(args.device) if args.device else None
    diarizer = MeetingDiarizer(device=device, max_gap=args.max_gap)
    segments = diarizer.diarize(input_path)
    print(f"   Detected {len(segments)} speech segments.")

    # 3. Load audio into memory
    print("3. Loading audio into memory...")
    waveform, sample_rate = torchaudio.load(input_path)

    # 4. Transcribe segments using in-process STT engine
    print("4. Transcribing segments...")
    engine = STTEngine(
        model_dir=args.model_dir,
        device=args.device,
        language=args.language,
        vad_model=args.vad_model,
        use_itn=args.use_itn,
        merge_vad=args.merge_vad,
        merge_length_s=args.merge_length_s,
    )

    sem = asyncio.Semaphore(args.max_workers)
    final_segments: list[dict] = []

    async def _transcribe_one(seg: dict) -> dict:
        async with sem:
            buf = await asyncio.to_thread(
                prepare_audio_buffer,
                waveform,
                seg["start"],
                seg["end"],
                sample_rate,
                args.padding,
            )
            if buf is None:
                return {**seg, "text": "[Audio Error]"}
            audio_bytes = buf.read()
            result = await asyncio.to_thread(engine.transcribe, audio_bytes)
            text = result.get("text", "").strip() or "[Transcribe Error]"
            return {**seg, "text": text}

    tasks = [_transcribe_one(seg) for seg in segments]
    for coro in tqdm(
        asyncio.as_completed(tasks),
        total=len(tasks),
        desc="   Transcribing",
        unit="seg",
    ):
        final_segments.append(await coro)

    final_segments.sort(key=lambda s: s["start"])

    # 5. Generate output files
    formats = [f.strip() for f in args.format.split(",")]

    if args.output:
        output_dir = args.output
    else:
        audio_dir = os.path.dirname(os.path.abspath(input_path))
        output_dir = os.path.join(audio_dir, "output")

    base_name = Path(input_path).stem

    print("5. Saving outputs...")
    written = save_outputs(final_segments, output_dir, base_name, formats)
    for path in written:
        print(f"   -> {path}")

    print(f"\nDone! {len(written)} file(s) saved to {output_dir}")


# ---------------------------------------------------------------------------
# Server mode
# ---------------------------------------------------------------------------


def run_server(args: argparse.Namespace) -> None:
    """Start the STT HTTP server."""
    from server import run_server as _run_server

    _run_server(
        model_dir=args.model_dir,
        host=args.host,
        port=args.port,
        device=args.device,
        language=args.language,
        vad_model=args.vad_model,
        use_itn=args.use_itn,
        merge_vad=args.merge_vad,
        merge_length_s=args.merge_length_s,
    )


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="meeting-transcriber: one-command meeting transcription",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Transcribe a meeting file\n"
            "  uv run transcribe.py -i audio/meeting.mp4 --device mps\n\n"
            "  # Start STT HTTP server\n"
            "  uv run transcribe.py --server --port 8100 --device mps "
            "--model_dir ./models/sensevoice_small_yue\n"
        ),
    )

    # -- Mode selection --
    parser.add_argument(
        "--server",
        action="store_true",
        help="Start the STT HTTP server instead of transcribing",
    )

    # -- Common options --
    parser.add_argument("--device", type=str, default="cpu", help="Device: cpu, mps, cuda (default: cpu)")
    parser.add_argument("--model_dir", type=str, default="iic/SenseVoiceSmall", help="SenseVoice model directory")

    # -- Transcription mode options --
    parser.add_argument("-i", "--input", type=str, help="Input audio/video file path")
    parser.add_argument("--language", type=str, default="auto", help="Language: auto, zh, en, yue, ja, ko (default: auto)")
    parser.add_argument(
        "--format",
        type=str,
        default="txt",
        help="Comma-separated output formats (default: txt; e.g. srt,json,txt,vtt)",
    )
    parser.add_argument("-o", "--output", type=str, default=None, help="Output directory (default: <input_dir>/output/)")
    parser.add_argument("--max-workers", type=int, default=1, help="Max concurrent transcriptions (default: 1 for in-process safety)")
    parser.add_argument("--padding", type=float, default=0.3, help="Audio segment padding in seconds (default: 0.3)")
    parser.add_argument("--max-gap", type=float, default=2.0, help="Max gap to merge same-speaker segments (default: 2.0s)")

    # -- Server mode options --
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--vad_model", type=str, default="fsmn-vad", help="VAD model name (default: fsmn-vad)")
    parser.add_argument("--use_itn", type=bool, default=True, help="Use inverse text normalization (default: True)")
    parser.add_argument("--merge_vad", type=bool, default=True, help="Merge VAD segments (default: True)")
    parser.add_argument("--merge_length_s", type=int, default=15, help="VAD merge max length in seconds (default: 15)")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.server:
        run_server(args)
    else:
        asyncio.run(run_transcription(args))


if __name__ == "__main__":
    main()
