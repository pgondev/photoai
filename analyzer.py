import cv2
import numpy as np
import imagehash
from PIL import Image, ImageOps
import sys
import os
import json
import torch
import piexif
from datetime import datetime
from PIL.ExifTags import TAGS
from transformers import BlipProcessor, BlipForConditionalGeneration, AutoProcessor, AutoModelForCausalLM
from sentence_transformers import SentenceTransformer, util
from functools import lru_cache
import warnings
from model_config import MODEL_TIERS, TIER_THRESHOLDS, DEFAULT_TIER

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# Suppress annoying "Corrupt EXIF data" warnings from PIL/TiffImagePlugin
warnings.filterwarnings("ignore", category=UserWarning, module="PIL.TiffImagePlugin")

class ImageAnalyzer:
    def __init__(self, tier: str = DEFAULT_TIER, threshold_overrides: dict = None):
        """
        tier: "fast" | "smart" | "modern"  (from model_config.MODEL_TIERS)
        threshold_overrides: dict of {key: float} from settings.json, overrides TIER_THRESHOLDS defaults
        """
        print(f"Initializing AI models (tier: {tier})... This might take a moment.")

        self.torch = torch
        self.util = util
        self.tier = tier

        cfg = MODEL_TIERS[tier]
        self.blip_type = cfg["blip_type"]

        # Merge per-tier default thresholds with any user overrides
        base = dict(TIER_THRESHOLDS[tier])
        if threshold_overrides:
            base.update(threshold_overrides)
        self.thr = base  # e.g. self.thr["doc"], self.thr["fewshot"]

        # --- Model path resolution ---
        # Priority: 1) bundled (_MEIPASS/models/)  2) user cache (~/.photoai/models/)  3) Hub download
        user_cache = os.path.join(os.path.expanduser("~"), ".photoai", "models")
        os.makedirs(user_cache, exist_ok=True)

        bundled_dir = None
        if getattr(sys, 'frozen', False):
            candidate = os.path.join(sys._MEIPASS, "models")
            if os.path.exists(candidate):
                bundled_dir = candidate

        def resolve_model_dir(dir_name):
            """Return first existing path for a model directory, else user cache path (for download)."""
            if bundled_dir:
                p = os.path.join(bundled_dir, dir_name)
                if os.path.exists(p):
                    return p, True   # (path, is_local)
            p = os.path.join(user_cache, dir_name)
            return p, os.path.exists(p)

        # Move to GPU if available
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # 1. Load CLIP
        clip_path, clip_exists = resolve_model_dir(cfg["clip_dir"])
        if clip_exists:
            print(f"Loading CLIP from: {clip_path}")
            self.similarity_model = SentenceTransformer(clip_path, device=self.device)
        else:
            print(f"Downloading CLIP ({cfg['clip_id']}) to {clip_path}...")
            self.similarity_model = SentenceTransformer(cfg["clip_id"], device=self.device, cache_folder=user_cache)

        # --- FEW-SHOT LEARNING STORAGE ---
        self.ref_file = os.path.join(os.path.expanduser("~"), ".photoai", "reference_embeddings.json")
        self.references = self.load_references()

        # 2. Load caption model (BLIP or Florence-2)
        caption_path, caption_exists = resolve_model_dir(cfg["blip_dir"])
        try:
            if self.blip_type == "florence2":
                self._load_florence2(caption_path, caption_exists, cfg)
            else:
                self._load_blip(caption_path, caption_exists, cfg)
        except Exception as e:
            print(f"Warning: GPU load failed, falling back to CPU. Error: {e}")
            self.device = "cpu"
            if self.blip_type == "florence2":
                self._load_florence2(caption_path, caption_exists, cfg)
            else:
                self._load_blip(caption_path, caption_exists, cfg, cpu_fallback=True)

        self._precalc_prompts()
        print(f"Models loaded on {self.device} (tier: {self.tier}).")

    def _load_blip(self, path, exists, cfg, cpu_fallback=False):
        if exists:
            print(f"Loading BLIP from: {path}")
            self.caption_processor = BlipProcessor.from_pretrained(path)
            self.caption_model = BlipForConditionalGeneration.from_pretrained(
                path, low_cpu_mem_usage=cpu_fallback
            ).to(self.device).to(torch.float32)
        else:
            print(f"Downloading BLIP ({cfg['blip_id']})...")
            user_cache = os.path.join(os.path.expanduser("~"), ".photoai", "models")
            self.caption_processor = BlipProcessor.from_pretrained(cfg["blip_id"], cache_dir=user_cache)
            self.caption_model = BlipForConditionalGeneration.from_pretrained(
                cfg["blip_id"], cache_dir=user_cache, low_cpu_mem_usage=cpu_fallback
            ).to(self.device).to(torch.float32)

    def _load_florence2(self, path, exists, cfg):
        if exists:
            print(f"Loading Florence-2 from: {path}")
            self.caption_processor = AutoProcessor.from_pretrained(path, trust_remote_code=True)
            self.caption_model = AutoModelForCausalLM.from_pretrained(
                path, trust_remote_code=True
            ).to(self.device).to(torch.float32)
        else:
            print(f"Downloading Florence-2 ({cfg['blip_id']})...")
            user_cache = os.path.join(os.path.expanduser("~"), ".photoai", "models")
            self.caption_processor = AutoProcessor.from_pretrained(
                cfg["blip_id"], cache_dir=user_cache, trust_remote_code=True
            )
            self.caption_model = AutoModelForCausalLM.from_pretrained(
                cfg["blip_id"], cache_dir=user_cache, trust_remote_code=True
            ).to(self.device).to(torch.float32)

    def _precalc_prompts(self):
        """Pre-encode meme/screenshot detection prompts for fast reuse. Called from __init__."""
        self._prompts_meme = [
            "a meme", "a screenshot", "incorrectly cropped image",
            "a twitter post", "a whatsapp chat", "text overlay on image",
            "a funny picture with text"
        ]
        self._prompts_meme_neg = [
            "a professional photo", "a landscape", "a portrait",
            "a clear document", "natural scenery", "a family photo",
            "a barcode", "an id card", "a physical object"
        ]
        self._emb_meme_pos = self.similarity_model.encode(self._prompts_meme, convert_to_tensor=True)
        self._emb_meme_neg = self.similarity_model.encode(self._prompts_meme_neg, convert_to_tensor=True)

    @lru_cache(maxsize=32)
    def _get_image(self, img_path):
        """
        Cached image loading with robustness for corrupt/empty files.
        Automatically applies EXIF transposition.
        """
        try:
            # Check if file exists and has content
            if not os.path.exists(img_path) or os.path.getsize(img_path) == 0:
                return None

            # Ignore AppleDouble ._ files (metadata)
            if os.path.basename(img_path).startswith("._"):
                return None
                
            img = Image.open(img_path)
            img = ImageOps.exif_transpose(img)
            # Ensure image is in a mode that PIL/CV2 can handle
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            return img
        except Exception as e:
            if "cannot identify image file" in str(e):
                print(f"Skipping unrecognized file format: {os.path.basename(img_path)}")
            else:
                print(f"Skipping corrupt or unreadable image {os.path.basename(img_path)}: {e}")
            return None

    @lru_cache(maxsize=32)
    def _get_embedding_tensor(self, img_path):
        """Cached CLIP embedding to prevent re-encoding same image."""
        try:
            pil_img = self._get_image(img_path)
            if pil_img is None: return None
            return self.similarity_model.encode(pil_img, convert_to_tensor=True)
        except Exception as e:
            print(f"Error getting embedding for {img_path}: {e}")
            return None

    def load_references(self):
        """Loads user-corrected reference embeddings from JSON."""
        if not os.path.exists(self.ref_file):
            return {}
        try:
            with open(self.ref_file, 'r') as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f"Error loading references: {e}")
            return {}

    def find_custom_category(self, img_path):
        """
        Checks if img_path matches any user-taught examples with high confidence.
        Returns category string or None.
        """
        try:
            if not self.references:
                return None
            
            # Helper to check extension before opening (speed up)
            if not str(img_path).lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff')):
                 return None

            try:
                pil_img = Image.open(img_path)
            except Exception:
                 # Not a valid image
                 return None

            # Get tensor for optimized cosine calcs
            input_emb = self.similarity_model.encode(pil_img, convert_to_tensor=True)
            
            best_cat = None
            best_score = 0.0
            
            for category, embeddings in self.references.items():
                if not embeddings:
                    continue
                # Convert list of lists to tensor
                ref_embs = self.torch.tensor(embeddings).to(self.device)
                
                # Compare input against all refs in this category
                scores = self.util.cos_sim(input_emb, ref_embs)[0] 
                max_score = scores.max().item()
                
                # Check for high confidence match
                if max_score > best_score:
                    best_score = max_score
                    best_cat = category
            
            # Threshold: Must be very similar to a known example
            if best_score > self.thr["fewshot"]:
                print(f"Custom Match: {best_cat} ({best_score:.3f})")
                return best_cat
            
            return None
        except Exception as e:
            print(f"Error finding custom category: {e}")
            return None

    def calculate_phash(self, img_path):
        """
        Calculates rotation-invariant perceptual hash (pHash).
        Generates hashes for 8 orientations and returns the minimum.
        """
        try:
            img = self._get_image(img_path)
            if img is None: return None
            
            # Force to a fixed square shape (resize, not thumbnail) for canonical form
            img_small = img.resize((64, 64), Image.Resampling.LANCZOS).convert('L')
            
            # Calculate hash for 8 orientations (4 rotations * 2 flips) to be bulletproof
            hashes = []
            img_flipped = ImageOps.mirror(img_small)
            
            for base_img in [img_small, img_flipped]:
                for angle in [0, 90, 180, 270]:
                    rotated = base_img.rotate(angle)
                    # pHash is generally more robust to slight edits/noise than dHash
                    hash_val = str(imagehash.phash(rotated))
                    hashes.append(hash_val)
            
            return min(hashes)
        except Exception as e:
            print(f"Error calculating pHash: {e}")
            return None

    def calculate_colorhash(self, img_path):
        """
        Calculates color hash to distinguish solid colors that might share phash.
        """
        try:
            img = self._get_image(img_path)
            if img is None: return None
            img_small = img.resize((64, 64), Image.Resampling.LANCZOS)
            
            hashes = []
            for angle in [0, 90, 180, 270]:
                rotated = img_small.rotate(angle)
                hash_val = str(imagehash.colorhash(rotated))
                hashes.append(hash_val)
            return min(hashes)
        except Exception as e:
            print(f"Error calculating ColorHash: {e}")
            return None

    def analyze_quality(self, img_path):
        """
        Calculates quality metrics: Blur, Brightness, and Smile Score.
        Returns a dict.
        """
        scores = {"blur": 0.0, "brightness": 0.0, "smile": 0.0, "overall": 0.0}
        try:
            pil_img = self._get_image(img_path)
            if pil_img is None: return scores

            # OpenCV for Blur/Brightness (requires reading as cv2 image)
            # Convert PIL image to OpenCV format
            cv_img = np.array(pil_img)
            # If PIL image is RGB, OpenCV expects BGR
            if pil_img.mode == 'RGB':
                cv_img = cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR)
            
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            
            # 1. Blur (Laplacian Variance) - Higher is sharper
            blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
            scores["blur"] = blur_score

            # 2. Brightness (Mean intensity)
            brightness = np.mean(gray)
            scores["brightness"] = brightness

            # 3. Smile/Aesthetics (CLIP)
            # We compare image against "a smiling face" vs "a face"
            # Or just use raw score of "good photo"
            # Simple prompt-based score
            prompts = ["a smiling face", "a blurry photo"]
            encoded_prompts = self.similarity_model.encode(prompts, convert_to_tensor=True)
            encoded_img = self.similarity_model.encode(pil_img, convert_to_tensor=True)
            
            # cosine similarity
            sims = self.util.cos_sim(encoded_img, encoded_prompts)
            smile_score = sims[0][0].item() # Score for "smiling face"
            
            scores["smile"] = smile_score * 100
            
            # Weighted overall score (Heuristic)
            # Normalized Blur (typical sharp > 100), Brightness (0-255), Smile (0-100)
            norm_blur = min(blur_score, 500) / 500.0 # Cap at 500
            norm_bright = min(brightness, 200) / 200.0 
            
            scores["overall"] = (norm_blur * 0.4) + (norm_bright * 0.2) + (smile_score * 0.4)
            
        except Exception as e:
            print(f"Error analyzing quality: {e}")
        
        return scores

    def calculate_similarity(self, img_path1, img_path2):
        """
        Returns a percentage of similarity between two images.
        """
        try:
            # We can cache embeddings for efficiency later, but for now calculate on fly
            img1 = Image.open(img_path1)
            img2 = Image.open(img_path2)
            
            # SentenceTransformer handles image encoding directly
            emb1 = self.similarity_model.encode(img1, convert_to_tensor=True)
            emb2 = self.similarity_model.encode(img2, convert_to_tensor=True)
            
            cosine_score = self.util.cos_sim(emb1, emb2)
            return cosine_score.item() * 100 # Return as percentage
        except Exception as e:
            print(f"Error calculating similarity: {e}")
            return 0.0

    def generate_tags(self, img_path):
        """
        Returns a list of keyword tags/descriptions for the image.
        Extracts meaningful keywords from the generated caption.
        Supports both BLIP and Florence-2 caption models.
        """
        try:
            image = self._get_image(img_path)
            if image is None: return []

            if self.blip_type == "florence2":
                inputs = self.caption_processor(
                    text="<DETAILED_CAPTION>", images=image, return_tensors="pt"
                ).to(self.device)
                out = self.caption_model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=64,
                )
                raw = self.caption_processor.batch_decode(out, skip_special_tokens=True)[0]
                # Florence-2 wraps output in task token — strip it
                caption = raw.replace("<DETAILED_CAPTION>", "").strip()
            else:
                inputs = self.caption_processor(image, return_tensors="pt").to(self.device)
                out = self.caption_model.generate(**inputs)
                caption = self.caption_processor.decode(out[0], skip_special_tokens=True)
            
            # Extract keywords from caption
            # Remove common articles and prepositions
            stop_words = {'a', 'an', 'the', 'in', 'on', 'at', 'of', 'with', 'and', 'or', 'is', 'are', 'was', 'were'}
            words = caption.lower().replace(',', '').replace('.', '').split()
            keywords = [w for w in words if w not in stop_words and len(w) > 2]
            
            # Return unique keywords (limit to 5 most relevant)
            unique_keywords = []
            for kw in keywords:
                if kw not in unique_keywords:
                    unique_keywords.append(kw)
                if len(unique_keywords) >= 5:
                    break
            
            # --- Advanced Document Classification ---
            # If it looks like a document or PII, try to get specific type
            if self.is_document_image(img_path) or self.is_pii_document(img_path):
                doc_type = self.classify_document_type(img_path)
                if doc_type:
                    unique_keywords.insert(0, doc_type) # Add as first tag
            
            return unique_keywords if unique_keywords else [caption]
        except Exception as e:
            print(f"Error generating tags: {e}")
            return []

    def is_document_image(self, img_path):
        """
        Uses CLIP to determine if an image is likely a document/text vs a photo.
        Returns Boolean.
        """
        try:
            pil_img = Image.open(img_path)
            # Prompts focused on PHYSICAL/SCANNED documents
            prompts = ["a scanned document", "paperwork", "an invoice", "a receipt", "a text document on paper", "printed text", "a letter", "a contract"]
            
            # Negatives focused on DIGITAL/GRAPHICAL content
            neg_prompts = [
                "a photo of a person", "a landscape", "a pet", "a selfie", "nature", 
                "an indoor photo", "a room", "a street", "food", "an object",
                "a poster", "a banner", "an advertisement", "a flyer", "a presentation slide", 
                "graphic design", "a social media post", "digital art", "a meme", "text overlay on photo"
            ]
            
            all_prompts = prompts + neg_prompts
            
            encoded_img = self.similarity_model.encode(pil_img, convert_to_tensor=True)
            encoded_text = self.similarity_model.encode(all_prompts, convert_to_tensor=True)
            
            sims = self.util.cos_sim(encoded_img, encoded_text)[0]
            
            # Average score for positive vs negative prompts
            pos_score = sims[:len(prompts)].mean()
            neg_score = sims[len(prompts):].mean()

            # Stricter threshold: Must clearly be a document (0.05 buffer)
            return pos_score > (neg_score + self.thr["doc"])
            
        except Exception as e:
            print(f"Error detecting document: {e}")
            return False

    def is_pii_document(self, img_path):
        """
        Uses CLIP to detect sensitive PII documents.
        Prompts: Passport, ID Card, Credit Card, etc.
        """
        try:
            pil_img = Image.open(img_path)
            # PII Prompts
            prompts = [
                "a passport", "an identity card", "a driver license", 
                "a credit card", "a social security card", "a bank statement",
                "a tax document", "a medical report", "a birth certificate",
                "a visa", "a legal contract", "a w2 form", "an official government letter",
                "a form with personal information"
            ]
            # Content that is definitely NOT PII (generic docs or photos)
            neg_prompts = [
                "a landscape", "a pet", "a selfie", "a receipt", "a flyer", 
                "a book page", "a screenshot of chat", "a random photo", "a menu",
                "a poster", "a sign", "graphic design", "abstract art", "a red block",
                "a greeting card", "a meme", "a chat bubble", "alphabet", "text message",
                "a chart", "a graph", "an infographic", "a diagram", "financial stats"
            ]
            
            all_prompts = prompts + neg_prompts
            
            encoded_img = self.similarity_model.encode(pil_img, convert_to_tensor=True)
            encoded_text = self.similarity_model.encode(all_prompts, convert_to_tensor=True)
            
            sims = self.util.cos_sim(encoded_img, encoded_text)[0]
            
            pos_score = sims[:len(prompts)].max() # Use MAX match for PII (if it looks like ANY valid ID, flag it)
            neg_score = sims[len(prompts):].max()
            
            # Threshold: Must be somewhat confident it's PII
            return (pos_score > self.thr["pii"]) and (pos_score > neg_score)
            
        except Exception as e:
            print(f"Error detecting PII: {e}")
            return False

    def classify_document_type(self, img_path):
        """
        Uses CLIP to classify specific international document types (India, USA, Financial, etc.)
        Returns the best matching category string or None.
        """
        try:
            pil_img = Image.open(img_path)
            
            # Dictionary of category prompts
            doc_categories = {
                "India Identity": ["aadhaar card", "pan card", "voter id india", "indian driving license"],
                "USA Identity": ["social security card", "green card", "us passport", "us driver license"],
                "Financial": ["bank cheque", "cancelled cheque", "pay stub", "tax return", "bank statement"],
                "Identity": ["passport", "visa", "driving license", "identity card"],
                "Document": ["invoice", "receipt", "legal contract", "medical report", "certificate"]
            }
            
            best_cat = None
            highest_score = 0.0
            
            # Use 'a photo of' prefix for better CLIP matching
            flat_prompts = []
            flat_labels = []
            
            for cat, prompts in doc_categories.items():
                for p in prompts:
                    flat_prompts.append(f"a photo of a {p}")
                    flat_labels.append(f"{cat}: {p.title()}")
            
            # Also add generic negatives to reduce false positives
            neg_prompts = ["a landscape", "a person", "a pet", "food", "text message", "screenshot"]
            all_prompts = flat_prompts + neg_prompts
            
            encoded_img = self.similarity_model.encode(pil_img, convert_to_tensor=True)
            encoded_text = self.similarity_model.encode(all_prompts, convert_to_tensor=True)
            
            sims = self.util.cos_sim(encoded_img, encoded_text)[0]
            # Only look at the document prompts (ignore negatives)
            doc_sims = sims[:len(flat_prompts)]
            
            max_idx = doc_sims.argmax().item()
            max_val = doc_sims[max_idx].item()
            
            # Threshold to apply the specific tag (0.25 is heuristic base)
            if max_val > 0.25:
                return flat_labels[max_idx]
                
            return None
            
        except Exception as e:
            print(f"Error classifying document: {e}")
            return None

    def save_reference(self, img_path, category):
        """
        Learns from a user correction.
        Calculates embedding for img_path and saves it under 'category'.
        Smartly removes this image from ANY other category's references to prevent conflicts.
        """
        try:
            pil_img = Image.open(img_path)
            # Encode just the image - convert to list for JSON storage
            # We use a numpy array for calculation but store as list
            embedding_tensor = self.similarity_model.encode(pil_img, convert_to_tensor=True)
            embedding_list = embedding_tensor.tolist()
            
            # --- 1. SELF-CORRECTION: Remove conflicting old memories ---
            # Check if this image (or a near-identical one) was previously taught as something else
            for existing_cat, examples in list(self.references.items()):
                # We iterate backwards to allow safe removal
                for i in range(len(examples) - 1, -1, -1):
                    ref_emb = self.torch.tensor(examples[i]).to(self.device)
                    score = self.util.cos_sim(embedding_tensor, ref_emb).item()
                    
                    if score > 0.98: # Almost identical image
                        print(f"Correcting memory: Removed conflicting training from '{existing_cat}'")
                        self.references[existing_cat].pop(i)
            
            # --- 2. Add to new category ---
            if category not in self.references:
                self.references[category] = []
            
            # Limit samples per category (FIFO Buffer)
            if len(self.references[category]) >= 50:
                 self.references[category].pop(0)
                 
            self.references[category].append(embedding_list)
            
            os.makedirs(os.path.dirname(self.ref_file), exist_ok=True)
            with open(self.ref_file, 'w') as f:
                json.dump(self.references, f)
            
            print(f"Learned: {os.path.basename(img_path)} is {category}")
            return True
        except Exception as e:
            print(f"Error saving reference: {e}")
            return False

    def is_likely_forward(self, img_path):
        """
        Detects if an image is likely a forward/download (WhatsApp, etc.)
        Heuristics:
        1. Filename contains '-WA' (WhatsApp standard).
        2. MISSING EXIF data (Camera/DateTime), often stripped by messengers.
        3. STRICT: Original photos MUST have camera Make/Model. If missing, likely forwarded.
        """
        try:
            # 1. Check Filename
            fname = str(img_path).lower()
            if "-wa" in fname or "whatsapp" in fname:
                return True
            
            # 2. Check EXIF - STRICT MODE
            # Original photos from cameras/phones ALWAYS have Make/Model
            # Forwarded images often have these stripped
            try:
                img = Image.open(img_path)
                exif = img.getexif()
                
                # No EXIF at all -> Likely downloaded/forwarded/screenshot
                if not exif:
                    return True
                
                # Check specific tags
                # 36867 = DateTimeOriginal, 306 = DateTime, 271 = Make, 272 = Model
                has_datetime = (36867 in exif) or (306 in exif)
                has_camera = (271 in exif) or (272 in exif)
                
                # STRICT: Require BOTH datetime AND camera info for original photos
                # If either is missing, treat as forward
                if not has_camera:
                    # No camera info = definitely forwarded or edited
                    return True
                
                if not has_datetime:
                    # No datetime but has camera = suspicious, likely edited/forwarded
                    return True
                    
            except Exception:
                # Error reading exif -> treat as weird file, likely forwarded
                return True
                
            return False
            
        except Exception as e:
            print(f"Error detecting forward: {e}")
            return False

    def is_meme_or_screenshot(self, img_path):
        """
        Uses CLIP to check if image is likely a Meme, Screenshot, or Social Media post.
        Used to bolster 'Forwards' detection.
        """
        try:
            # OPTIMIZED: Use cached embedding and pre-calculated text embeddings
            encoded_img = self._get_embedding_tensor(img_path)
            if encoded_img is None: return False

            # Combine pos/neg text embeddings into one tensor for comparison
            # (We could optimize this further, but this is already much faster than re-encoding text)
            all_text_embs = self.torch.cat((self._emb_meme_pos, self._emb_meme_neg))
            
            sims = self.util.cos_sim(encoded_img, all_text_embs)[0]
            
            pos_score = sims[:len(self._prompts_meme)].max()
            neg_score = sims[len(self._prompts_meme):].max()
            
            return (pos_score > self.thr["meme"]) and (pos_score > neg_score)

        except Exception as e:
            print(f"Error in is_meme_or_screenshot for {os.path.basename(img_path)}: {e}")
            return False

    def is_screenshot(self, img_path):
        """
        Specific check for Screenshots (distinct from Memes/Forwards)
        """
        try:
            pil_img = Image.open(img_path)
            prompts = [
                "a screenshot", "a mobile interface", "a computer screen", 
                "a web page screenshot", "software interface", "chat screenshot"
            ]
            neg_prompts = [
                "a meme", "a funny picture", "a landscape", "a portrait", 
                "a document", "a receipt", "a scanned paper"
            ]
            
            all_prompts = prompts + neg_prompts
            encoded_img = self.similarity_model.encode(pil_img, convert_to_tensor=True)
            encoded_text = self.similarity_model.encode(all_prompts, convert_to_tensor=True)
            
            sims = self.util.cos_sim(encoded_img, encoded_text)[0]
            
            pos_score = sims[:len(prompts)].max()
            neg_score = sims[len(prompts):].max()
            
            return (pos_score > self.thr["screenshot"]) and (pos_score > neg_score)
        except Exception as e:
            print(f"Error in is_screenshot for {os.path.basename(img_path)}: {e}")
            return False

    def is_likely_forward_visual(self, img_path):
        """
        Detects 'visual' forwards that are not necessarily memes or screenshots.
        Includes: Mantras, Quotes, Digital Greetings, Religious text, Posters.
        """
        try:
            pil_img = Image.open(img_path)
            prompts = [
                "a digital quote", "a mantra", "religious text", "a digital greeting card", 
                "text on plain background", "a social media post", "a whatsapp forward",
                "inspirational quote", "a poster", "a banner"
            ]
            neg_prompts = [
                "a photo of a person", "a landscape", "a pet", "a selfie", "nature", 
                "an indoor photo", "a room", "a street", "food", "an object",
                "a document", "a receipt", "a scanned paper", "a screenshot"
            ]
            
            all_prompts = prompts + neg_prompts
            encoded_img = self.similarity_model.encode(pil_img, convert_to_tensor=True)
            encoded_text = self.similarity_model.encode(all_prompts, convert_to_tensor=True)
            
            sims = self.util.cos_sim(encoded_img, encoded_text)[0]
            
            pos_score = sims[:len(prompts)].max()
            neg_score = sims[len(prompts):].max()
            
            return (pos_score > self.thr["meme"]) and (pos_score > neg_score)
        except Exception as e:
            print(f"Error in is_likely_forward_visual for {os.path.basename(img_path)}: {e}")
            return False

    def write_tags_to_exif(self, img_path, tags):
        """
        Writes AI-generated tags to the image's EXIF metadata (Keywords field).
        Only works with JPEG images that support EXIF.
        Returns True if successful, False otherwise.
        """
        try:
            # Only process JPEG images
            if not img_path.lower().endswith(('.jpg', '.jpeg')):
                return False
            
            # Read existing EXIF data
            try:
                exif_dict = piexif.load(img_path)
            except Exception:
                # If no EXIF exists, create a new dict
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            
            # Convert tags list to comma-separated string
            keywords_str = ", ".join(tags) if tags else ""
            
            # Write to XPKeywords (Windows-compatible) - tag 0x9c9e in IFD0
            # This is a UTF-16LE encoded string
            keywords_bytes = keywords_str.encode('utf-16le') + b'\x00\x00'
            exif_dict["0th"][0x9c9e] = keywords_bytes
            
            # Also write to standard Keywords field if available (tag 0x9c9e doesn't always work)
            # Some software uses ImageDescription (0x010e) or UserComment (0x9286)
            
            # Dump EXIF to bytes
            exif_bytes = piexif.dump(exif_dict)
            
            # Write back to image
            img = Image.open(img_path)
            img.save(img_path, exif=exif_bytes, quality=95)
            
            return True
        except Exception as e:
            print(f"Error writing tags to {img_path}: {e}")
            return False

    def fix_orientation(self, img_path):
        """
        Permanently applies EXIF orientation to the image pixels and resets the tag.
        Returns True if image was rotated/updated, False if no change needed or error.
        """
        try:
            # Check if it's a supported format
            if not img_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                return False

            img = Image.open(img_path)
            exif = img.getexif()
            
            # Tag 274 is Orientation. If it's 1 or missing, no need to fix.
            orientation = exif.get(274)
            if not orientation or orientation == 1:
                return False
            
            # Apply transposition
            # exif_transpose returns a new image copy with pixels rotated and orientation tag removed/reset
            fixed_img = ImageOps.exif_transpose(img)
            
            # Save back to disk
            # We want to preserve other EXIF data if possible, but exif_transpose deliberately strips the orientation.
            # We should copy the original exif (minus orientation) to the new image if we want to be super clean,
            # but usually save() handles basic metadata if we pass it. 
            # However, with PIL, simple save often loses EXIF unless explicitly passed.
            # ImageOps.exif_transpose handles the pixel rotation.
            
            # To be safe and keep things simple for this utility:
            # Just save it. Most viewers will now see it correctly because pixels are rotated.
            # We can optionally use quality=95 for JPEGs.
            
            save_kwargs = {}
            if img_path.lower().endswith(('.jpg', '.jpeg')):
                save_kwargs['quality'] = 95
                save_kwargs['exif'] = fixed_img.getexif() # Try to pass back clean exif
                
            fixed_img.save(img_path, **save_kwargs)
            return True
            
        except Exception as e:
            print(f"Error fixing orientation for {img_path}: {e}")
            return False

    def get_exif_date(self, image_path):
        """
        Extracts the original date taken from EXIF data.
        Returns a datetime object or None.
        """
        try:
            image = Image.open(image_path)
            exif_data = image.getexif()
            if not exif_data:
                # Go to fallback
                raise Exception("No EXIF")
            
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTimeOriginal':
                    # Sometimes value is a bit weird, handle it
                    if isinstance(value, str):
                        return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
        except Exception:
            pass
        
        # Fallback to file creation/modification time if EXIF is missing or invalid
        try:
            mtime = os.path.getmtime(image_path)
            ctime = os.path.getctime(image_path)
            # Use the earlier of the two as a heuristic for "Original Date" if no EXIF exists
            return datetime.fromtimestamp(min(mtime, ctime))
        except Exception:
            return None
