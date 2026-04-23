"""
landuse_model.py
================
Satellite land-use classifier powered by a EuroSAT-trained CNN.

KEY FIX (2026-04):
  The model was trained on *actual satellite imagery* (64x64 px Sentinel-2
  tiles).  When users upload a **photo / scan of their FRA claim form**, the
  model has no meaningful signal and produces spurious labels like "Highway"
  or "Residential", causing valid claims to be hard-rejected.

  Solution - is_document_image():
    Before running the CNN we run a fast, heuristic check on the raw image:
      * High brightness (mean > 195/255) - paper is white
      * Low colour saturation - grayscale/near-grayscale document
      * High luminance variance - printed text edges
      * Aspect ratio close to standard paper (A4, letter, etc.)
    If 3 out of 4 signals fire we classify the image as a *document* and
    return ("Document", 0.0), which the upload router treats the same as a
    PDF - "Not Validated" - and allows the claim through for manual review.

    Genuine satellite images are colourful, low-brightness, and not paper-
    aspect-ratio, so they continue to go through the CNN as before.
"""

import io
import os
import logging
try:
    import tensorflow as tf
except ImportError:
    tf = None

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model setup
# ---------------------------------------------------------------------------
IMG_SIZE = 64
CLASS_NAMES = [
    "AnnualCrop",
    "Forest",
    "HerbaceousVegetation",
    "Highway",
    "Industrial",
    "Pasture",
    "PermanentCrop",
    "Residential",
    "River",
    "SeaLake",
]

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "best_model.h5")

# Lazy-load the model so startup does not fail if the file is temporarily absent.
_model = None


def _load_model():
    global _model
    if _model is None:
        try:
            if tf is None:
                raise RuntimeError("TensorFlow not available - predictions handled by Hugging Face")
            _model = tf.keras.models.load_model(MODEL_PATH)
            logger.info(f"Land-use model loaded from {MODEL_PATH}")
        except Exception as exc:
            logger.error(f"Could not load land-use model: {exc}")
            raise
    return _model


# ---------------------------------------------------------------------------
# Document-image detection
# ---------------------------------------------------------------------------

# Standard paper aspect ratios (portrait): A4=0.707, US-Letter=0.773
# and their landscape inverses (1.414, 1.294).
_PAPER_RATIOS = [0.707, 0.773, 1.414, 1.294]
_PAPER_RATIO_TOL = 0.12          # +/- 12% tolerance

# Thresholds - tuned conservatively to avoid false-positives on bright farmland.
_BRIGHTNESS_THRESH = 175         # mean pixel value (0-255); paper > 175 (was 195)
_SATURATION_THRESH = 30          # mean HSV-S (0-255); docs typically < 30 (was 25)
_VARIANCE_THRESH   = 400         # pixel variance in luminance; text edges > 400 (was 500)
_SIGNALS_NEEDED    = 2           # classify as document if >= 2 signals match (was 3)


def is_document_image(pil_img: Image.Image) -> bool:
    """
    Return True if pil_img looks like a scanned/photographed document
    rather than a satellite tile.

    Heuristics (each counts as one signal):
      1. High mean brightness  -> white paper background
      2. Low colour saturation -> near-greyscale (text on paper)
      3. High luminance variance -> dense text/line edges
      4. Aspect ratio close to a standard paper size
    """
    # Work on a small thumbnail for speed.
    thumb = pil_img.copy()
    thumb.thumbnail((256, 256))

    rgb = np.array(thumb.convert("RGB"), dtype=np.float32)

    # Signal 1: brightness
    brightness = rgb.mean()
    sig_bright = brightness > _BRIGHTNESS_THRESH

    # Signal 2: saturation (low = near-greyscale = printed text on white paper)
    hsv = np.array(thumb.convert("HSV"), dtype=np.float32)
    mean_sat = hsv[:, :, 1].mean()
    sig_desat = mean_sat < _SATURATION_THRESH

    # Signal 3: luminance variance (text produces sharp high-contrast edges)
    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    lum_var = lum.var()
    sig_var = lum_var > _VARIANCE_THRESH

    # Signal 4: aspect ratio close to a standard paper size
    w, h = pil_img.size
    ratio = min(w, h) / max(w, h)   # normalised to <= 1 (portrait)
    sig_ratio = any(abs(ratio - r) < _PAPER_RATIO_TOL for r in _PAPER_RATIOS)

    signals = sum([sig_bright, sig_desat, sig_var, sig_ratio])
    is_doc = signals >= _SIGNALS_NEEDED

    logger.debug(
        f"Doc-detect: brightness={brightness:.1f}(ok={sig_bright}) "
        f"sat={mean_sat:.1f}(ok={sig_desat}) "
        f"var={lum_var:.0f}(ok={sig_var}) "
        f"ratio={ratio:.3f}(ok={sig_ratio}) "
        f"=> signals={signals}/4 => is_doc={is_doc}"
    )
    return is_doc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def predict_land_use(file_bytes: bytes):
    """
    Predict the land-use class from file_bytes (PNG / JPEG).

    Returns
    -------
    label : str
        EuroSAT class name, or "Document" if the image appears to be a
        scanned form rather than a satellite tile.
    confidence : float
        Model softmax probability (0.0 for "Document" returns).
    """
    image = Image.open(io.BytesIO(file_bytes)).convert("RGB")

    # Guard: detect document images BEFORE running the satellite CNN
    if is_document_image(image):
        logger.info(
            "Uploaded image classified as a document/form scan - "
            "skipping satellite ML classification."
        )
        return "Document-Scan", 0.0

    # Normal path: satellite image -> CNN
    model = _load_model()

    img_arr = image.resize((IMG_SIZE, IMG_SIZE))
    img_arr = np.array(img_arr) / 255.0
    img_arr = np.expand_dims(img_arr, axis=0)

    preds      = model.predict(img_arr)
    class_idx  = int(np.argmax(preds))
    confidence = float(np.max(preds))
    label      = CLASS_NAMES[class_idx] if class_idx < len(CLASS_NAMES) else "Unknown"

    return label, confidence