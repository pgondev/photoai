from PIL import Image
import os

def convert_png_to_ico(png_path, ico_path):
    if os.path.exists(png_path):
        img = Image.open(png_path)
        # Use sizes that Windows likes
        img.save(ico_path, format='ICO', sizes=[(16,16), (24,24), (32,32), (48,48), (64,64), (128,128), (256,256)])
        print(f"Created {ico_path}")

if __name__ == "__main__":
    convert_png_to_ico("assets/logo_ai.png", "assets/logo_ai.ico")
    convert_png_to_ico("assets/logo_ai_red.png", "assets/logo_ai_red.ico")
