"""
Diagnostic script to test hash distances between uploaded images.
This will help understand why duplicate detection is failing.
"""

import sys
sys.path.append('.')

from analyzer import ImageAnalyzer
import imagehash

# Initialize analyzer
analyzer = ImageAnalyzer()

# Paths to the uploaded images
img1 = r"C:/Users/parag/.gemini/antigravity/brain/42f22cbf-2805-4b3f-be53-16d722965072/uploaded_image_0_1766160329163.jpg"
img2 = r"C:/Users/parag/.gemini/antigravity/brain/42f22cbf-2805-4b3f-be53-16d722965072/uploaded_image_1_1766160329163.jpg"
img3 = r"C:/Users/parag/.gemini/antigravity/brain/42f22cbf-2805-4b3f-be53-16d722965072/uploaded_image_2_1766160329163.jpg"
img4 = r"C:/Users/parag/.gemini/antigravity/brain/42f22cbf-2805-4b3f-be53-16d722965072/uploaded_image_3_1766160329163.jpg"

images = [img1, img2, img3, img4]

print("="*60)
print("HASH CALCULATION FOR UPLOADED IMAGES")
print("="*60)

# Calculate hashes for all images
hashes = {}
for img_path in images:
    phash = analyzer.calculate_phash(img_path)
    chash = analyzer.calculate_colorhash(img_path)
    hashes[img_path] = {'phash': phash, 'chash': chash}
    print(f"\n{img_path.split('/')[-1]}:")
    print(f"  pHash: {phash}")
    print(f"  cHash: {chash}")

print("\n" + "="*60)
print("PAIRWISE HASH DISTANCES")
print("="*60)

# Compare all pairs
for i, img1_path in enumerate(images):
    for j, img2_path in enumerate(images):
        if i >= j:
            continue
        
        h1 = imagehash.hex_to_hash(hashes[img1_path]['phash'])
        h2 = imagehash.hex_to_hash(hashes[img2_path]['phash'])
        c1 = imagehash.hex_to_hash(hashes[img1_path]['chash'])
        c2 = imagehash.hex_to_hash(hashes[img2_path]['chash'])
        
        phash_dist = h1 - h2
        chash_dist = c1 - c2
        
        img1_name = img1_path.split('/')[-1]
        img2_name = img2_path.split('/')[-1]
        
        print(f"\n{img1_name} vs {img2_name}:")
        print(f"  pHash distance: {phash_dist}")
        print(f"  cHash distance: {chash_dist}")
        
        # Check if they would be detected as duplicates
        if phash_dist <= 6 and chash_dist <= 4:
            print(f"  ✓ WOULD BE DETECTED AS DUPLICATES")
        else:
            print(f"  ✗ NOT DETECTED (threshold: pHash≤6, cHash≤4)")

print("\n" + "="*60)
print("EXPECTED DUPLICATES:")
print("  - Image 0 and Image 2 (same page)")
print("  - Image 1 and Image 3 (same page)")
print("="*60)
