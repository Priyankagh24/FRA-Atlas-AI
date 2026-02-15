import json
import re
import os
import requests
from dotenv import load_dotenv
# from langchain_google_genai import ChatGoogleGenerativeAI

from db import fetch_schemes
from typing import Dict, Any
from datetime import datetime

chain = None
dss_chain = None
INDIAN_STATES = {
    "jharkhand",
    "odisha",
    "chhattisgarh"
}


# -------------------------
# Load API Keys
# -------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# llm = None
# if GEMINI_API_KEY:
#     try:
#         llm = ChatGoogleGenerativeAI(
#             model="gemini-2.5-flash",
#             temperature=0,
#             google_api_key=GEMINI_API_KEY
#         )
#         print("✅ Gemini LLM initialized")
#     except Exception as e:
#         print("⚠️ LLM init failed:", e)


# -------------------------
# Conversion factors to acres
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
# Prompt Template (OCR → JSON Schema)
# -------------------------
# SCHEMA_PROMPT = """
# You are an assistant that extracts structured data from OCR text.

# Rules:
# 1. Extract only values present in text.
# 2. No guessing.
# 3. Fix spelling mistakes.
# 4. Missing fields = "".
# 5. Return valid JSON only.

# JSON Format:
# {{
#     "Patta-Holder Name": "",
#     "Father/Husband Name": "",
#     "Age": "",
#     "Gender": "",
#     "Address": "",
#     "Village Name": "",
#     "Block": "",
#     "District": "",
#     "State": "",
#     "Total Area Claimed": "",
#     "Coordinates": "",
#     "Land Use": "",
#     "Claim ID": "",
#     "Date of Application": "",
#     "Water bodies": "",
#     "Forest cover": "",
#     "Homestead": ""
# }}

# OCR Text:
# {ocr_text}
# """
# prompt = PromptTemplate.from_template(SCHEMA_PROMPT)
# chain = prompt | llm if llm else None
# -------------------------
# Prompt Template (DISABLED)
# -------------------------
SCHEMA_PROMPT = None
chain = None


# -------------------------
# JSON Cleaning
# -------------------------
def clean_llm_output(raw_text: str) -> str:
    first = raw_text.find("{")
    last = raw_text.rfind("}")
    if first == -1 or last == -1:
        return raw_text
    raw_text = raw_text[first:last+1]
    raw_text = raw_text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
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
            return {"raw_text": text, "error": "LLM JSON parse failed"}

# -------------------------
# Regex Fallback
# -------------------------
def fallback_extract(data: dict, text: str) -> dict:
    patterns = {
        "Patta-Holder Name": r"(Claimant Name|Patta[- ]Holder Name)[:\-]?\s*(.+)",
        "Father/Husband Name": r"(Father|Husband)[/ ]?Name[:\-]?\s*(.+)",
        "Age": r"Age[:\-]?\s*(\d+)",
        "Gender": r"Gender[:\-]?\s*(Male|Female|Other)",
        "Village Name": r"Village[:\-]?\s*(.+)",
        "Block": r"Block[:\-]?\s*(.+)",
        "District": r"District[:\-]?\s*(.+)",
        "State": r"State[:\-]?\s*(.+)",
        "Total Area Claimed": r"Total Area Claimed[:\-]?\s*([\d\.]+\s*\w+)",
        "Coordinates": r"Coordinates[:\-]?\s*([\d\.\,\s]+)",
        "Land Use": r"Land Use[:\-]?\s*(.+)",
        "Claim ID": r"Claim ID[:\-]?\s*(.+)",
        "Date of Application": r"Date of Application[:\-]?\s*(.+)",
        "Type of Claim": r"Type of Claim[:\-]?\s*(.+)",
        "Declaration": r"Declaration[:\-]?\s*(.+)"
    }

    for field, pattern in patterns.items():
        if not data.get(field):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data[field] = match.group(len(match.groups())).strip()

    return data



# -------------------------
# Area Conversion
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
            acres = value * factor
            return f"{acres:.2f} acres"
    return f"{value:.2f} acres"

# -------------------------
# Coordinate Helpers
# -------------------------
def is_valid_coordinates(coords: str) -> bool:
    if not coords:
        return False
    return bool(re.match(r"^-?\d+\.\d+,\s*-?\d+\.\d+$", coords))

def fetch_coordinates_from_address(address: str) -> str:
    if not address.strip():
        return ""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": "FRA-System/1.0"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        print("🔍 Geocoding request:", resp.url)
        data = resp.json()
        print("📍 Geocoding response:", data)
        if data:
            return f"{data[0]['lat']}, {data[0]['lon']}"
    except Exception as e:
        print("Geocoding error:", e)
    return ""

# -------------------------
# Main Cleaning
# -------------------------
def clean_with_llm(text: str) -> dict:
    data = {}

    # 1️⃣ Regex extraction
    data = fallback_extract(data, text)
        # 2️⃣ Normalize location fields
    for key in ["Village Name", "District", "State"]:
        if data.get(key):
            data[key] = data[key].replace("Name:", "").strip()

    if data.get("Land Use"):
        # 🔒 FORCE Land Use normalization
   
    # 🔒 FORCE Land Use normalization
    lu = (data.get("Land Use") or "").lower()

    if any(k in lu for k in ["house", "home", "residential", "hut", "dwelling", "homestead"]):
      data["Land Use"] = "Homestead"





    elif "homestead" in lu:
        data["Land Use"] = "Homestead"


    # 3️⃣ Area normalization
    if data.get("Total Area Claimed"):
        data["Total Area Claimed"] = convert_area_to_acres(
            data["Total Area Claimed"]
        )

    # 4️⃣ FORCE coordinates
    coords = data.get("Coordinates", "").strip()
    if not is_valid_coordinates(coords):
        full_address = ", ".join(
            filter(None, [
                data.get("Village Name"),
                data.get("District"),
                data.get("State"),
                "India"
            ])
        )

        new_coords = fetch_coordinates_from_address(full_address)

        if not new_coords:
            new_coords = fetch_coordinates_from_address(
                f"{data.get('District')}, {data.get('State')}, India"
            )

        data["Coordinates"] = new_coords or ""

    return data



# -------------------------
# DSS Query Parsing
# -------------------------
# DSS_PROMPT = """
# You are an assistant that extracts structured filters from a natural language question
# about government scheme eligibility.

# Rules:
# 1. Extract scheme, village, district, state (if available).
# 2. If any field is missing, return null.
# 3. Output ONLY valid JSON. No explanation, no markdown.

# Example:
# Question: Who is eligible for Farm Support Scheme in Bhimganga?
# Answer:
# {
#   "scheme": "Farm Support Scheme",
#   "village": "Bhimganga",
#   "district": null,
#   "state": null
# }

# Question: List all people in Mandla eligible for Old Age Pension.
# Answer:
# {
#   "scheme": "Old Age Pension",
#   "village": "Mandla",
#   "district": null,
#   "state": null
# }
# """


# dss_prompt = PromptTemplate.from_template(DSS_PROMPT)
# dss_chain: Runnable | None = dss_prompt | llm | StrOutputParser() if llm else None

DSS_PROMPT = None
dss_chain = None

# -------------------------
# DSS Scheme Keywords
# -------------------------
SCHEME_KEYWORDS = {
    "minor forest produce": "Minor Forest Produce Scheme",
    "mfp": "Minor Forest Produce Scheme",
    "housing": "Housing Support Scheme",
    "indlu": "Housing Support Scheme",
    "house": "Housing Support Scheme",
    "farm support": "Farm Support Scheme",
    "agriculture support": "Farm Support Scheme",
    "pds": "Public Distribution System",
    "ration": "Public Distribution System",
}

def parse_dss_query(user_query: str) -> Dict[str, Any]:
    result = {
        "scheme": None,
        "village": None,
        "district": None,
        "state": None
    }

    q = user_query.lower()

    # 1️⃣ Detect scheme
    for keyword, scheme_name in SCHEME_KEYWORDS.items():
        if keyword in q:
            result["scheme"] = scheme_name
            break

    # 2️⃣ Detect location
    # 2️⃣ Detect location
    m = re.search(r"in ([A-Za-z ]+)", user_query, re.IGNORECASE)
    if m:
    location = m.group(1).strip()

    location_l = location.lower()

    if location_l in INDIAN_STATES:
        result["state"] = location
    else:
        result["district"] = location

    # 3️⃣ Fallback scheme lookup from DB
    if not result["scheme"]:
        schemes = fetch_schemes()
        for s in schemes:
            if s["name"].lower() in q:
                result["scheme"] = s["name"]
                break

    return result
