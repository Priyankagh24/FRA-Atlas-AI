from fastapi import FastAPI, HTTPException, APIRouter, UploadFile, File
from pydantic import BaseModel
import ee
import requests
from PIL import Image
import numpy as np
import io
import os
import math
import tensorflow as tf
from shapely.geometry import Polygon, Point
from typing import Optional

router = APIRouter(prefix="/model", tags=["model"])

# ------------------ CONFIG ------------------
MODEL_PATH = "model.keras"            # <- replace with your trained model file path
IMG_SIZE = 64                        # model input size (width & height)
SAVED_IMAGES_DIR = "saved_images"
EE_START_DATE = "2023-01-01"
EE_END_DATE = "2023-12-31"
THUMB_DIM = 512                       # thumbnail pixel dimension
# --------------------------------------------

os.makedirs(SAVED_IMAGES_DIR, exist_ok=True)

# Initialize Earth Engine (assumes ee.Authenticate() was already run interactively)
try:
    ee.Initialize()
except Exception as e:
    # If EE not initialized, the endpoint will fail later with an explicit message
    print("Warning: Earth Engine not initialized. Ensure ee.Authenticate() was run earlier.", e)

# Load TensorFlow model
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "..", "best_model.h5")
HF_SPACE_URL = os.getenv("HF_SPACE_URL", "")  # set this in Render env vars later

# Example mapping: change according to your model's classes
CLASS_NAMES = [
    "AnnualCrop", "Forest", "HerbaceousVegetation",
    "Highway", "Industrial", "Pasture", "PermanentCrop",
    "Residential", "River", "SeaLake"
]  # update to match your model output classes


class Claim(BaseModel):
    id: int
    patta_holder_name: str
    father_or_husband_name: Optional[str] = None
    age: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    village_name: Optional[str] = None
    block: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    total_area_claimed: Optional[str] = None
    coordinates: str
    land_use: Optional[str] = None
    claim_id: Optional[str] = None
    date_of_application: Optional[str] = None

# ---------------- Utility functions ----------------
def parse_coordinate(coord_str: str):
    """Parse 'lat, lon' or 'lon, lat' string into floats and detect order.
       Returns (lat, lon)."""
    try:
        parts = [p.strip() for p in coord_str.replace(',', ' ').split()]
        if len(parts) < 2:
            raise ValueError("coordinate string must have two numeric values")
        a, b = float(parts[0]), float(parts[1])
        # Heuristic: lat in [-90, 90], lon in [-180, 180]; if first value outside [-90,90], treat as lon,lat
        if -90 <= a <= 90 and -180 <= b <= 180:
            # assume a is lat, b is lon
            lat, lon = a, b
        elif -90 <= b <= 90 and -180 <= a <= 180:
            # swapped
            lat, lon = b, a
        else:
            # fallback: assume first is lat
            lat, lon = a, b
        return lat, lon
    except Exception as e:
        raise ValueError(f"Could not parse coordinates: {e}")

def parse_area_to_m2(area_str: str):
    """Parse area strings like '1.00 acres', '0.5 ha', '4000 m2' into square meters."""
    if not area_str:
        return None
    s = area_str.strip().lower()
    try:
        # detect numeric and unit
        # examples: "1.00 acres", "1 acres", "0.5 ha", "1.2 hectare", "4000 m2"
        tokens = s.split()
        num = float(tokens[0])
        unit = tokens[1] if len(tokens) > 1 else "acres"
    except Exception:
        # try to strip trailing unit characters
        import re
        m = re.match(r"([\d\.]+)", s)
        if not m:
            return None
        num = float(m.group(1))
        unit = s[m.end():].strip() or "acres"

    if unit.startswith("acre"):
        return num * 4046.8564224
    if unit.startswith("ha") or "hect" in unit:
        return num * 10000.0
    if unit.startswith("m") or "sq" in unit:
        return num  # assume already m2
    # fallback assume acres
    return num * 4046.8564224

def make_square_polygon(lat, lon, area_m2):
    """Create a simple axis-aligned square polygon (lon,lat order) around (lat,lon) with given area in m2."""
    if area_m2 is None or area_m2 <= 0:
        # default small square (100m)
        half_side = 50.0
    else:
        side = math.sqrt(area_m2)
        half_side = side / 2.0  # meters
    # degrees per meter approx (lat)
    delta_lat = half_side / 111000.0
    # degrees per meter for lon depends on latitude
    delta_lon = half_side / (111000.0 * math.cos(math.radians(lat)) + 1e-9)
    # corners in lon, lat order for EE / shapely polygon
    p1 = (lon - delta_lon, lat - delta_lat)
    p2 = (lon + delta_lon, lat - delta_lat)
    p3 = (lon + delta_lon, lat + delta_lat)
    p4 = (lon - delta_lon, lat + delta_lat)
    return [p1, p2, p3, p4, p1]

def ee_polygon_from_coords(coords_list):
    """Convert list of (lon,lat,...,lon,lat) to ee.Geometry.Polygon form."""
    return ee.Geometry.Polygon([coords_list])

def fetch_satellite_thumbnail(aoi_coords, start_date=EE_START_DATE, end_date=EE_END_DATE, dim=THUMB_DIM):
    """Return a thumbnail URL (PNG) for the AOI. aoi_coords is a list of [ (lon,lat), ... ] with last repeated."""
    aoi = ee_polygon_from_coords(aoi_coords)
    coll = ee.ImageCollection('COPERNICUS/S2')\
            .filterBounds(aoi)\
            .filterDate(start_date, end_date)\
            .select(['B4','B3','B2'])\
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60))\
            .median()\
            .clip(aoi)
    vis = {'min': 0, 'max': 3000, 'bands': ['B4','B3','B2']}
    url = coll.getThumbURL({'region': aoi, 'dimensions': dim, 'format': 'png', **vis})
    return url

def download_image_from_url(url):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")

def preprocess_for_model(pil_img, size=IMG_SIZE):
    img = pil_img.resize((size, size))
    arr = np.array(img).astype(np.float32) / 255.0
    # ensure shape (1, H, W, C)
    return np.expand_dims(arr, axis=0)

def predict_with_model(img_bytes: bytes):
    if not HF_SPACE_URL:
        raise RuntimeError("HF_SPACE_URL not set in environment variables.")
    import requests
    response = requests.post(
        f"{HF_SPACE_URL}/predict",
        files={"file": ("image.png", img_bytes, "image/png")},
        timeout=30
    )
    response.raise_for_status()
    return response.json()

# ---------------- API ENDPOINT ----------------
@router.post("/predict")
def predict(claim: Claim):
    # 1) parse coordinate
    try:
        lat, lon = parse_coordinate(claim.coordinates)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid coordinate: {e}")

    # 2) parse area
    area_m2 = parse_area_to_m2(claim.total_area_claimed or "")
    # 3) create polygon coordinates (lon,lat order)
    square_coords = make_square_polygon(lat, lon, area_m2)
    # 4) get thumbnail URL from Earth Engine
    try:
        thumb_url = fetch_satellite_thumbnail(square_coords)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Earth Engine error: {e}")

    # 5) download thumbnail
    try:
        pil_img = download_image_from_url(thumb_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download thumbnail: {e}")

    # 6) save local image (optional)
    img_filename = f"{SAVED_IMAGES_DIR}/claim_{claim.id}.png"
    pil_img.save(img_filename)

    # 7) preprocess and predict
    try:
        arr = preprocess_for_model(pil_img, size=IMG_SIZE)
        pred = predict_with_model(arr)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model prediction error: {e}")

    # 8) return response
    return {
        "id": claim.id,
        "claim_id": claim.claim_id,
        "input_coordinates": {"lat": lat, "lon": lon},
        "polygon_coords_lonlat": square_coords,
        "thumbnail_url": thumb_url,
        "saved_image": img_filename,
        "model_prediction": pred
    }

@router.post("/classify-image")
async def classify_image(file: UploadFile = File(...)):
    # Check if file is provided and has content
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Check file type - allow common image extensions if content_type is None
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''

    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    elif not file.content_type and f'.{file_ext}' not in allowed_extensions:
        raise HTTPException(status_code=400, detail="File must be an image (jpg, png, gif, bmp, tiff, webp)")

    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file provided")

    try:
        from services.landuse_model import predict_land_use
        label, confidence = predict_land_use(file_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

    return {
        "filename": file.filename,
        "land_use_class": label,
        "confidence": confidence
    }

# Simple root
def root():
    return {"status": "ok", "note": "POST /predict with claim JSON to run the pipeline."}