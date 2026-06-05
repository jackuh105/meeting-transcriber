# Installation & Setup

<cite>
**Referenced Files in This Document**
- [README.md](file://README.md)
- [pyproject.toml](file://pyproject.toml)
- [run.sh](file://run.sh)
- [transcribe.py](file://transcribe.py)
- [stt_engine.py](file://stt_engine.py)
- [diarizer.py](file://diarizer.py)
- [audio_utils.py](file://audio_utils.py)
- [server.py](file://server.py)
- [output_formats.py](file://output_formats.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Step-by-Step Installation](#step-by-step-installation)
4. [Platform-Specific Setup](#platform-specific-setup)
5. [Environment Configuration](#environment-configuration)
6. [Verification Steps](#verification-steps)
7. [Common Issues & Troubleshooting](#common-issues--troubleshooting)
8. [First-Time Usage Verification](#first-time-usage-verification)
9. [Conclusion](#conclusion)

## Introduction

Meeting Transcriber is a comprehensive speech-to-text solution that combines automatic speaker diarization with high-precision voice recognition. The system automatically detects different speakers in meetings and generates synchronized transcripts with speaker attribution across multiple output formats including SRT, VTT, TXT, and JSON.

The system leverages cutting-edge technologies including PyAnnote.audio for speaker separation and SenseVoice (FunASR) for accurate speech recognition, supporting multiple languages including Chinese, English, Cantonese, Japanese, and Korean.

## Prerequisites

Before installing Meeting Transcriber, ensure your system meets the following requirements:

### Core Dependencies
- **Python 3.11+**: The project requires Python 3.11 or later for optimal compatibility
- **FFmpeg 4-8**: Essential for audio format conversion and processing
- **uv Package Manager**: Modern Python dependency management tool
- **HuggingFace Account**: Required for accessing PyAnnote models
- **SenseVoice Model**: Can be downloaded automatically or specified locally

### Hardware Requirements
- **CPU**: Minimum Intel i5 or AMD Ryzen 5 equivalent
- **GPU**: Optional but recommended for CUDA acceleration (NVIDIA)
- **Memory**: Minimum 8GB RAM for reliable operation
- **Storage**: At least 2GB free space for model downloads

**Section sources**
- [README.md:14-21](file://README.md#L14-L21)
- [pyproject.toml:6](file://pyproject.toml#L6)

## Step-by-Step Installation

### Step 1: Install Python Dependencies

The primary installation method uses the uv package manager:

```bash
# Install all project dependencies
uv sync
```

This command reads the project configuration and installs all required packages including:
- PyAnnote.audio for speaker diarization
- FunASR/SenseVoice for speech recognition
- FastAPI for HTTP server functionality
- Torch ecosystem for GPU acceleration

### Step 2: Configure Environment Variables

Create a local environment configuration file:

```bash
# Copy the example configuration
cp .env.example .env
```

Edit the `.env` file to include your HuggingFace token:

```env
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx
```

**Important**: You must agree to the PyAnnote model terms on HuggingFace before using the system.

### Step 3: Verify Installation

Test your installation with a basic command:

```bash
uv run transcribe.py --help
```

This should display the available command-line options and confirm all dependencies are properly installed.

**Section sources**
- [README.md:22-36](file://README.md#L22-L36)
- [run.sh:1-7](file://run.sh#L1-L7)
- [transcribe.py:230-240](file://transcribe.py#L230-L240)

## Platform-Specific Setup

### macOS Installation

For macOS users, use Homebrew to install FFmpeg:

```bash
# Install FFmpeg using Homebrew
brew install ffmpeg
```

Verify installation:
```bash
ffmpeg -version
```

### Ubuntu/Debian Systems

For Ubuntu and Debian-based Linux distributions:

```bash
# Update package index
sudo apt-get update

# Install FFmpeg
sudo apt-get install ffmpeg
```

Verify installation:
```bash
ffmpeg -version
```

### Windows Users

Windows users should use WSL2 or install FFmpeg through Chocolatey:

```bash
# Using Chocolatey
choco install ffmpeg
```

Or download FFmpeg binaries from the official website and add to PATH.

**Section sources**
- [README.md:17](file://README.md#L17)
- [README.md:197-203](file://README.md#L197-L203)

## Environment Configuration

### Required Environment Variables

The system primarily relies on one critical environment variable:

| Variable | Purpose | Example Value |
|----------|---------|---------------|
| `HF_TOKEN` | HuggingFace authentication token | `hf_xxxxxxxxxxxxxxxxxxxx` |

### Model Configuration

The system supports flexible model configuration:

- **Default Model**: `iic/SenseVoiceSmall` (automatically downloaded)
- **Custom Path**: Specify local model directory using `--model_dir`
- **Language Support**: Automatic detection or explicit language selection

### Device Selection

Choose the optimal processing device:

| Device | Description | Performance |
|--------|-------------|-------------|
| `cpu` | Central Processing Unit | Universal compatibility |
| `mps` | Apple Metal Performance Shaders | macOS GPU acceleration |
| `cuda` | NVIDIA CUDA | High-performance GPU processing |

**Section sources**
- [diarizer.py:36-40](file://diarizer.py#L36-L40)
- [transcribe.py:195-196](file://transcribe.py#L195-L196)
- [stt_engine.py:27-39](file://stt_engine.py#L27-L39)

## Verification Steps

### Basic System Check

Verify all components are functioning correctly:

```bash
# Check Python version
python --version

# Verify uv installation
uv --version

# Test FFmpeg installation
ffmpeg -version
```

### Dependency Validation

Ensure all required packages are properly installed:

```bash
# Test Python imports
python -c "import torch; import torchaudio; import pyannote.audio; import funasr"
```

### Model Access Test

Verify HuggingFace model access:

```bash
# Test PyAnnote model loading
python -c "from pyannote.audio import Pipeline; p = Pipeline.from_pretrained('pyannote/speaker-diarization-community-1', token='YOUR_HF_TOKEN')"
```

**Section sources**
- [README.md:175-203](file://README.md#L175-L203)
- [diarizer.py:43-46](file://diarizer.py#L43-L46)

## Common Issues & Troubleshooting

### torchcodec Version Compatibility

**Issue**: `NameError: name 'AudioDecoder' is not defined`

**Cause**: Incompatible torchcodec and torch versions

**Solution**: Ensure torchcodec >= 0.12 is installed:

```bash
# Check current versions
pip show torch torchcodec

# Upgrade if necessary
pip install --upgrade torch torchcodec
```

**Reference**: The project specifies `torchcodec>=0.12` in dependencies.

### PyAnnote Model Access Permissions

**Issue**: Authentication errors when loading PyAnnote models

**Cause**: Missing or invalid HuggingFace token

**Solution**: 
1. Agree to terms on [HuggingFace](https://huggingface.co/pyannote/speaker-diarization-community-1)
2. Add token to `.env` file
3. Restart the application

**Section sources**
- [README.md:177-186](file://README.md#L177-L186)
- [diarizer.py:36-40](file://diarizer.py#L36-L40)

### FFmpeg Version Requirements

**Issue**: Audio conversion failures or poor quality output

**Cause**: Outdated FFmpeg version

**Solution**: 
- Ensure FFmpeg 4-8 is installed
- Verify installation: `ffmpeg -version`

**Section sources**
- [README.md:187-203](file://README.md#L187-L203)

### Memory and Performance Issues

**Symptoms**: Slow processing, memory errors, or crashes

**Solutions**:
- Reduce `--max-workers` parameter
- Use CPU instead of GPU for smaller systems
- Ensure adequate RAM (minimum 8GB recommended)

### Model Download Problems

**Issue**: Failed model downloads during first run

**Solutions**:
- Check internet connectivity
- Verify HuggingFace token validity
- Clear model cache and retry
- Use local model directory with `--model_dir`

## First-Time Usage Verification

### Test Command

Run a quick test to verify everything works:

```bash
# Basic transcription test
uv run transcribe.py -i audio/test.wav --device cpu --model_dir iic/SenseVoiceSmall
```

### Expected Output

After successful execution, you should see:
- Audio conversion progress
- Speaker diarization results
- Transcription completion
- Output files in the `output/` directory

### Output Directory Structure

```
audio/
├── test.wav              # Original audio
└── output/
    ├── test.srt          # SubRip subtitles
    ├── test.vtt          # Web Video Text Tracks
    ├── test.txt          # Plain text transcript
    └── test.json         # Structured JSON data
```

### HTTP Server Test

If using the server mode:

```bash
# Start server
uv run transcribe.py --server --port 8100 --device cpu

# Test with curl
curl -X POST http://localhost:8100/v1/audio/transcriptions \
  -F file=@audio/example.wav \
  -F model=sensevoice
```

**Section sources**
- [README.md:40-89](file://README.md#L40-L89)
- [output_formats.py:118-160](file://output_formats.py#L118-L160)

## Conclusion

Meeting Transcriber provides a robust solution for automated meeting transcription with speaker diarization. By following this installation guide, you should have a fully functional system capable of processing various audio formats and languages.

Key success factors:
- Proper Python 3.11+ environment setup
- Correct FFmpeg installation (versions 4-8)
- Valid HuggingFace token for model access
- Adequate system resources for optimal performance

For ongoing maintenance, regularly update dependencies using `uv sync` and monitor system resources during intensive transcription tasks.