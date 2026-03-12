# model_config.py
# Single source of truth for AI model tier definitions.
# Imported by analyzer.py, download_models.py, and gui_flet.py.

DEFAULT_TIER = "smart"

MODEL_TIERS = {
    "fast": {
        "display_name": "Fast",
        "tagline": "Lightweight, works on low-end hardware",
        "icon": "⚡",
        "clip_id": "clip-ViT-B-32",
        "clip_dir": "clip-ViT-B-32",
        "blip_id": "Salesforce/blip-image-captioning-base",
        "blip_dir": "blip-base",
        "blip_type": "blip",
        # Technical details (shown in advanced view)
        "clip_params": "151M params · 512-dim · 224px",
        "blip_params": "385M params · 384px",
        "clip_size_mb": 582,
        "blip_size_mb": 856,
    },
    "smart": {
        "display_name": "Smart",
        "tagline": "Best accuracy, recommended for most users",
        "icon": "🧠",
        "clip_id": "clip-ViT-L-14",
        "clip_dir": "clip-ViT-L-14",
        "blip_id": "Salesforce/blip-image-captioning-large",
        "blip_dir": "blip-large",
        "blip_type": "blip",
        "clip_params": "427M params · 768-dim · 224px",
        "blip_params": "447M params · 384px",
        "clip_size_mb": 1100,
        "blip_size_mb": 1400,
    },
    "modern": {
        "display_name": "Modern",
        "tagline": "Florence-2 captioning — compact and new",
        "icon": "🔬",
        "clip_id": "clip-ViT-L-14",
        "clip_dir": "clip-ViT-L-14",           # shared with smart — downloads once
        "blip_id": "microsoft/Florence-2-base",
        "blip_dir": "florence-2-base",
        "blip_type": "florence2",
        "clip_params": "427M params · 768-dim · 224px",
        "blip_params": "270M params",
        "clip_size_mb": 1100,
        "blip_size_mb": 270,
    },
}

# Per-tier default detection thresholds.
# Keys match the threshold keys used throughout analyzer.py.
# Users can override these in settings.json under "thresholds".
TIER_THRESHOLDS = {
    "fast": {
        "doc":        0.23,   # is_document_image positive margin
        "meme":       0.24,   # is_meme_or_screenshot
        "screenshot": 0.25,   # is_screenshot
        "pii":        0.23,   # is_pii_document
        "fewshot":    0.90,   # find_custom_category match confidence
    },
    "smart": {
        "doc":        0.21,
        "meme":       0.22,
        "screenshot": 0.23,
        "pii":        0.21,
        "fewshot":    0.88,
    },
    "modern": {
        "doc":        0.21,
        "meme":       0.22,
        "screenshot": 0.23,
        "pii":        0.21,
        "fewshot":    0.88,
    },
}

# Human-readable threshold labels for the advanced settings UI
THRESHOLD_LABELS = {
    "doc":        "Document detection",
    "meme":       "Meme / forward detection",
    "screenshot": "Screenshot detection",
    "pii":        "PII document detection",
    "fewshot":    "Few-shot match confidence",
}

# Slider ranges for each threshold in the advanced UI
THRESHOLD_RANGES = {
    "doc":        (0.10, 0.50),
    "meme":       (0.10, 0.50),
    "screenshot": (0.10, 0.50),
    "pii":        (0.10, 0.50),
    "fewshot":    (0.70, 0.99),
}


def get_total_size_mb(tier: str) -> int:
    """Returns combined CLIP + caption model download size in MB."""
    t = MODEL_TIERS[tier]
    # If sharing CLIP with smart tier, don't double-count
    if tier == "modern":
        # CLIP shared with smart — only new download is Florence-2
        return t["blip_size_mb"]
    return t["clip_size_mb"] + t["blip_size_mb"]


def format_size(mb: int) -> str:
    if mb >= 1000:
        return f"~{mb / 1000:.1f} GB"
    return f"~{mb} MB"
