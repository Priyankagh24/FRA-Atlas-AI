"""
ner_utils.py  —  Named Entity Recognition for FRA documents
============================================================
Extracts structured entities from raw OCR text using:
  1. Rule-based regex patterns (fast, no dependencies)
  2. spaCy NER (if installed) as a secondary pass for person/place names

Entities extracted:
  - PERSON         : Patta-holder name, father/husband name
  - VILLAGE        : Village / gram sabha name
  - DISTRICT       : District name
  - STATE          : State name
  - COORDINATES    : Lat/Lon pairs
  - AREA           : Land area with unit
  - CLAIM_ID       : FRA claim reference number
  - DATE           : Application date
  - CLAIM_TYPE     : IFR / CFR / CR
  - LAND_USE       : Agriculture / Homestead / Forest / Water
"""

import re
from typing import Dict, List, Any

# ─── Constants ────────────────────────────────────────────────────────────────

INDIAN_STATES_NER = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
}

LAND_USE_KEYWORDS = {
    "forest": "Forest",
    "forest produce": "Forest",
    "minor forest produce": "Forest",
    "agriculture": "Agriculture",
    "agricultural": "Agriculture",
    "annual crop": "Agriculture",
    "cultivation": "Agriculture",
    "homestead": "Homestead",
    "residential": "Homestead",
    "house": "Homestead",
    "water": "Water Body",
    "river": "Water Body",
    "pond": "Water Body",
    "lake": "Water Body",
    "pasture": "Pasture",
    "grazing": "Pasture",
}

CLAIM_TYPE_KEYWORDS = {
    "individual forest right": "IFR",
    "ifr": "IFR",
    "community forest resource": "CFR",
    "cfr": "CFR",
    "community right": "CR",
    "cr": "CR",
    "individual": "IFR",
    "community": "CFR",
}

# ─── Core extractor ───────────────────────────────────────────────────────────

def extract_entities(ocr_text: str) -> Dict[str, Any]:
    """
    Main entry point.
    Returns a dict of extracted entities with confidence scores.
    """
    text = ocr_text.strip()
    entities: Dict[str, Any] = {}

    entities["PERSON"]       = _extract_person(text)
    entities["VILLAGE"]      = _extract_field(text, r"(?:Village(?:\s+Name)?|Gram\s+Sabha)\s*[:\-]\s*([^\n]+)")
    entities["DISTRICT"]     = _extract_field(text, r"District\s*[:\-]\s*([^\n]+)")
    entities["STATE"]        = _extract_state(text)
    entities["COORDINATES"]  = _extract_coordinates(text)
    entities["AREA"]         = _extract_area(text)
    entities["CLAIM_ID"]     = _extract_field(text, r"Claim\s*(?:ID|No\.?|Number)\s*[:\-]\s*([^\n]+)")
    entities["DATE"]         = _extract_date(text)
    entities["CLAIM_TYPE"]   = _extract_claim_type(text)
    entities["LAND_USE"]     = _extract_land_use(text)
    entities["FATHER_NAME"]  = _extract_field(text, r"(?:Father|Husband)[/\s]?(?:Name)?\s*[:\-]\s*([^\n]+)")

    # Remove None / empty
    entities = {k: v for k, v in entities.items() if v}

    return entities


def entities_to_document_fields(entities: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert NER entity dict → upload_router data dict keys.
    Merges with existing regex extraction for maximum coverage.
    """
    person_list = entities.get("PERSON", [])
    fields = {
        "Patta-Holder Name":   person_list[0]["text"] if person_list else "",
        "Father/Husband Name": (entities.get("FATHER_NAME") or {}).get("text", ""),
        "Village Name":        (entities.get("VILLAGE") or {}).get("text", ""),
        "District":            (entities.get("DISTRICT") or {}).get("text", ""),
        "State":               (entities.get("STATE") or {}).get("text", ""),
        "Coordinates":         (entities.get("COORDINATES") or {}).get("text", ""),
        "Total Area Claimed":  (entities.get("AREA") or {}).get("text", ""),
        "Claim ID":            (entities.get("CLAIM_ID") or {}).get("text", ""),
        "Date of Application": (entities.get("DATE") or {}).get("text", ""),
        "Type of Claim":       (entities.get("CLAIM_TYPE") or {}).get("text", ""),
        "Land Use":            (entities.get("LAND_USE") or {}).get("text", ""),
        "_ner_entities":       entities,   # attach raw entities for audit trail
    }
    return {k: v for k, v in fields.items() if v}


# ─── Private helpers ──────────────────────────────────────────────────────────

def _extract_field(text: str, pattern: str) -> Dict[str, Any] | None:
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    value = m.group(1).strip()
    # Strip trailing pipe artifacts common in OCR
    value = re.sub(r"\s*\|\s*$", "", value).strip()
    if not value or len(value) < 2:
        return None
    return {"text": value, "confidence": 0.85, "source": "regex"}


def _extract_person(text: str) -> List[Dict[str, Any]]:
    """
    Extract person names. Priority:
      1. Explicit Patta-Holder Name / Claimant Name label
      2. spaCy PERSON entities (if available)
    """
    persons = []

    # Labelled name
    patterns = [
        r"(?:Patta[- ]Holder\s+Name|Claimant\s+Name|Applicant\s+Name)\s*[:\-]\s*([^\n]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            name = re.sub(r"\s*\|\s*$", "", name).strip()
            # Reject if it bleeds into next field
            if name and len(name) >= 2 and not re.search(
                r"(father|husband|s/o|w/o|d/o|age|gender|village|district|state)",
                name, re.IGNORECASE
            ):
                persons.append({"text": name, "confidence": 0.90, "source": "labeled_field"})
                break

    # spaCy fallback
    if not persons:
        try:
            import spacy
            nlp = spacy.load("en_core_web_sm")
            doc = nlp(text[:2000])  # limit for speed
            for ent in doc.ents:
                if ent.label_ == "PERSON" and len(ent.text.split()) >= 2:
                    persons.append({
                        "text": ent.text.strip(),
                        "confidence": 0.70,
                        "source": "spacy"
                    })
            # Deduplicate
            seen = set()
            unique = []
            for p in persons:
                key = p["text"].lower()
                if key not in seen:
                    seen.add(key)
                    unique.append(p)
            persons = unique[:3]  # top 3 candidates
        except Exception:
            pass  # spaCy not installed — regex-only mode

    return persons


def _extract_state(text: str) -> Dict[str, Any] | None:
    """Extract state — first try labelled field, then scan entire text."""
    labelled = _extract_field(text, r"State\s*[:\-]\s*([^\n]+)")
    if labelled:
        state_val = labelled["text"].lower().strip()
        # Normalise multi-word OCR artefacts
        for known in INDIAN_STATES_NER:
            if known in state_val or state_val in known:
                return {"text": known.title(), "confidence": 0.92, "source": "regex_labeled"}

    # Scan entire text for state names
    text_lower = text.lower()
    for state in sorted(INDIAN_STATES_NER, key=len, reverse=True):  # longest first
        if re.search(r"\b" + re.escape(state) + r"\b", text_lower):
            return {"text": state.title(), "confidence": 0.75, "source": "fulltext_scan"}

    return None


def _extract_coordinates(text: str) -> Dict[str, Any] | None:
    """Extract lat/lon pairs in various formats."""
    patterns = [
        r"Coordinates?\s*[:\-]\s*([-\d.]+\s*,\s*[-\d.]+)",
        r"Lat(?:itude)?\s*[:\-]\s*([-\d.]+)[,\s]+Lon(?:gitude)?\s*[:\-]\s*([-\d.]+)",
        r"\b((?:1[0-3]|[1-9])\d\.\d{4,})\s*[,\s]\s*((?:[6-9]\d|[1-7]\d)\.\d{4,})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            coord_str = m.group(1) if "," in (m.group(1) or "") else f"{m.group(1)}, {m.group(2)}"
            return {"text": coord_str.strip(), "confidence": 0.95, "source": "regex"}
    return None


def _extract_area(text: str) -> Dict[str, Any] | None:
    """Extract land area with unit."""
    m = re.search(
        r"(?:Total\s+Area\s+Claimed|Area\s+Claimed|Land\s+Area)\s*[:\-]\s*([\d.]+\s*(?:hectares?|acres?|ha|sq\.?\s*m|bigha))",
        text, re.IGNORECASE
    )
    if m:
        return {"text": m.group(1).strip(), "confidence": 0.90, "source": "regex"}
    # Bare number + unit anywhere
    m2 = re.search(r"\b([\d.]+\s*(?:hectares?|acres?|ha|bigha))\b", text, re.IGNORECASE)
    if m2:
        return {"text": m2.group(1).strip(), "confidence": 0.65, "source": "regex_bare"}
    return None


def _extract_date(text: str) -> Dict[str, Any] | None:
    patterns = [
        r"(?:Date\s+of\s+Application|Application\s+Date)\s*[:\-]\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
        r"(?:Date\s+of\s+Application|Application\s+Date)\s*[:\-]\s*(\d{1,2}\s+\w+\s+\d{4})",
        r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return {"text": m.group(1).strip(), "confidence": 0.88, "source": "regex"}
    return None


def _extract_claim_type(text: str) -> Dict[str, Any] | None:
    text_lower = text.lower()
    for keyword, ctype in CLAIM_TYPE_KEYWORDS.items():
        if re.search(r"\b" + re.escape(keyword) + r"\b", text_lower):
            return {"text": ctype, "confidence": 0.80, "source": "keyword"}
    return None


def _extract_land_use(text: str) -> Dict[str, Any] | None:
    """Extract land use — prefer labelled field, fallback to keyword scan."""
    labelled = _extract_field(text, r"Land\s+Use\s*[:\-]\s*([^\n]+)")
    if labelled and not re.search(r"type\s+of\s+claim", labelled["text"], re.IGNORECASE):
        # Normalise to canonical category
        val = labelled["text"].lower()
        for kw, canonical in LAND_USE_KEYWORDS.items():
            if kw in val:
                return {"text": canonical, "confidence": 0.90, "source": "regex_labeled"}
        return labelled

    # Keyword scan
    text_lower = text.lower()
    for kw, canonical in LAND_USE_KEYWORDS.items():
        if kw in text_lower:
            return {"text": canonical, "confidence": 0.65, "source": "keyword_scan"}

    return None