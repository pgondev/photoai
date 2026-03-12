# PhotoAI Pro - Flexible Build Script
# Supports version tags: Beta, Alpha, Dev, RC, etc.

"""
Usage:
    python build.py              # Standard build: "PhotoAI Pro"
    python build.py --beta       # Beta build: "PhotoAI Pro (Beta)"
    python build.py --alpha      # Alpha build: "PhotoAI Pro (Alpha)"
    python build.py --dev        # Dev build: "PhotoAI Pro (Dev)"
    python build.py --lite       # Lite build: "PhotoAI Pro Lite"
    python build.py --lite --beta  # Lite Beta: "PhotoAI Pro Lite (Beta)"
"""

import PyInstaller.__main__
import os
import sys

# Always run from project root so PyInstaller finds gui_flet.py and assets
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Parse arguments
args = sys.argv[1:]
is_lite = '--lite' in args
is_beta = '--beta' in args
is_alpha = '--alpha' in args
is_dev = '--dev' in args
is_rc = '--rc' in args

# Build app name
app_name = "PhotoAI Pro"

if is_lite:
    app_name += " Lite"

# Add version tag
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

# Add models for full version (not lite)
if not is_lite:
    build_args.insert(-1, '--add-data=models;models')

# Run PyInstaller
print(f"\nBuilding: {app_name}")
print(f"   Type: {'Lite' if is_lite else 'Full'} Version")
print(f"   Size: {'~50-100 MB' if is_lite else '~2-3 GB'}")
print()

PyInstaller.__main__.run(build_args)

print(f"\nBuild complete!")
print(f"Your .exe: dist/{app_name}.exe")

if is_lite:
    print("\nLITE VERSION:")
    print("   - First launch requires internet")
    print("   - Models download automatically (~1-2 GB)")
    print("   - Models cached in user's home directory")
else:
    print("\nFULL VERSION:")
    print("   - Works completely offline")
    print("   - All models bundled")

if is_beta or is_alpha or is_dev:
    print(f"\nVERSION TAG: {app_name.split('(')[1].strip(')')}")
    print("   - Clearly marked as pre-release")
    print("   - Window title will show version tag")
