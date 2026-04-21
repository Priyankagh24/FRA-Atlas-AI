from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from fastapi.responses import JSONResponse
from db import engine
from pydantic import BaseModel
from typing import Optional
import math
import io
import os
import json
import traceback
import logging

# Professional Satellite & AI Imports
try:
    import ee
    import numpy as np
    import tensorflow as tf
    from PIL import Image
    from collections import Counter
    import requests as http_requests
except ImportError as e:
    logging.error(f"Failed to import satellite/ML dependencies: {e}")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/atlas", tags=["Atlas"])

# ── Global AI Model Loading (Performance Optimisation) ────────────────────────
MODEL = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "..", "best_model.h5")

def _load_model_safe():
    global MODEL
    if MODEL: return MODEL
    try:
        if os.path.exists(MODEL_PATH):
            MODEL = tf.keras.models.load_model(MODEL_PATH)
            logger.info("✅ Atlas AI Model loaded into memory.")
        else:
            logger.warning(f"⚠️ Model file not found at {MODEL_PATH}")
    except Exception as e:
        logger.error(f"❌ Failed to load Atlas AI Model: {e}")
    return MODEL

# ── Global GEE Initialisation (Stability Optimisation) ────────────────────────
GEE_INITIALIZED = False
GEE_ERROR = None

def _init_gee_safe():
    global GEE_INITIALIZED, GEE_ERROR
    if GEE_INITIALIZED: return True
    try:
        ee.Initialize(project='eighth-zenith-493606-b1')
        GEE_INITIALIZED = True
        logger.info("✅ Google Earth Engine Initialized (Project: eighth-zenith-493606-b1)")
        return True
    except Exception as e:
        GEE_ERROR = str(e)
        logger.error(f"❌ GEE Initialization failed: {GEE_ERROR}")
        return False

# Trigger lazy initialization (Uvicorn reload will handle this on startup)
_load_model_safe()
_init_gee_safe()

# ── Helper: Spatial Cloud Masking ─────────────────────────────────────────────
def _mask_clouds(img):
    qa = img.select('QA60')
    cloud_bit = 1 << 10
    cirrus_bit = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit).eq(0).And(qa.bitwiseAnd(cirrus_bit).eq(0))
    return img.updateMask(mask).divide(10000)


def _parse_coords(coord_str: str):
    """Parse 'lat, lon' string → (lat, lon) floats or None."""
    try:
        parts = [p.strip() for p in str(coord_str).split(",")]
        if len(parts) < 2:
            return None
        lat, lon = float(parts[0]), float(parts[1])
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except Exception:
        pass
    return None


def _make_geojson_polygon(lat: float, lon: float, area_str: str) -> dict:
    """Generate a square GeoJSON polygon around a point for the given area."""
    try:
        tokens = str(area_str).lower().split()
        num = float(tokens[0]) if tokens else 0.5
        unit = tokens[1] if len(tokens) > 1 else "acres"
        if "hectare" in unit or unit == "ha":
            area_m2 = num * 10000
        else:
            area_m2 = num * 4046.86
    except Exception:
        area_m2 = 2000

    half = math.sqrt(area_m2) / 2
    dlat = half / 111320
    dlon = half / (111320 * math.cos(math.radians(lat)) + 1e-9)

    coords = [
        [lon - dlon, lat - dlat],
        [lon + dlon, lat - dlat],
        [lon + dlon, lat + dlat],
        [lon - dlon, lat + dlat],
        [lon - dlon, lat - dlat],
    ]
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [coords]},
        "properties": {},
    }


def _map_land_use_to_class(lu: str) -> tuple:
    """Map any land use string to a standard display class."""
    if not lu:
        return "Unknown", 0.50
    lu_lower = lu.lower().strip()
    if any(k in lu_lower for k in ["forest", "van", "jungle", "herbaceous", "vegetation"]):
        return "Forest", 0.91
    if any(k in lu_lower for k in ["agri", "crop", "farm", "cultivation", "paddy", "wheat", "annual", "permanent"]):
        return "Agriculture", 0.88
    if any(k in lu_lower for k in ["home", "house", "residential", "ghar", "awas", "dwelling", "settlement"]):
        return "Homestead", 0.87
    if any(k in lu_lower for k in ["water", "river", "nadi", "lake", "pond", "talab", "sea"]):
        return "Water Body", 0.89
    if any(k in lu_lower for k in ["pasture", "grass", "grazing", "charai"]):
        return "Pasture", 0.85
    return lu.strip().title(), 0.75


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/claims")
def get_all_claims_for_atlas():
    """Returns all FRA claims with all fields needed for Atlas visualization."""
    query = text("""
        SELECT
            id,
            patta_holder_name,
            father_or_husband_name,
            village_name,
            district,
            state,
            total_area_claimed,
            coordinates,
            claim_id,
            claim_type,
            COALESCE(status, 'pending') AS status,
            land_use,
            ml_land_use,
            ml_confidence,
            eligible_scheme,
            validation_status,
            date_of_application,
            age,
            gender,
            created_at
        FROM fra_documents
        WHERE coordinates IS NOT NULL
          AND coordinates <> ''
        ORDER BY created_at DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return {"results": [dict(row) for row in rows]}


class CoordinateClassifyRequest(BaseModel):
    lat: float
    lon: float
    claim_id: Optional[str] = None
    total_area_claimed: Optional[str] = "1 acres"


@router.post("/classify-coordinates")
def classify_coordinates(req: CoordinateClassifyRequest):
    """
    AI-powered land use classification for a given lat/lon.

    FIXED priority chain:
      1. Google Earth Engine + CNN (live satellite) — only when GEE credentials exist
      2. Stored DB ML prediction from upload-time CNN  ← NEW: this was being skipped entirely
      3. FRA document declared land use               ← NEW: used as fallback, not a heuristic
      4. Geographic biome heuristic                   ← LAST resort only, clearly labelled

    BUG FIXED: Previously, when GEE failed (no credentials), the code skipped
    directly to a hardcoded geographic heuristic that returned "Forest" for most
    of Central/Eastern India regardless of what the CNN actually predicted at
    upload time. This caused Residential/Agriculture claims in Odisha/Jharkhand
    to always show a mismatch in the Atlas. Now the DB's stored CNN prediction
    (recorded at upload) is used as the primary offline verification source.
    """
    if not (-90 <= req.lat <= 90 and -180 <= req.lon <= 180):
        raise HTTPException(400, "Invalid coordinates")

    # ── Phase 1: Fetch stored claim data from DB ──────────────────────────────
    claimed_lu = None
    db_ml_label = None
    db_ml_conf = None
    db_state = None
    db_district = None
    db_village = None
    db_validation_status = None

    if req.claim_id:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT land_use, ml_land_use, ml_confidence,
                           state, district, village_name, validation_status
                    FROM fra_documents WHERE claim_id = :cid
                """),
                {"cid": req.claim_id}
            ).mappings().first()
            if row:
                claimed_lu          = row.get("land_use") or ""
                db_ml_label         = row.get("ml_land_use") or ""
                db_ml_conf          = row.get("ml_confidence")
                db_state            = row.get("state") or ""
                db_district         = row.get("district") or ""
    db_village          = row.get("village_name") or ""
    db_validation_status = row.get("validation_status") or ""
    gee_error_detail    = None

    # ── Phase 2: Live Sentinel-2 Spatial Consensus AI (Professional) ─────────
    try:
        if not _init_gee_safe():
            raise Exception(GEE_ERROR or "GEE Not Initialized")
            
        model = _load_model_safe()
        if not model:
            raise Exception("AI Model not available on server")

        half_deg = 0.009
        aoi_coords = [
            [req.lon - half_deg, req.lat - half_deg],
            [req.lon + half_deg, req.lat - half_deg],
            [req.lon + half_deg, req.lat + half_deg],
            [req.lon - half_deg, req.lat + half_deg],
            [req.lon - half_deg, req.lat - half_deg],
        ]
        aoi = ee.Geometry.Polygon([aoi_coords])
        
        coll = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate("2023-01-01", "2024-12-31")
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
            .map(_mask_clouds)
            .median()
            .clip(aoi)
        )
        
        # ── Spectral Verification (Multi-Sensor) ─────────────────────────────
        # NDWI = (Green - NIR) / (Green + NIR) -> Sentinel-2 B3 & B8
        # High value (> 0.0) indicates deep water.
        ndwi_img = coll.normalizedDifference(['B3', 'B8'])
        ndwi_val = ndwi_img.reduceRegion(
            reducer=ee.Reducer.median(),
            geometry=aoi,
            scale=10
        ).get('nd').getInfo()
        
        # Professional-grade TCI (True Color Image) thumbnail for UI
        vis = {"min": 0, "max": 0.3, "bands": ["B4", "B3", "B2"]}
        thumb_url = coll.getThumbURL({"region": aoi, "dimensions": 192, "format": "png", **vis})

        resp = http_requests.get(thumb_url, timeout=30)
        resp.raise_for_status()

        grid_img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        
        tiles = []
        for y in range(3):
            for x in range(3):
                tile = grid_img.crop((x*64, y*64, (x+1)*64, (y+1)*64))
                tiles.append(np.array(tile).astype(np.float32) / 255.0)
        
        batch = np.array(tiles) 

        CLASS_NAMES = [
            "AnnualCrop", "Forest", "HerbaceousVegetation", "Highway",
            "Industrial", "Pasture", "PermanentCrop", "Residential", "River", "SeaLake"
        ]
        
        preds_batch = model.predict(batch, verbose=0)
        tile_labels = [CLASS_NAMES[int(np.argmax(p))] for p in preds_batch]
        
        counts = Counter(tile_labels)
        winner, win_count = counts.most_common(1)[0]
        consensus_pct = win_count / 9.0
        avg_confidence = float(np.mean([np.max(p) for p in preds_batch]))

        # ── Spectral Override ────────────────────────────────────────────────
        # If NDWI > 0.01, it is a clear spectral signal of water.
        # Overrule the AI guess if it says PermanentCrop, Forest, or Herbaceous.
        final_winner = winner
        
        if (ndwi_val and ndwi_val > 0.01):
            if winner in ["PermanentCrop", "Forest", "HerbaceousVegetation", "Pasture"]:
                final_winner = "River"
                avg_confidence = 0.98 # Signal from NIR sensor is high authority

        return {
            "status": "ok",
            "coordinates": {"lat": req.lat, "lon": req.lon},
            "classification": {
                "source": "satellite_ai",
                "is_independent_verification": True,
                "land_use_class": final_winner,
                "confidence": round(avg_confidence, 4),
                "consensus_score": round(consensus_pct, 2),
                "thumbnail_url": thumb_url,
                "claimed_land_use": claimed_lu,
                "ndwi_value": round(float(ndwi_val or 0), 4),
                "method": "Spatial Consensus + Spectral Multi-Sensor Verification"
            },
            "geojson": _make_geojson_polygon(req.lat, req.lon, req.total_area_claimed or "1 acres"),
        }
    except Exception as ee_err:
        # Capture raw error but also provide a clean explanation for UI
        raw_error = str(ee_err)
        trace = traceback.format_exc()
        logger.error(f"⚠️ Live GEE pipeline unavailable:\n{trace}")
        
        gee_status = "unauthenticated" if "not authenticated" in raw_error.lower() else "connection_error"
        gee_error_detail = raw_error

    # ── Phase 3: Use stored DB CNN prediction (upload-time result) ────────────
    # FIX: This was being completely skipped before, jumping straight to the
    # biome heuristic. The CNN already ran on the uploaded image at upload time
    # and stored its result. That result is far more accurate than a lat/lon rule.
    #
    # Skip this phase only if:
    #   - No claim_id was provided
    #   - The stored label is "Document-Scan", "Pending Satellite Scan",
    #     "Not Applicable", or "ML Error" (i.e. the CNN never ran meaningfully)
    SKIP_DB_LABELS = {
        "", "document-scan", "pending satellite scan",
        "not applicable", "ml error", "unknown"
    }
    if (
        db_ml_label
        and db_ml_label.lower().strip() not in SKIP_DB_LABELS
        and db_ml_conf is not None
    ):
        # Normalise the stored CNN class to a display-friendly label
        display_class, _ = _map_land_use_to_class(db_ml_label)
        location_desc = ", ".join(filter(None, [db_village, db_district, db_state]))

        return {
            "status": "ok",
            "coordinates": {"lat": req.lat, "lon": req.lon},
            "classification": {
                "source": "db_ml_prediction",
                "is_independent_verification": True,
                "land_use_class": display_class,
                "confidence": round(float(db_ml_conf), 4),
                "claimed_land_use": claimed_lu,
                "method": (
                    f"CNN Model (EuroSAT, upload-time prediction)"
                    + (f" — {location_desc}" if location_desc else "")
                ),
                "raw_ml_label": db_ml_label,
                "gee_error": gee_error_detail,
                "upload_validation": db_validation_status,
            },
            "geojson": _make_geojson_polygon(req.lat, req.lon, req.total_area_claimed or "1 acres"),
        }

    # ── Phase 4: FRA document declared land use ───────────────────────────────
    # If the CNN never ran (PDF upload, document scan, or error), use the
    # declared land use from the FRA document itself. This is NOT independent
    # verification — it just echoes what the claimant wrote. Label it clearly.
    if claimed_lu and claimed_lu.strip():
        display_class, conf = _map_land_use_to_class(claimed_lu)
        location_desc = ", ".join(filter(None, [db_village, db_district, db_state]))
        return {
            "status": "ok",
            "coordinates": {"lat": req.lat, "lon": req.lon},
            "classification": {
                "source": "fra_document",
                "is_independent_verification": False,  # <-- important: not independent
                "land_use_class": display_class,
                "confidence": conf,
                "claimed_land_use": claimed_lu,
                "method": (
                    "FRA document declared land use (not independently verified)"
                    + (f" — {location_desc}" if location_desc else "")
                    + ". Upload a satellite image to enable CNN verification."
                ),
            },
            "geojson": _make_geojson_polygon(req.lat, req.lon, req.total_area_claimed or "1 acres"),
        }

    # ── Phase 5: Geographic biome heuristic — LAST RESORT only ───────────────
    # BUG FIX: This was previously the PRIMARY fallback. It is now LAST.
    # It should only fire when there is literally no other data (no claim_id,
    # no DB record, no claimed land use at all).
    # It is clearly labelled as an estimate so the UI can warn the user.
    label, conf, zone_desc = _india_biome_estimate(req.lat, req.lon)
    return {
        "status": "ok",
        "coordinates": {"lat": req.lat, "lon": req.lon},
        "classification": {
            "source": "coordinate_heuristic",
            "is_independent_verification": False,
            "land_use_class": label,
            "confidence": conf,
            "claimed_land_use": claimed_lu,
            "method": (
                f"⚠️ Geographic zone estimate only — no satellite data available. "
                f"Zone: {zone_desc}. Upload a satellite image for real verification."
            ),
        },
        "geojson": _make_geojson_polygon(req.lat, req.lon, req.total_area_claimed or "1 acres"),
    }


def _india_biome_estimate(lat: float, lon: float) -> tuple:
    """
    Rule-based land use estimate for India.
    NOTE: This is a LAST-RESORT fallback only. It is coarse and should never
    be used as verification. It was previously the primary fallback, which
    caused false mismatches for Residential/Agriculture claims in forest zones.
    """
    if 18 <= lat <= 25 and 78 <= lon <= 87:
        return "Forest", 0.55, "Central Indian forest belt (Vindhya-Satpura) — low confidence estimate"
    if 22 <= lat <= 27 and 88 <= lon <= 97:
        return "Forest", 0.58, "Northeast India dense forest zone — low confidence estimate"
    if 8 <= lat <= 20 and 73 <= lon <= 77:
        return "Forest", 0.54, "Western Ghats corridor — low confidence estimate"
    if 24 <= lat <= 30 and 74 <= lon <= 89:
        return "Agriculture", 0.52, "Indo-Gangetic Plain — low confidence estimate"
    if 15 <= lat <= 22 and 76 <= lon <= 83:
        return "Agriculture", 0.50, "Deccan plateau — low confidence estimate"
    if lat <= 15 and 76 <= lon <= 82:
        return "Agriculture", 0.48, "South India coastal — low confidence estimate"
    return "Unknown", 0.40, "India tribal belt — insufficient data for estimate"


@router.get("/asset-layers")
def get_asset_layers(
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
):
    """Returns aggregated asset layer data grouped by land use type."""
    base_q = """
        SELECT
            id, patta_holder_name, coordinates, land_use,
            ml_land_use, ml_confidence, village_name, district, state,
            total_area_claimed, claim_id, eligible_scheme
        FROM fra_documents
        WHERE coordinates IS NOT NULL AND coordinates <> ''
    """
    params = {}
    if state:
        base_q += " AND LOWER(state) = LOWER(:state)"
        params["state"] = state
    if district:
        base_q += " AND LOWER(district) = LOWER(:district)"
        params["district"] = district

    with engine.connect() as conn:
        rows = conn.execute(text(base_q), params).mappings().all()

    layers = {"forest": [], "agriculture": [], "water": [], "homestead": [], "other": []}
    for row in rows:
        d = dict(row)
        lu = (d.get("ml_land_use") or d.get("land_use") or "").lower()
        if any(k in lu for k in ["forest", "herbaceous", "pasture"]):
            layers["forest"].append(d)
        elif any(k in lu for k in ["crop", "agri", "farm", "cultivation", "pasture", "permanent"]):
            layers["agriculture"].append(d)
        elif any(k in lu for k in ["river", "sea", "lake", "water"]):
            layers["water"].append(d)
        elif any(k in lu for k in ["residential", "home", "house", "homestead"]):
            layers["homestead"].append(d)
        else:
            layers["other"].append(d)

    return {
        "status": "ok",
        "total": len(rows),
        "layers": {key: {"count": len(items), "items": items} for key, items in layers.items()}
    }


@router.get("/progress")
def get_fra_progress(
    level: str = Query("state", description="state | district | village | block"),
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
):
    """FRA progress tracking at village / block / district / state level."""
    if level not in ("state", "district", "village", "block"):
        raise HTTPException(400, "level must be one of: state, district, village, block")

    group_col = {"state": "state", "district": "district", "village": "village_name", "block": "block"}[level]

    query_str = f"""
        SELECT
            COALESCE({group_col}, 'Unknown') AS location,
            COUNT(*)                                                      AS total_claims,
            COUNT(*) FILTER (WHERE LOWER(validation_status) LIKE '%match%' AND LOWER(validation_status) NOT LIKE '%mis%') AS verified,
            COUNT(*) FILTER (WHERE LOWER(validation_status) LIKE '%mismatch%') AS mismatch,
            COUNT(*) FILTER (WHERE LOWER(validation_status) LIKE '%not%')      AS not_validated,
            COUNT(DISTINCT eligible_scheme)                               AS scheme_count,
            ROUND(AVG(CASE WHEN age ~ '^[0-9]+$' THEN age::numeric ELSE NULL END), 1) AS avg_age
        FROM fra_documents
        WHERE {group_col} IS NOT NULL AND TRIM({group_col}) != ''
    """
    params = {}
    if state:
        query_str += " AND LOWER(state) = LOWER(:state)"
        params["state"] = state
    if district:
        query_str += " AND LOWER(district) = LOWER(:district)"
        params["district"] = district

    query_str += f" GROUP BY {group_col} ORDER BY total_claims DESC"

    with engine.connect() as conn:
        rows = conn.execute(text(query_str), params).mappings().all()

    results = []
    for row in rows:
        d = dict(row)
        total = d["total_claims"] or 1
        d["verified_pct"] = round((d["verified"] / total) * 100, 1)
        results.append(d)

    return {"status": "ok", "level": level, "count": len(results), "results": results}


@router.get("/shapefile/{claim_id}")
def get_claim_shapefile(claim_id: str):
    """Returns a GeoJSON Feature for a single claim (land boundary polygon)."""
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, patta_holder_name, coordinates, total_area_claimed,
                       land_use, claim_type, state, district, village_name,
                       claim_id, eligible_scheme, validation_status
                FROM fra_documents WHERE claim_id = :cid
            """),
            {"cid": claim_id}
        ).mappings().first()

    if not row:
        raise HTTPException(404, f"Claim {claim_id} not found")

    d = dict(row)
    coords = _parse_coords(d.get("coordinates", ""))
    if not coords:
        raise HTTPException(422, "Claim has no valid coordinates")

    lat, lon = coords
    feature = _make_geojson_polygon(lat, lon, d.get("total_area_claimed") or "1 acres")
    feature["properties"] = {
        "claim_id":        d["claim_id"],
        "patta_holder":    d["patta_holder_name"],
        "land_use":        d["land_use"],
        "claim_type":      d["claim_type"],
        "state":           d["state"],
        "district":        d["district"],
        "village":         d["village_name"],
        "eligible_scheme": d["eligible_scheme"],
        "validation":      d["validation_status"],
    }

    return JSONResponse(content={"type": "FeatureCollection", "features": [feature]})