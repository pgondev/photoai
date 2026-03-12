# PhotoAI Pro - Flexible Build Script
# Supports version tags: Beta, Alpha, Dev, RC, etc.

"""
Usage:
    python build.py                      # Full build, Smart tier bundled (~2.5 GB)
    python build.py --bundle-fast        # Full build, Fast tier bundled (~1.5 GB)
    python build.py --beta               # Beta build: "PhotoAI Pro (Beta)"
    python build.py --alpha              # Alpha build: "PhotoAI Pro (Alpha)"
    python build.py --dev                # Dev build: "PhotoAI Pro (Dev)"
    python build.py --lite               # Lite build: no models bundled (~100 MB)
    python build.py --lite --beta        # Lite Beta: "PhotoAI Pro Lite (Beta)"

Bundled tier controls which models are included in the full .exe:
  Default (Smart): clip-ViT-L-14 + blip-large  — ~2.5 GB, best offline accuracy
  --bundle-fast  : clip-ViT-B-32 + blip-base   — ~1.5 GB, smaller exe
  Lite           : no models bundled; all tiers download on first use
"""

import PyInstaller.__main__
import os
import sys

# Always run from project root so PyInstaller finds gui_flet.py and assets
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

from model_config import MODEL_TIERS

# Parse arguments
args = sys.argv[1:]
is_lite        = '--lite'        in args
is_beta        = '--beta'        in args
is_alpha       = '--alpha'       in args
is_dev         = '--dev'         in args
is_rc          = '--rc'          in args
is_bundle_fast = '--bundle-fast' in args

# Determine which tier to bundle (only relevant for full build)
bundle_tier = "fast" if is_bundle_fast else "smart"
tier_cfg = MODEL_TIERS[bundle_tier]

# Build app name
app_name = "PhotoAI Pro"
if is_lite:
    app_name += " Lite"
if is_beta:
    app_name += " (Beta)"
elif is_alpha:
    app_name += " (Alpha)"
elif is_dev:
    app_name += " (Dev)"
elif is_rc:
    app_name += " (RC)"

# Ensure assets directory exists
os.makedirs('assets', exist_ok=True)

# Build PyInstaller arguments
build_args = [
    'gui_flet.py',
    f'--name={app_name}',
    '--onefile',
    '--windowed',
    '--icon=assets/logo_ai.ico',
    '--splash=assets/logo_ai.png',
    '--add-data=assets;assets',
    '--hidden-import=PIL._tkinter_finder',
    '--hidden-import=transformers',
    '--hidden-import=sentence_transformers',
    '--clean',
]

# Full build: bundle the selected tier's models
if not is_lite:
    clip_dir = os.path.join('models', tier_cfg['clip_dir'])
    blip_dir = os.path.join('models', tier_cfg['blip_dir'])

    if not os.path.exists(clip_dir):
        print(f"\nWARNING: Bundled CLIP not found at '{clip_dir}'")
        print(f"  Run: python scripts/download_models.py --tier {bundle_tier}")
        print(f"  Models will be downloaded at runtime instead.\n")
    else:
        build_args.insert(-1, f'--add-data={clip_dir};models/{tier_cfg["clip_dir"]}')

    if not os.path.exists(blip_dir):
        print(f"\nWARNING: Bundled caption model not found at '{blip_dir}'")
        print(f"  Run: python scripts/download_models.py --tier {bundle_tier}")
        print(f"  Models will be downloaded at runtime instead.\n")
    else:
        build_args.insert(-1, f'--add-data={blip_dir};models/{tier_cfg["blip_dir"]}')

# Run PyInstaller
bundled_size = "~2.5 GB" if bundle_tier == "smart" else "~1.5 GB"
print(f"\nBuilding: {app_name}")
print(f"   Type: {'Lite (no bundled models)' if is_lite else 'Full'}")
if not is_lite:
    print(f"   Bundled tier: {bundle_tier.capitalize()} ({tier_cfg['clip_id']} + {tier_cfg['blip_id']})")
    print(f"   Approx size: {bundled_size}")
print()

PyInstaller.__main__.run(build_args)

print(f"\nBuild complete!")
print(f"Your .exe: dist/{app_name}.exe")

if is_lite:
    print("\nLITE VERSION:")
    print("   - Models download on first use per selected tier")
    print("   - Cached in ~/.photoai/models/")
    print("   - Users can switch tiers in Settings")
else:
    print(f"\nFULL VERSION ({bundle_tier.upper()} tier bundled):")
    print("   - Default tier works completely offline")
    print("   - Other tiers download on demand to ~/.photoai/models/")
    print("   - Users can switch tiers in Settings")

if is_beta or is_alpha or is_dev:
    print(f"\nVERSION TAG: {app_name.split('(')[1].strip(')')}")
    print("   - Clearly marked as pre-release")
    print("   - Window title will show version tag")
