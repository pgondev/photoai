from PIL import Image
import pillow_heif
import os
import sys

print(f"Python Version: {sys.version}")
print(f"Pillow Heif Version: {pillow_heif.__version__}")

# Register HEIF opener
pillow_heif.register_heif_opener()
print("HEIF Opener Registered.")

# Specific file from user report
img_path = r"C:\Users\parag\Pictures\Camera Roll\Riya\2023-12-20 - 2023-12-20\2023-12-20 052.HEIC"

if os.path.exists(img_path):
    print(f"File exists: {img_path}")
    print(f"Size: {os.path.getsize(img_path)} bytes")
    try:
        img = Image.open(img_path)
        print(f"Success! Image format: {img.format}, Mode: {img.mode}, Size: {img.size}")
        img.load()
        print("Image loaded into memory successfully.")
    except Exception as e:
        print(f"FAILED to open image: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"File NOT found: {img_path}")
