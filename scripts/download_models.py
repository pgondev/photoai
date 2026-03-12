"""
Download AI models for a specific tier to ~/.photoai/models/

Usage:
    python scripts/download_models.py                # downloads default (smart) tier
    python scripts/download_models.py --tier fast
    python scripts/download_models.py --tier smart
    python scripts/download_models.py --tier modern
    python scripts/download_models.py --tier all     # downloads all tiers

Also callable from code:
    from scripts.download_models import download_tier
    download_tier("smart", progress_cb=lambda msg: print(msg))
"""

import os
import sys

# Allow running directly or as a module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_config import MODEL_TIERS, DEFAULT_TIER, format_size


MODELS_DIR = os.path.join(os.path.expanduser("~"), ".photoai", "models")


def _is_cached(dir_name: str) -> bool:
    p = os.path.join(MODELS_DIR, dir_name)
    return os.path.exists(p) and any(os.scandir(p))


def download_tier(tier: str, progress_cb=None) -> bool:
    """
    Download the two models for the given tier into MODELS_DIR.
    progress_cb(message: str) is called with status updates if provided.
    Returns True on success, False on error.
    """
    def log(msg):
        if progress_cb:
            progress_cb(msg)
        else:
            print(msg)

    if tier not in MODEL_TIERS:
        log(f"Unknown tier: {tier}. Choose from: {list(MODEL_TIERS)}")
        return False

    cfg = MODEL_TIERS[tier]
    os.makedirs(MODELS_DIR, exist_ok=True)

    success = True

    # --- 1. CLIP ---
    clip_path = os.path.join(MODELS_DIR, cfg["clip_dir"])
    if _is_cached(cfg["clip_dir"]):
        log(f"CLIP already cached: {cfg['clip_dir']}")
    else:
        size_str = format_size(cfg["clip_size_mb"])
        log(f"Downloading CLIP ({cfg['clip_id']})  {size_str}...")
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(cfg["clip_id"])
            model.save(clip_path)
            log(f"CLIP saved to {clip_path}")
        except Exception as e:
            log(f"ERROR downloading CLIP: {e}")
            success = False

    # --- 2. Caption model (BLIP or Florence-2) ---
    blip_path = os.path.join(MODELS_DIR, cfg["blip_dir"])
    if _is_cached(cfg["blip_dir"]):
        log(f"Caption model already cached: {cfg['blip_dir']}")
    else:
        size_str = format_size(cfg["blip_size_mb"])
        log(f"Downloading caption model ({cfg['blip_id']})  {size_str}...")
        try:
            if cfg["blip_type"] == "florence2":
                from transformers import AutoProcessor, AutoModelForCausalLM
                proc = AutoProcessor.from_pretrained(cfg["blip_id"], trust_remote_code=True)
                mdl = AutoModelForCausalLM.from_pretrained(cfg["blip_id"], trust_remote_code=True)
                proc.save_pretrained(blip_path)
                mdl.save_pretrained(blip_path)
            else:
                from transformers import BlipProcessor, BlipForConditionalGeneration
                proc = BlipProcessor.from_pretrained(cfg["blip_id"])
                mdl = BlipForConditionalGeneration.from_pretrained(cfg["blip_id"])
                proc.save_pretrained(blip_path)
                mdl.save_pretrained(blip_path)
            log(f"Caption model saved to {blip_path}")
        except Exception as e:
            log(f"ERROR downloading caption model: {e}")
            success = False

    if success:
        log(f"Tier '{tier}' ready.")
    return success


def download_all(progress_cb=None):
    results = {}
    for tier in MODEL_TIERS:
        results[tier] = download_tier(tier, progress_cb=progress_cb)
    return results


def get_cache_status() -> dict:
    """Returns {tier: {clip: bool, blip: bool}} indicating what's already cached."""
    status = {}
    for tier, cfg in MODEL_TIERS.items():
        status[tier] = {
            "clip": _is_cached(cfg["clip_dir"]),
            "blip": _is_cached(cfg["blip_dir"]),
        }
    return status


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", default=DEFAULT_TIER,
                        choices=list(MODEL_TIERS) + ["all"],
                        help="Model tier to download")
    args = parser.parse_args()

    print(f"Model cache directory: {MODELS_DIR}\n")

    if args.tier == "all":
        download_all()
    else:
        download_tier(args.tier)
