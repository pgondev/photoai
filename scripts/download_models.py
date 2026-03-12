import os
from sentence_transformers import SentenceTransformer
from transformers import BlipProcessor, BlipForConditionalGeneration

def download_models():
    models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
    os.makedirs(models_dir, exist_ok=True)

    print(f"Downloading models to {models_dir}...")

    # 1. CLIP (via Sentence-Transformers)
    print("Downloading CLIP (clip-ViT-B-32)...")
    clip_path = os.path.join(models_dir, "clip-ViT-B-32")
    if not os.path.exists(clip_path):
        model = SentenceTransformer('clip-ViT-B-32')
        model.save(clip_path)
        print("CLIP downloaded.")
    else:
        print("CLIP already exists.")

    # 2. BLIP (via Transformers)
    print("Downloading BLIP (Salesforce/blip-image-captioning-base)...")
    blip_path = os.path.join(models_dir, "blip-base")
    if not os.path.exists(blip_path):
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        
        processor.save_pretrained(blip_path)
        model.save_pretrained(blip_path)
        print("BLIP downloaded.")
    else:
        print("BLIP already exists.")

    print("All models downloaded successfully!")

if __name__ == "__main__":
    download_models()
