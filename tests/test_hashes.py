
import os
from PIL import Image
import imagehash

def test_hashes():
    # Create Red and Green images
    red = Image.new('RGB', (100, 100), (255, 0, 0))
    green = Image.new('RGB', (100, 100), (0, 255, 0))
    
    # Calculate ColorHash
    # analyzer uses default: imagehash.colorhash(img)
    h_red = imagehash.colorhash(red)
    h_green = imagehash.colorhash(green)
    
    print(f"Red Hash: {h_red}")
    print(f"Green Hash: {h_green}")
    print(f"Distance: {h_red - h_green}")
    
    # Calculate pHash
    p_red = imagehash.phash(red)
    p_green = imagehash.phash(green)
    print(f"Red pHash: {p_red}")
    print(f"Green pHash: {p_green}") 
    print(f"pHash Distance: {p_red - p_green}")

if __name__ == "__main__":
    test_hashes()
