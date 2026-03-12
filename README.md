# PhotoAI Pro

AI-powered desktop app to find duplicate photos, organize your photo library, and classify images by type (memes, screenshots, documents, forwards, PII).

## Features

- **Duplicate detection** — perceptual hash (pHash + colorHash) with fuzzy matching
- **AI categorization** — CLIP + BLIP classify photos into Images, Memes, Screenshots, Forwards, Documents, Personal (PII), Videos, Audio, Documents
- **Photo organization** — moves files into dated folder structure (`Year/Month`)
- **Teach mode** — correct a misclassified image and the app learns from it (few-shot)
- **EXIF tag writing** — AI-generated tags embedded into JPEG metadata
- **HEIC support** — reads Apple HEIC/HEIF photos

## Requirements

- Python 3.9+
- Dependencies listed in `requirements.txt`
- Optional: NVIDIA GPU (CUDA) for faster AI inference

## Installation

```bash
pip install -r requirements.txt
```

> **Note:** `piexif` is also required for EXIF tag writing:
> ```bash
> pip install piexif
> ```

## Running

```bash
python gui_flet.py
```

## First-time model download

On first launch the app downloads two AI models (~1–2 GB total) and caches them in `~/.photoai/models/`:

- `clip-ViT-B-32` — image similarity and classification
- `Salesforce/blip-image-captioning-base` — image captioning / tagging

Subsequent launches use the cached models and work offline.

## Building a standalone .exe

```bash
# Standard build
python build.py

# Beta build
python build.py --beta

# Lite build (downloads models on first run, smaller .exe)
python build.py --lite
```

## Settings & data

All user settings and history are stored in `~/.photoai/`:

| File | Purpose |
|---|---|
| `settings.json` | Source/destination folders, theme |
| `history.json` | Scan and organize history |
| `logs/` | Per-operation log files |
| `models/` | Cached AI model weights |
| `reference_embeddings.json` | Teach-mode learned examples |

## Known limitations

- Duplicate detection works on images only; videos/audio/documents are listed but not deduplicated
- EXIF tag writing is JPEG-only
- Orientation fix is JPEG/PNG/WebP only
