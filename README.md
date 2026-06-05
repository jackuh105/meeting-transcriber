# Meeting Transcriber

一條指令完成會議轉錄：自動說話者分離 + SenseVoice 語音識別，輸出 SRT / VTT / TXT / JSON 字幕。

## 功能

- **說話者分離** — 使用 PyAnnote.audio 自動偵測並區分不同說話者
- **語音識別** — 使用 SenseVoice (FunASR) 進行高精度轉錄，支援中文、英文、廣東話、日文、韓文
- **多格式輸出** — SRT、VTT、純文字（含時間戳和說話者標籤）、結構化 JSON
- **In-process 模式** — 預設在同一個 process 內直接調用模型，無需啟動 HTTP server
- **HTTP Server 模式** — 可選啟動 OpenAI Whisper API 兼容的 STT server，供外部工具使用
- **音訊格式支援** — 自動轉換 MP4、MP3、M4A 等格式為 WAV

## 前置需求

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/) 4–8（macOS: `brew install ffmpeg`）
- [uv](https://docs.astral.sh/uv/) 套件管理器
- HuggingFace 帳號（用於 PyAnnote 模型下載）
- SenseVoice 模型檔案（可指定本地路徑或讓 FunASR 自動下載）

## 安裝

```bash
# 1. 安裝 Python 依賴
uv sync

# 2. 設定環境變數
cp .env.example .env
```

編輯 `.env`，填入你的 HuggingFace token：

```env
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx
```

> PyAnnote 模型需要在 [HuggingFace](https://huggingface.co/pyannote/speaker-diarization-community-1) 上同意使用條款。

## 使用方式

### 會議轉錄（預設模式）

```bash
# 基本用法
uv run transcribe.py -i audio/meeting.mp4 --device mps --model_dir /path/to/sensevoice_model

# 指定語言和輸出格式
uv run transcribe.py -i audio/meeting.mp4 \
  --device mps \
  --language yue \
  --format srt,json \
  --model_dir /path/to/sensevoice_model

# 自訂輸出目錄
uv run transcribe.py -i audio/meeting.mp4 \
  --device mps \
  --model_dir /path/to/sensevoice_model \
  -o results/
```

輸出檔案會預設存放在 `<音訊所在目錄>/output/` 子目錄中：

```
audio/
├── meeting.mp4              # 原始音訊
└── output/
    ├── meeting.srt          # SRT 字幕
    ├── meeting.vtt          # WebVTT 字幕
    ├── meeting.txt          # 純文字（含時間戳）
    └── meeting.json         # 結構化 JSON
```

### HTTP Server 模式

啟動 OpenAI Whisper API 兼容的 STT server：

```bash
uv run transcribe.py --server --port 8100 --device mps --model_dir /path/to/sensevoice_model
```

啟動後可用 curl 或任何 OpenAI 客戶端呼叫：

```bash
curl -X POST http://localhost:8100/v1/audio/transcriptions \
  -F file=@audio/example.wav \
  -F model=sensevoice
```

## CLI 參數

### 通用參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `--server` | flag | — | 啟動 HTTP server 模式（預設為轉錄模式） |
| `--device` | str | `cpu` | 運算裝置：`cpu`、`mps`、`cuda` |
| `--model_dir` | str | `iic/SenseVoiceSmall` | SenseVoice 模型目錄路徑 |

### 轉錄模式參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `-i, --input` | str | — | 輸入音訊/影片檔案路徑（必填） |
| `--language` | str | `auto` | 語言：`auto`、`zh`、`en`、`yue`、`ja`、`ko` |
| `--format` | str | `srt,vtt,txt,json` | 輸出格式（逗號分隔） |
| `-o, --output` | str | `<input_dir>/output/` | 自訂輸出目錄 |
| `--max-workers` | int | `1` | 最大併發轉錄數 |
| `--padding` | float | `0.3` | 音訊分段前後填充秒數 |
| `--max-gap` | float | `2.0` | 合併同一說話者片段的最大間隔秒數 |

### Server 模式參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `--host` | str | `0.0.0.0` | Server 監聽地址 |
| `--port` | int | `8000` | Server 端口 |
| `--vad_model` | str | `fsmn-vad` | VAD 模型名稱 |
| `--use_itn` | bool | `True` | 使用反文本正則化 |
| `--merge_vad` | bool | `True` | 合併 VAD 分段 |
| `--merge_length_s` | int | `15` | VAD 合併最大長度（秒） |

## 支援語言

| 語言 | 代碼 |
|------|------|
| 自動偵測 | `auto` |
| 中文 | `zh` |
| 英文 | `en` |
| 廣東話 | `yue` |
| 日文 | `ja` |
| 韓文 | `ko` |

## 專案結構

```
meeting-transcriber/
├── transcribe.py      # 統一 CLI 入口
├── stt_engine.py      # In-process SenseVoice STT 引擎
├── server.py          # FastAPI HTTP server（--server 模式）
├── diarizer.py        # 說話者分離（PyAnnote wrapper）
├── audio_utils.py     # 音訊轉換、分段提取
├── output_formats.py  # SRT / VTT / TXT / JSON 輸出生成器
├── model.py           # SenseVoice 模型程式碼
├── utils/
│   └── ctc_alignment.py
├── run.sh             # 便捷啟動腳本
└── pyproject.toml
```

## 工作流程

```
輸入音訊/影片
    │
    ▼
1. 音訊格式轉換（ffmpeg → 16kHz mono WAV）
    │
    ▼
2. 說話者分離（PyAnnote.audio）
    │  偵測不同說話者並切分時段
    │
    ▼
3. 時段合併
    │  合併同一說話者相鄰時段（間隔 ≤ 2 秒）
    │
    ▼
4. 逐段轉錄（SenseVoice in-process）
    │  提取每個時段的音訊 → 模型推理
    │
    ▼
5. 輸出 SRT / VTT / TXT / JSON
```

## 疑難排解

### torchcodec 版本不相容

如果遇到 `NameError: name 'AudioDecoder' is not defined`，表示 torchcodec 版本與 torch 不相容。請確保 `pyproject.toml` 中使用 `torchcodec>=0.12`。

參閱 [torchcodec 版本兼容表](https://github.com/pytorch/torchcodec?tab=readme-ov-file#installing-torchcodec)。

### PyAnnote 模型存取

確保已在 HuggingFace 上同意 [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) 的使用條款，並且 `.env` 中設定了有效的 `HF_TOKEN`。

### FFmpeg 版本

torchcodec >= 0.12 支援 FFmpeg 4–8。確認系統已安裝 FFmpeg：

```bash
ffmpeg -version
```

如未安裝：

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg
```

## 致謝

- [FunASR](https://github.com/alibaba-damo-academy/FunASR) / [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) — 語音識別引擎
- [PyAnnote.audio](https://github.com/pyannote/pyannote-audio) — 說話者分離
- [OpenAI Whisper API](https://platform.openai.com/docs/guides/speech-to-text) — API 格式參考
