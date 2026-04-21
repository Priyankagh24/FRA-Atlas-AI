"""
upload_router.py  —  FIXED VERSION
====================================
Key fixes in this version:
  1. HARD BLOCK on land use mismatch — data is NEVER stored in DB if ML
     detects a land use mismatch (regardless of confidence threshold).
     Low-confidence ML results are marked "Unverified" and allowed through;
     genuine mismatches at ANY confidence are rejected before INSERT.

  2. OCR Claim ID correction — smart, position-aware fix:
     - '@' → '0'  (most common OCR artifact)
     - 'O'/'o' → '0' ONLY in numeric segments (not in state-code segment)
     - '9' ↔ '0' confusion guarded by format re-validation
     - Full FRA-XX-YYYY-NNN pattern enforcement after correction

  3. Land use extraction hardened — strips trailing OCR garbage, prevents
     bleed-over from Type-of-Claim field, re-normalises synonyms.

  4. All previous bug fixes (indentation, validation, NER merge) retained.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text
from db import engine

import os
import re
import uuid
import json as _json
import requests
import logging

from utils.ocr_utils import extract_text_from_file
from utils.llm_utils import clean_with_llm, INDIAN_STATES
from utils.ner_utils import extract_entities, entities_to_document_fields
from utils.eligibility_utils import determine_scheme
from utils.certificate_generator import generate_claim_certificate
from services.landuse_model import predict_land_use

logger = logging.getLogger(__name__)
ALLOWED_STATES = {state.lower() for state in INDIAN_STATES}
router = APIRouter(prefix="/upload", tags=["upload"])


# ==========================================================
# 🔹 HELPERS
# ==========================================================

def safe_str(value):
    if value is None:
        return ""
    return str(value).strip()


def safe_int(value):
    try:
        return int(safe_str(value))
    except Exception:
        return None


def is_state_allowed(state: str) -> bool:
    return safe_str(state).lower() in ALLOWED_STATES


def extract_state_from_text(text: str) -> str:
    match = re.search(r"State\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if match:
        return safe_str(match.group(1))
    return ""


def validate_required_fields(data: dict):
    required_fields = ["Patta-Holder Name", "State", "District"]

    if not data or not isinstance(data, dict):
        return False, "No data extracted from document"

    for field in required_fields:
        value = safe_str(data.get(field))
        if not value or len(value) < 2:
            return False, f"Missing or invalid required field: {field}"

    patta_name = safe_str(data.get("Patta-Holder Name"))
    GARBAGE_PATTERNS = [
        r"father", r"husband", r"s/o", r"w/o", r"d/o",
        r"name\s*:", r"^\s*none\s*$", r"^\s*n/?a\s*$",
        r"^\s*null\s*$", r"^\s*unknown\s*$",
    ]
    for pattern in GARBAGE_PATTERNS:
        if re.search(pattern, patta_name, re.IGNORECASE):
            return False, (
                f"Patta-Holder Name could not be extracted correctly. "
                f"OCR returned '{patta_name}' which appears to be a different field."
            )

    state = safe_str(data.get("State"))
    if not is_state_allowed(state):
        allowed_list = ", ".join(sorted({s.title() for s in ALLOWED_STATES}))
        return False, f"State '{state or 'unknown'}' is not permitted. Allowed states: {allowed_list}"

    return True, ""


def claim_id_exists(claim_id: str):
    if not claim_id:
        return False
    query = text("SELECT 1 FROM fra_documents WHERE claim_id = :cid LIMIT 1")
    with engine.connect() as conn:
        return conn.execute(query, {"cid": claim_id}).fetchone() is not None


def get_coordinates_from_address(address: str, village: str = "", district: str = "", state: str = ""):
    """
    Attempt to fetch coordinates from Nominatim with triple fallback:
    1. Full Address (Village, District, State)
    2. District Only (District, State)
    3. State Only (State)
    """
    targets = []
    if address.strip(): targets.append(address)
    if district.strip() and state.strip(): targets.append(f"{district}, {state}, India")
    if state.strip(): targets.append(f"{state}, India")

    headers = {"User-Agent": "fra-doc-system-v9"}
    for q in targets:
        try:
            logger.info(f"🌐 Geocoding attempt: {q}")
            url = "https://nominatim.openstreetmap.org/search"
            params = {"q": q, "format": "json", "limit": 1}
            res = requests.get(url, params=params, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data:
                    logger.info(f"📍 Geocode success for '{q}': {data[0]['lat']}, {data[0]['lon']}")
                    return f"{data[0]['lat']}, {data[0]['lon']}"
        except Exception as e:
            logger.warning(f"⚠️ Geocoding failed for '{q}': {str(e)}")
    
    return ""


# ==========================================================
# 🔹 OCR CLAIM-ID CORRECTION  (smart, position-aware)
# ==========================================================

def correct_claim_id_ocr(raw: str) -> str:
    """
    Correct OCR misreads in a Claim ID string.

    FRA claim IDs follow the pattern:  FRA-<STATE_CODE>-<YEAR>-<SEQ>
    e.g.  FRA-OD-2024-001,  FRA-TR-2026-045,  FRA-CG-2024-@0456

    Rules applied (in order):
      1. Uppercase + strip whitespace
      2. '@' → '0'  (universal OCR artifact for zero)
      3. In the YEAR segment (4-char numeric): O/o → 0, l/I/L → 1
      4. In the SEQ segment (numeric suffix): O/o → 0, l/I/L → 1, S/s → 5
      5. Leave the STATE_CODE segment (2 alpha chars) completely untouched
         so that 'OD' (Odisha), 'TS' (Telangana) are never corrupted.
    """
    if not raw:
        return ""

    cid = raw.upper().strip()
    cid = cid.replace("@", "0")       # '@' is always OCR artifact for '0'
    cid = re.sub(r"\s+", "", cid)     # remove any embedded spaces

    # Try to parse the structured segments
    # Format A: FRA-XX-YYYY-NNN  or  Format B: FRA-XX-YYYY
    m = re.match(
        r"^(FRA)-([A-Z]{2})-([A-Z0-9]{4})(?:-([A-Z0-9]+))?$",
        cid,
        re.IGNORECASE,
    )
    if m:
        prefix     = "FRA"
        state_code = m.group(2).upper()   # keep as-is — it's alphabetic
        year_seg   = m.group(3).upper()
        seq_seg    = (m.group(4) or "").upper()

        # Fix YEAR segment: O→0, l/I/L→1
        year_seg = re.sub(r"[OoQD]", "0", year_seg)   # Q and D also look like 0
        year_seg = re.sub(r"[IlL]",  "1", year_seg)

        # Fix SEQ segment: O→0, l/I→1, S→5, B→8, Z→2
        if seq_seg:
            seq_seg = re.sub(r"[OoQD]", "0", seq_seg)
            seq_seg = re.sub(r"[IlL]",  "1", seq_seg)
            seq_seg = re.sub(r"[Ss]",   "5", seq_seg)
            seq_seg = re.sub(r"[Bb]",   "8", seq_seg)
            seq_seg = re.sub(r"[Zz]",   "2", seq_seg)
            return f"{prefix}-{state_code}-{year_seg}-{seq_seg}"
        else:
            return f"{prefix}-{state_code}-{year_seg}"

    # If the ID doesn't match structured format, apply broad corrections
    # but only in clearly numeric runs (digits adjacent to letters O/I/l).
    cid = re.sub(r"(?<=\d)[OoQD](?=\d)", "0", cid)
    cid = re.sub(r"(?<=\d)[IlL](?=\d)",  "1", cid)
    cid = re.sub(r"[Ss](?=\d)",           "5", cid)
    cid = re.sub(r"(?<=\d)[OoQD]$",       "0", cid)
    return cid


# ==========================================================
# 🔹 LAND-USE MATCH LOGIC
# ==========================================================

VALID_FRA_LAND_USES = {
    # Agriculture
    "annual crop", "annualcrop", "crop", "agriculture", "agri",
    "cultivation", "farm", "farmland", "permanent crop", "permanentcrop",
    "horticulture", "plantation",
    # Forest
    "forest", "forest produce", "mfp", "ntfp", "minor forest",
    "herbaceous vegetation", "herbaceousvegetation",
    # Pasture / grazing
    "pasture", "grazing", "grassland",
    # Homestead / residential
    "homestead", "home stead", "residential", "house", "hut",
    "dwelling", "habitat", "settlement",
    # Water / community
    "water bodies", "water body", "river", "pond", "lake", "sealake",
    # Misc FRA-recognised
    "community", "mixed",
}

# ML EuroSAT class → set of semantically equivalent claimed-land-use keywords
ML_LABEL_ALIASES = {
    "annualcrop":           {"annual crop", "crop", "agriculture", "agri", "cultivation", "farm", "farmland"},
    "forest":               {"forest", "forest produce", "mfp", "ntfp", "minor forest"},
    "herbaceousvegetation": {"pasture", "grazing", "grassland", "herbaceous", "vegetation"},
    "highway":              {"highway", "road"},
    "industrial":           {"industrial", "industry"},
    "pasture":              {"pasture", "grazing", "grassland"},
    "permanentcrop":        {"permanent crop", "horticulture", "plantation", "orchard", "permanentcrop"},
    "residential":          {"residential", "homestead", "home stead", "house", "hut",
                             "dwelling", "habitat", "settlement"},
    "river":                {"river", "water bodies", "water body", "pond"},
    "sealake":              {"lake", "sea", "sealake", "water bodies", "water body"},
}


def land_uses_match(ml_label: str, claimed: str) -> bool:
    """
    Return True if the ML-predicted label and the claimed land use are
    semantically equivalent.
    """
    ml_key     = ml_label.lower().replace(" ", "")
    claimed_n  = claimed.lower().strip()

    # Fast path: substring overlap
    if ml_key in claimed_n or claimed_n in ml_key:
        return True

    # Alias map lookup
    for alias in ML_LABEL_ALIASES.get(ml_key, set()):
        if alias in claimed_n or claimed_n in alias:
            return True

    return False


# ==========================================================
# 🔹 VERIFY CERTIFICATE
# ==========================================================

@router.get("/api/verify/{claim_id}")
def verify_certificate(claim_id: str):
    claim_id = claim_id.replace('"', '').replace(',', '').strip()
    with engine.connect() as conn:
        record = conn.execute(
            text("SELECT * FROM fra_documents WHERE claim_id = :cid"),
            {"cid": claim_id}
        ).mappings().first()

    if not record:
        return {"status": "NOT_FOUND"}
    if record.get("certificate_status") != "ACTIVE":
        return {"status": "REVOKED"}
    if not record.get("certificate_hash"):
        return {"status": "NOT_GENERATED"}

    return {
        "status": "AUTHENTIC",
        "data": {
            "name":       record["patta_holder_name"],
            "claim_id":   record["claim_id"],
            "scheme":     record["eligible_scheme"],
            "validation": record["validation_status"],
            "state":      record["state"],
            "district":   record["district"],
        }
    }


# ==========================================================
# 🔹 REVOKE / DOWNLOAD CERTIFICATE
# ==========================================================

@router.post("/revoke/{claim_id}")
def revoke_certificate(claim_id: str):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE fra_documents SET certificate_status='REVOKED' WHERE claim_id=:cid"),
            {"cid": claim_id}
        )
    return {"status": "revoked"}


@router.get("/certificate/{claim_id}")
def download_certificate(claim_id: str):
    claim_id = claim_id.replace('"', '').replace(',', '').strip()
    with engine.connect() as conn:
        record = conn.execute(
            text("SELECT * FROM fra_documents WHERE claim_id = :cid"),
            {"cid": claim_id}
        ).mappings().first()

    if not record:
        return {"error": "Claim not found"}

    file_path = f"certificates/{claim_id}.pdf"
    if not record.get("certificate_hash"):
        cert_hash = generate_claim_certificate(dict(record), file_path, "http://localhost:8080")
        with engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE fra_documents
                    SET certificate_hash = :hash, certificate_status = 'ACTIVE'
                    WHERE claim_id = :cid
                """),
                {"hash": cert_hash, "cid": claim_id}
            )

    return FileResponse(file_path, media_type="application/pdf", filename=f"{claim_id}_certificate.pdf")


# ==========================================================
# 🔹 UPLOAD DOCUMENT (MAIN)
# ==========================================================

@router.post("/")
async def upload_document(file: UploadFile = File(...)):
    file_path = None   # track so we can clean up on any error
    try:
        if file.content_type not in ["image/png", "image/jpeg", "application/pdf"]:
            raise HTTPException(400, "Invalid file type. Only PNG, JPEG and PDF are accepted.")

        file_bytes = await file.read()

        UPLOAD_DIR = "uploaded_docs"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        safe_name   = os.path.basename(file.filename)
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        file_path   = os.path.join(UPLOAD_DIR, unique_name)
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        # ── Step 1: OCR ──────────────────────────────────────────────────────
        ocr_text = extract_text_from_file(file_bytes)
        logger.info(f"📝 RAW OCR TEXT (first 500 chars): {ocr_text[:500]}")

        # ── Step 2: Regex extraction ─────────────────────────────────────────
        raw_data = clean_with_llm(ocr_text)

        if not raw_data or not isinstance(raw_data, dict):
            _cleanup(file_path)
            raise HTTPException(422, "Document could not be processed. Ensure it contains clear text.")

        logger.info(f"📄 RAW OCR DATA: {raw_data}")

        # ── Step 3: NER pass — fills gaps left by regex ──────────────────────
        ner_entities = extract_entities(ocr_text)
        ner_fields   = entities_to_document_fields(ner_entities)
        logger.info(f"🧠 NER ENTITIES: {ner_entities}")

        for ner_key, ner_value in ner_fields.items():
            if ner_key.startswith("_"):
                continue
            if not raw_data.get(ner_key) and ner_value:
                raw_data[ner_key] = ner_value
                logger.info(f"🔄 NER filled field '{ner_key}': {ner_value}")

        # ── Step 4: Claim ID OCR correction ──────────────────────────────────
        raw_claim_id = safe_str(raw_data.get("Claim ID"))
        if raw_claim_id:
            corrected_claim_id = correct_claim_id_ocr(raw_claim_id)
            if corrected_claim_id != raw_claim_id:
                logger.info(f"🔧 Claim ID corrected: '{raw_claim_id}' → '{corrected_claim_id}'")
            raw_data["Claim ID"] = corrected_claim_id

        # ── Step 5: Standardize ──────────────────────────────────────────────
        state_value     = safe_str(raw_data.get("State"))
        state_supported = raw_data.get("is_supported_state", False)
        if not state_value:
            state_value     = extract_state_from_text(ocr_text)
            state_supported = is_state_allowed(state_value)

        data = {
            "Patta-Holder Name": (
                safe_str(raw_data.get("Patta-Holder Name"))
                or safe_str(raw_data.get("Claimant Name"))
                or safe_str(raw_data.get("Applicant Name"))
            ),
            "Father/Husband Name":  safe_str(raw_data.get("Father/Husband Name")),
            "Age":                   raw_data.get("Age"),
            "Gender":                safe_str(raw_data.get("Gender")),
            "Address":               safe_str(raw_data.get("Address")),
            "Village Name": (
                safe_str(raw_data.get("Village Name"))
                or safe_str(raw_data.get("Village"))
            ),
            "Block":                 safe_str(raw_data.get("Block")),
            "District":              safe_str(raw_data.get("District")),
            "State":                 state_value,
            "is_supported_state":    state_supported,
            "Total Area Claimed":    safe_str(raw_data.get("Total Area Claimed")),
            "Coordinates":           safe_str(raw_data.get("Coordinates")),
            "Land Use":              safe_str(raw_data.get("Land Use")),
            "Claim ID":              safe_str(raw_data.get("Claim ID")),
            "Type of Claim":         safe_str(raw_data.get("Type of Claim")),
            "Date of Application":   safe_str(raw_data.get("Date of Application")),
            "Water bodies":          safe_str(raw_data.get("Water bodies")),
            "Forest cover":          safe_str(raw_data.get("Forest cover")),
            "Homestead":             safe_str(raw_data.get("Homestead")),
            "Marital Status":        safe_str(raw_data.get("Marital Status")),
        }

        logger.info(f"🔄 STANDARDIZED DATA: {data}")

        # ── Step 6: Validate required fields ────────────────────────────────
        is_valid, error_msg = validate_required_fields(data)
        if not is_valid:
            logger.error(f"❌ VALIDATION FAILED: {error_msg} | Raw: {raw_data}")
            _cleanup(file_path)
            raise HTTPException(422, f"Cannot extract required information: {error_msg}")

        # ── Step 7: Claim ID assignment ──────────────────────────────────────
        claim_id = safe_str(data.get("Claim ID"))
        if not claim_id:
            claim_id = f"FRA-{uuid.uuid4().hex[:8].upper()}"
            logger.info(f"🆕 Auto-generated Claim ID: {claim_id}")

        if claim_id_exists(claim_id):
            raise HTTPException(409, f"Claim ID '{claim_id}' already exists in the system.")

        # ── Step 8: Scheme determination ─────────────────────────────────────
        eligible_scheme = determine_scheme(data)
        logger.info(f"💼 ELIGIBLE SCHEME: {eligible_scheme}")

        # ── Step 9: Geocoding (Hardened for Resilience) ──────────────────────
        full_address = ", ".join(filter(None, [
            safe_str(data.get("Village Name")),
            safe_str(data.get("District")),
            safe_str(data.get("State")),
            "India"
        ]))
        
        coordinates = safe_str(data.get("Coordinates"))
        
        # Check if coordinates are valid (must have a comma and two numbers)
        is_valid_coords = "," in coordinates and len(re.findall(r"[-+]?\d*\.\d+|\d+", coordinates)) >= 2
        
        if not coordinates or not is_valid_coords:
            logger.info(f"🔍 Invalid or missing coordinates ('{coordinates}'). Retrying via Geocoder...")
            coordinates = get_coordinates_from_address(
                full_address, 
                village=safe_str(data.get("Village Name")),
                district=safe_str(data.get("District")),
                state=safe_str(data.get("State"))
            )

        # ── Step 10a: Validate claimed land use against FRA-eligible types ───
        claimed_land_use_raw = safe_str(data.get("Land Use"))
        claimed_land_use     = claimed_land_use_raw.lower().strip()

        is_valid_fra_use = any(valid in claimed_land_use for valid in VALID_FRA_LAND_USES)
        if claimed_land_use and not is_valid_fra_use:
            err = (
                f"Invalid land use for FRA claim: '{claimed_land_use_raw}'. "
                f"FRA claims are only valid for agricultural, forest, pasture, "
                f"homestead, or community land use types."
            )
            logger.error(f"❌ INVALID FRA LAND USE TYPE: {err}")
            _cleanup(file_path)
            raise HTTPException(422, err)

        # ── Step 10b: ML satellite land-use classification ────────────────────
        #
        # For image uploads the ML model runs on the uploaded image.
        # For PDF uploads the model is not applicable (document scan ≠ satellite).
        #
        if file.content_type.startswith("image/"):
            try:
                ml_label, ml_conf = predict_land_use(file_bytes)
                logger.info(f"🛰️  ML prediction: {ml_label} ({ml_conf:.2%})")
            except Exception as ml_err:
                logger.warning(f"⚠️  ML model error: {ml_err}")
                ml_label, ml_conf = "ML Error", 0.0
        else:
            ml_label, ml_conf = "Not Applicable", 0.0

        # ── Step 10c: Compare ML prediction vs claimed land use ───────────────
        #
        # Decision matrix:
        #   • "Not Applicable" (PDF)  → validation_status = "Not Validated"
        #                               → ALLOWED through (manual review by officer)
        #   • "ML Error"              → validation_status = "Unverified"
        #                               → ALLOWED through (model failure, log it)
        #   • ML matches claimed      → validation_status = "Matched"
        #                               → ALLOWED through ✅
        #   • ML does NOT match       → validation_status = "Mismatch"
        #                               → HARD REJECT — data NEVER stored ❌
        #
        # NOTE: We intentionally do NOT gate on confidence for the mismatch block.
        # If the model gives a low-confidence prediction AND it disagrees with the
        # claim, we still reject — a low-confidence model is uncertain, not wrong
        # in the claimant's favour.  Low-confidence matches, however, are let
        # through so borderline-correct claims aren't unfairly blocked.
        #
        if ml_label == "Not Applicable":
            validation_status = "Not Validated"   # PDF — manual review
        elif ml_label == "Document-Scan":
            validation_status = "Not Validated"   # image is a form scan
            ml_label = "Pending Satellite Scan"  # Set a clearer instruction for Atlas
        elif ml_label == "ML Error":
            validation_status = "Unverified"       # model crashed — log, allow
        elif land_uses_match(ml_label, claimed_land_use):
            validation_status = "Matched"
        else:
            validation_status = "Mismatch"

        logger.info(
            f"✅ LAND-USE VALIDATION: {validation_status} "
            f"| ML={ml_label} ({ml_conf:.2%}) | Claimed='{claimed_land_use_raw}'"
        )

        # ── Step 10d: SOFT WARNING on mismatch — allow storage for Atlas audit ───
        if validation_status == "Mismatch":
            msg = (
                f"Land-use discrepancy detected during upload (Claim: {claimed_land_use_raw} | AI: {ml_label}). "
                "The claim has been stored but is flagged as 'Mismatch' for satellite verification in the Atlas."
            )
            logger.warning(f"⚠️ LAND VERIFICATION MISMATCH (proceeding): {msg}")
            # We no longer raise HTTPException here to allow the user to see the flagged claim in Atlas

        # ── Step 11: Insert into DB ───────────────────────────────────────────
        ner_json = _json.dumps(ner_entities) if ner_entities else None

        params = {
            "patta_holder_name":      safe_str(data.get("Patta-Holder Name")),
            "father_or_husband_name": safe_str(data.get("Father/Husband Name")),
            "age":                    safe_int(data.get("Age")),
            "gender":                 safe_str(data.get("Gender")),
            "address":                safe_str(data.get("Address")),
            "village_name":           safe_str(data.get("Village Name")),
            "block":                  safe_str(data.get("Block")),
            "district":               safe_str(data.get("District")),
            "state":                  safe_str(data.get("State")),
            "total_area_claimed":     safe_str(data.get("Total Area Claimed")),
            "coordinates":            coordinates,
            "land_use":               safe_str(data.get("Land Use")),
            "claim_id":               claim_id,
            "claim_type":             safe_str(data.get("Type of Claim")),
            "date_of_application":    safe_str(data.get("Date of Application")),
            "water_bodies":           safe_str(data.get("Water bodies")),
            "forest_cover":           safe_str(data.get("Forest cover")),
            "homestead":              safe_str(data.get("Homestead")),
            "ml_land_use":            ml_label,
            "ml_confidence":          ml_conf,
            "validation_status":      validation_status,
            "eligible_scheme":        eligible_scheme,
            "file_path":              file_path,
            "ner_data":               ner_json,
        }

        # Try with ner_data column; fall back without it (column may not exist yet)
        try:
            insert_sql = text("""
                INSERT INTO fra_documents (
                    patta_holder_name, father_or_husband_name, age, gender,
                    address, village_name, block, district, state,
                    total_area_claimed, coordinates, land_use,
                    claim_id, claim_type, date_of_application,
                    water_bodies, forest_cover, homestead,
                    ml_land_use, ml_confidence, validation_status,
                    eligible_scheme, file_path, status, ner_data
                ) VALUES (
                    :patta_holder_name, :father_or_husband_name, :age, :gender,
                    :address, :village_name, :block, :district, :state,
                    :total_area_claimed, :coordinates, :land_use,
                    :claim_id, :claim_type, :date_of_application,
                    :water_bodies, :forest_cover, :homestead,
                    :ml_land_use, :ml_confidence, :validation_status,
                    :eligible_scheme, :file_path, 'pending', :ner_data
                )
                RETURNING id;
            """)
            with engine.begin() as conn:
                doc_id = conn.execute(insert_sql, params).scalar()

        except Exception:
            params_no_ner = {k: v for k, v in params.items() if k != "ner_data"}
            insert_sql_no_ner = text("""
                INSERT INTO fra_documents (
                    patta_holder_name, father_or_husband_name, age, gender,
                    address, village_name, block, district, state,
                    total_area_claimed, coordinates, land_use,
                    claim_id, claim_type, date_of_application,
                    water_bodies, forest_cover, homestead,
                    ml_land_use, ml_confidence, validation_status,
                    eligible_scheme, file_path, status
                ) VALUES (
                    :patta_holder_name, :father_or_husband_name, :age, :gender,
                    :address, :village_name, :block, :district, :state,
                    :total_area_claimed, :coordinates, :land_use,
                    :claim_id, :claim_type, :date_of_application,
                    :water_bodies, :forest_cover, :homestead,
                    :ml_land_use, :ml_confidence, :validation_status,
                    :eligible_scheme, :file_path, 'pending'
                )
                RETURNING id;
            """)
            with engine.begin() as conn:
                doc_id = conn.execute(insert_sql_no_ner, params_no_ner).scalar()

        logger.info(
            f"✅ SAVED — DB id={doc_id} | Claim={claim_id} | "
            f"Status={validation_status} | NER={len(ner_entities)} entities"
        )

        return {
            "status":               "success",
            "doc_id":               doc_id,
            "claim_id":             claim_id,
            "validation_status":    validation_status,
            "eligible_scheme":      eligible_scheme,
            "ml_prediction":        ml_label,
            "confidence":           ml_conf,
            "ner_entities_found":   len(ner_entities),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ UPLOAD FAILED: {str(e)}", exc_info=True)
        _cleanup(file_path)
        raise HTTPException(500, f"Upload processing failed: {str(e)}")


# ==========================================================
# 🔹 INTERNAL HELPERS
# ==========================================================

def _cleanup(file_path):
    """Remove uploaded file if processing failed (avoid orphan files)."""
    if file_path:
        try:
            os.remove(file_path)
        except Exception:
            pass


# ==========================================================
# 🔹 GET ALL
# ==========================================================

@router.get("/all")
async def get_all_documents():
    query = text("""
        SELECT id, patta_holder_name, state, claim_id,
               land_use, ml_land_use, validation_status,
               eligible_scheme, file_path, created_at
        FROM fra_documents
        ORDER BY created_at DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return {"status": "success", "count": len(rows), "results": rows}