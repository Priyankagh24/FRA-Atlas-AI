import json
import re
import os
import requests
from dotenv import load_dotenv
from typing import Dict, Any
from db import fetch_schemes

load_dotenv()

# -------------------------
# LIMITED STATES (PROJECT SCOPE)
# -------------------------
INDIAN_STATES = {
    "madhya pradesh",
    "tripura",
    "odisha",
    "telangana"
}

# -------------------------
# UNIT CONVERSION
# -------------------------
UNIT_TO_ACRE = {
    "acre": 1.0, "acres": 1.0,
    "hectare": 2.47105, "hectares": 2.47105, "ha": 2.47105,
    "sq m": 0.000247105, "sqm": 0.000247105,
    "square meter": 0.000247105, "square meters": 0.000247105,
    "sq ft": 2.2957e-5, "sqft": 2.2957e-5, "square feet": 2.2957e-5,
    "bigha": 0.619, "cent": 0.0247, "guntha": 0.0247
}

# -------------------------
# SCHEME KEYWORDS
# -------------------------
SCHEME_KEYWORDS = {
    "pm-kisan": "PM-KISAN",
    "kisan": "PM-KISAN",
    "farmer": "PM-KISAN",

    "old age": "Indira Gandhi Old Age Pension",
    "senior citizen": "Indira Gandhi Old Age Pension",

    "widow": "Widow Pension Scheme",

    "mgnrega": "MGNREGA",
    "employment": "MGNREGA",

    "forest produce": "Forest Produce Livelihood Scheme",

    "housing": "Housing Support Scheme",
    "house": "Housing Support Scheme",

    "pds": "Public Distribution System",
    "ration": "Public Distribution System"
}

# -------------------------
# JSON CLEANING
# -------------------------
def clean_llm_output(raw_text: str) -> str:
    first = raw_text.find("{")
    last = raw_text.rfind("}")
    if first == -1 or last == -1:
        return raw_text

    raw_text = raw_text[first:last+1]
    raw_text = raw_text.replace("\u201c", '"').replace("\u201d", '"')
    raw_text = raw_text.replace("\u2018", "'").replace("\u2019", "'")
    raw_text = raw_text.replace("'", '"')
    raw_text = re.sub(r',\s*([}\]])', r'\1', raw_text)

    return raw_text


def safe_json_parse(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        cleaned = clean_llm_output(text)
        try:
            return json.loads(cleaned)
        except Exception:
            return {"raw_text": text, "error": "JSON parse failed"}


# -------------------------
# REGEX EXTRACTION
# -------------------------
def fallback_extract(data: dict, text: str) -> dict:
    # ⚠️  Use [^\n]+ instead of .+ so each field only captures up to end of that line,
    # preventing OCR bleed-over across lines (e.g. name bleeding into father/husband line).
    patterns = {
        # Patta-Holder Name: must NOT match lines that only contain Father/Husband label
        "Patta-Holder Name":   r"(?:Claimant Name|Patta[- ]Holder Name|Applicant Name)\s*[:\-]\s*([^\n]+)",
        "Father/Husband Name": r"(?:Father|Husband)[/\s]?(?:Name)?\s*[:\-]\s*([^\n]+)",
        "Age":                 r"Age\s*[:\-]\s*(\d+)",
        "Gender":              r"Gender\s*[:\-]\s*(Male|Female|Other)",
        "Village Name":        r"Village(?:\s+Name)?\s*[:\-]\s*([^\n]+)",
        "Block":               r"Block\s*[:\-]\s*([^\n]+)",
        "District":            r"District\s*[:\-]\s*([^\n]+)",
        "State":               r"State\s*[:\-]\s*([^\n]+)",
        "Total Area Claimed":  r"Total Area Claimed\s*[:\-]\s*([\d\.]+\s*\w+)",
        "Land Use":            r"Land Use\s*[:\-]\s*([^\n]+)",
        "Type of Claim":       r"Type of Claim\s*[:\-]\s*([^\n]+)",
        "Claim ID":            r"Claim ID\s*[:\-]\s*([^\n]+)",
        "Coordinates":         r"Coordinates\s*[:\-]\s*([\d\.\-]+\s*,\s*[\d\.\-]+)",
    }

    for field, pattern in patterns.items():
        if not data.get(field):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted = match.group(match.lastindex).strip()
                # 🛡️ Extra guard: if extracted value is blank or just punctuation, skip it
                if extracted and len(extracted) >= 2 and not re.match(r"^[\s\-:_|]+$", extracted):
                    data[field] = extracted

    # 🛡️ Post-extraction guard: if Patta-Holder Name looks like a relative's name label,
    # it means OCR couldn't find the actual holder name — clear it so validation rejects doc.
    patta = data.get("Patta-Holder Name", "")
    if patta and re.search(r"(father|husband|s/o|w/o|d/o)", patta, re.IGNORECASE):
        data["Patta-Holder Name"] = ""

    return data


# -------------------------
# AREA CONVERSION
# -------------------------
def convert_area_to_acres(area_str: str) -> str:
    if not area_str:
        return ""

    match = re.search(r"([\d\.]+)\s*([a-zA-Z ]+)?", area_str)
    if not match:
        return area_str

    value = float(match.group(1))
    unit = (match.group(2) or "acre").strip().lower()

    for key, factor in UNIT_TO_ACRE.items():
        if key in unit:
            return f"{value * factor:.2f} acres"

    return f"{value:.2f} acres"


# -------------------------
# COORDINATES
# -------------------------
def is_valid_coordinates(coords: str) -> bool:
    if not coords:
        return False
    return bool(re.match(r"^-?\d+\.?\d*,\s*-?\d+\.?\d*$", coords.strip()))


def fetch_coordinates_from_address(address: str) -> str:
    if not address.strip():
        return ""

    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": "FRA-System/1.0"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()
        if data:
            return f"{data[0]['lat']}, {data[0]['lon']}"
    except Exception as e:
        print("Geocoding error:", e)

    return ""


def clean_claim_id(claim_id: str) -> str:
    """
    Clean and standardize extracted Claim ID.
    Fixes common OCR misreads.
    """
    if not claim_id:
        return ""
    
    claim_id = claim_id.upper().strip()
    
    claim_id = claim_id.replace('@', '0')
    # Remove extra spaces
    claim_id = re.sub(r'\s+', '', claim_id)
    
    # Fix common OCR misreads: O→0, l→1, I→1, S→5
    claim_id = claim_id.replace('O', '0')  # Letter O to Zero
    claim_id = claim_id.replace('l', '1')  # Letter l to 1
    claim_id = claim_id.replace('I', '1')  # Letter I to 1
    claim_id = claim_id.replace('S', '5')  # Letter S to 5
    
    return claim_id


# ── Coordinates validation ──────────────────────────────────────────────────

def is_valid_coordinates(coords: str) -> bool:
    """
    Check if coordinates are in valid format: lat, lng
    
    Examples:
    "22.9734, 78.6569"  → True
    "20.95, 85.10"      → True
    "-12.34, 56.78"     → True
    "invalid"           → False
    ""                  → False
    "22.9734"           → False (missing longitude)
    """
    if not coords:
        return False
    return bool(re.match(r"^-?\d+\.?\d*,\s*-?\d+\.?\d*$", coords.strip()))

def correct_ocr_digits(text: str) -> str:
    """
    Correct common OCR digit misreads.
    This is CRITICAL for Claim IDs and numeric fields.
    
    Common OCR confusions:
    - 0 (zero) misread as O (letter O)
    - 1 (one) misread as l (lowercase L) or I (capital I)
    - 2 (two) misread as Z
    - 5 (five) misread as S
    - 8 (eight) misread as B
    - 9 (nine) misread as g or q
    - 4 (four) misread as A
    - 6 (six) misread as G or b
    - 3 (three) misread as E
    """
    if not text:
        return ""
    
    # Context-aware replacements (only in numeric positions)
    result = text
    
    result = result.replace('@', '0')  # 🔥 CRITICAL FIX
    
    # Fix O→0 in claim ID patterns (FRA-XX-YYYY-NNN)
    # Look for patterns like FRA-TR-2024-004 where O appears where digits should be
    result = re.sub(r'FRA-([A-Z]{2})-(\d{4})-([A-Z0-9]+)', 
                    lambda m: f"FRA-{m.group(1)}-{m.group(2)}-{m.group(3).replace('O', '0').replace('o', '0')}", 
                    result, flags=re.IGNORECASE)
    
    # Fix year section: 2O24 → 2024, 2O2O → 2020, etc
    result = re.sub(r'([0-9])[OoIl]([0-9])', r'\g<1>0\2', result)
    result = re.sub(r'([0-9])[IlL]([0-9])', r'\g<1>1\2', result)
    
    # Fix at end of numbers: O, o, l, I → appropriate digit
    result = re.sub(r'([0-9])[Oo]$', r'\g<1>0', result)
    result = re.sub(r'([0-9])[IlL]$', r'\g<1>1', result)
    
    # Fix in sequences of digits with letter substitutions
    # 90O4 → 9004, OO4 → 004
    result = re.sub(r'([0-9])[Oo]([0-9])', r'\g<1>0\2', result)
    result = re.sub(r'([0-9])[IlL]([0-9])', r'\g<1>1\2', result)
    
    # Fix S→5 in numeric context
    result = re.sub(r'([0-9])[Ss]([0-9])', r'\g<1>5\2', result)
    result = re.sub(r'([0-9])[Ss]$', r'\g<1>5', result)
    
    # Fix Z→2
    result = re.sub(r'([0-9])[Zz]([0-9])', r'\g<1>2\2', result)
    result = re.sub(r'([0-9])[Zz]$', r'\g<1>2', result)
    
    # Fix B→8
    result = re.sub(r'([0-9])[Bb]([0-9])', r'\g<1>8\2', result)
    result = re.sub(r'([0-9])[Bb]$', r'\g<1>8', result)
    
    return result.strip()


def validate_claim_id_format(claim_id: str) -> tuple:
    """
    Validate Claim ID format.
    Accepts formats: 
    - FRA-XX-YYYY (e.g., FRA-OD-2001)
    - FRA-XX-YYYY-NNN (e.g., FRA-TR-2024-004)
    
    Returns (is_valid, error_message, corrected_id)
    """
    if not claim_id:
        return True, "", ""  # Empty is OK, will be auto-generated
    
    claim_id = safe_str(claim_id).upper()
    
    # First, apply OCR correction
    corrected = correct_ocr_digits(claim_id)
    
    # Accept both formats:
    # FRA-[2 letters]-[4 digits] or FRA-[2 letters]-[4 digits]-[3+ digits]
    pattern = r"^FRA-[A-Z]{2}-\d{4}(?:-\d{3,})?$"
    
    if not re.match(pattern, corrected):
        return False, (
            f"Invalid Claim ID format: '{claim_id}'. "
            f"Expected format: FRA-XX-YYYY (e.g., FRA-OD-2001) or FRA-XX-YYYY-NNN (e.g., FRA-TR-2024-004). "
            f"Original: {claim_id}"
        ), ""
    
    return True, "", corrected


def safe_str(value):
    """Safely convert any value to string, returns empty string if None"""
    if value is None:
        return ""
    return str(value).strip()

# -------------------------
# MAIN OCR CLEANING
# -------------------------
def clean_with_llm(text: str) -> dict:
    data = {}

    # 1. Extract
    data = fallback_extract(data, text)

    # 2. Clean fields
    for key in ["Village Name", "District", "State"]:
        if data.get(key):
            data[key] = data[key].replace("Name:", "").strip()

    # 3. Land Use normalization
    lu = (data.get("Land Use") or "").lower()
    if any(k in lu for k in ["house", "home", "residential", "hut", "dwelling", "homestead", "basti"]):
        data["Land Use"] = "Homestead"
    elif any(k in lu for k in ["forest", "van", "jungle", "mfp", "ntfp"]):
        data["Land Use"] = "Forest"
    elif any(k in lu for k in ["agri", "crop", "farm", "kheti", "cultivation", "paddy"]):
        data["Land Use"] = "Agriculture"
    elif any(k in lu for k in ["water", "river", "nadi", "pond", "talab", "lake"]):
        data["Land Use"] = "Water Body"
    elif any(k in lu for k in ["pasture", "grazing", "grass", "charai"]):
        data["Land Use"] = "Pasture"

    # 4. Area normalize
    if data.get("Total Area Claimed"):
        data["Total Area Claimed"] = convert_area_to_acres(data["Total Area Claimed"])

    # 5. OCR VALIDATION (IMPORTANT)
    name = (data.get("Patta-Holder Name") or "").strip()
    if not name or len(name) < 2 or name.isnumeric():
        data["Patta-Holder Name"] = ""

    # 5b. Fix Land Use field: if it contains "Type of Claim" it was misextracted
    #     e.g. OCR set Land Use = "Type of Claim: Individual" — move it to the right field
    land_use_val = (data.get("Land Use") or "").strip()
    if re.search(r"type\s+of\s+claim", land_use_val, re.IGNORECASE):
        # Extract real claim type from the bleed-over value
        claim_match = re.search(r"type\s+of\s+claim\s*[:\-]?\s*([^\n]+)", land_use_val, re.IGNORECASE)
        if claim_match and not data.get("Type of Claim"):
            data["Type of Claim"] = claim_match.group(1).strip()
        data["Land Use"] = ""  # clear the corrupted land use

    # 5c. Clean trailing garbage from text fields (OCR artifacts: |, newlines, labels)
    for field in ["District", "State", "Village Name", "Block"]:
        val = (data.get(field) or "").strip()
        # Remove trailing pipe char (common OCR artifact for blank field)
        val = re.sub(r"\s*\|\s*$", "", val).strip()
        # If only non-alpha characters remain, clear it
        if val and not re.search(r"[a-zA-Z]", val):
            val = ""
        data[field] = val

    # 6. State support flag
    state_value = (data.get("State") or "").strip()
    data["is_supported_state"] = bool(state_value and state_value.lower() in INDIAN_STATES)

    # 7. Coordinates
    coords = (data.get("Coordinates") or "").strip()
    if not is_valid_coordinates(coords):
        address = ", ".join(filter(None, [
            data.get("Village Name"),
            data.get("District"),
            data.get("State"),
            "India"
        ]))

        new_coords = fetch_coordinates_from_address(address)

        if not new_coords:
            new_coords = fetch_coordinates_from_address(
                f"{data.get('District')}, {data.get('State')}, India"
            )

        data["Coordinates"] = new_coords or ""

    return data


# -------------------------
# DSS QUERY PARSER
# -------------------------
def parse_dss_query(user_query: str) -> Dict[str, Any]:
    """
    Parse DSS query with improved robustness for:
    - Case insensitivity
    - Extra spaces
    - Spelling variations
    - Multiple location formats
    """
    result = {
        "scheme": None,
        "village": None,
        "district": None,
        "state": None
    }

    # Normalize query: lowercase, remove extra spaces, handle common typos
    q = " ".join(user_query.lower().split())

    # Handle common OCR/spelling mistakes
    q = q.replace("eligble", "eligible")
    q = q.replace("odisa", "odisha")
    q = q.replace("mandla", "mandla")  # Keep as district

    # 1. Scheme detection (expanded keywords)
    scheme_mappings = {
        # MGNREGA variations
        "mgnrega": "MGNREGA",
        "employment": "MGNREGA",
        "labour": "MGNREGA",
        "work": "MGNREGA",

        # Pension variations
        "old age": "Indira Gandhi Old Age Pension",
        "senior citizen": "Indira Gandhi Old Age Pension",
        "pension": "Indira Gandhi Old Age Pension",
        "indira gandhi": "Indira Gandhi Old Age Pension",

        # Widow variations
        "widow": "Widow Pension Scheme",

        # Forest variations
        "forest produce": "Forest Produce Livelihood Scheme",
        "mfp": "Forest Produce Livelihood Scheme",
        "minor forest": "Forest Produce Livelihood Scheme",

        # PM-KISAN variations
        "pm-kisan": "PM-KISAN",
        "kisan": "PM-KISAN",
        "farmer": "PM-KISAN",

        # Farm Support Scheme variations
        "farm": "Farm Support Scheme",
        "agriculture": "Farm Support Scheme",

        # Housing variations
        "housing": "Housing Support Scheme",
        "house": "Housing Support Scheme",
        "homestead": "Housing Support Scheme",

        # PDS variations
        "pds": "Public Distribution System",
        "ration": "Public Distribution System"
    }

    for keyword, scheme_name in scheme_mappings.items():
        if keyword in q:
            result["scheme"] = scheme_name
            break

    # 2. Location detection (improved regex)
    # Match patterns like: "in Odisha", "from Koraput", "in Koraput, Odisha"
    location_patterns = [
        r"\bin\s+([A-Za-z][A-Za-z ,]+?)(?:\?|$|\s+(?:eligible|for|show|claims?|beneficiaries?|people))",
        r"\bfrom\s+([A-Za-z][A-Za-z ,]+?)(?:\?|$|\s+(?:eligible|for|show|claims?|beneficiaries?|people))",
        r"\b(?:district|state)\s+(?:of\s+)?([A-Za-z][A-Za-z ,]+?)(?:\?|$|\s+(?:eligible|for|show|claims?|beneficiaries?|people))"
    ]

    location = None
    for pattern in location_patterns:
        match = re.search(pattern, user_query, re.IGNORECASE)
        if match:
            location = match.group(1).strip().rstrip(",")
            break

    if location:
        # Ignore scheme names appearing as a fake location like "in pm kisan"
        location_lower = location.lower().strip()
        if any(keyword in location_lower for keyword in scheme_mappings.keys()) or any(scheme_name.lower() in location_lower for scheme_name in scheme_mappings.values()):
            location = None

    if location:
        # Split by comma and clean
        parts = [p.strip() for p in location.split(",") if p.strip()]

        # Check each part against supported states
        for part in parts:
            if part.lower() in INDIAN_STATES:
                result["state"] = part
                # Remove state from parts, remaining is district/village
                parts.remove(part)
                break

        # Remaining parts: prefer district over village
        for part in parts:
            if not result["district"]:
                result["district"] = part
            elif not result["village"]:
                result["village"] = part

        # If only one location and not a state, assume it's district
        if len(parts) == 1 and not result["state"]:
            result["district"] = parts[0]

    # 3. DB fallback for scheme names
    if not result["scheme"]:
        try:
            schemes = fetch_schemes()
            for s in schemes:
                if s["name"].lower() in q:
                    result["scheme"] = s["name"]
                    break
        except Exception as e:
            print("DB error:", e)

    return result