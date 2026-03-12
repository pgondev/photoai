from PIL import Image
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    print("SUCCESS: pillow_heif registered.")
except ImportError:
    print("FAILURE: pillow_heif not installed.")

import os
# Create a dummy image to verify PIL generally
img = Image.new('RGB', (100, 100), color = 'red')
print("SUCCESS: PIL is working.")

# Check supported formats
from PIL import features
print(f"PIL Version: {Image.__version__}")

# Check if HEIC ID is in registered extensions
Image.init()
if '.heic' in Image.EXTENSION:
    print("SUCCESS: .heic extension is recognized by PIL.")
else:
    print("FAILURE: .heic extension NOT recognized by PIL.")
    print("Registered extensions:", Image.EXTENSION.keys())
