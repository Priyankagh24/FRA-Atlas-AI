from fastapi import APIRouter, UploadFile, File, HTTPException
import requests
from db import engine
from sqlalchemy import text
from datetime import datetime

from utils.ocr_utils import extract_text_from_file
from utils.llm_utils import clean_with_llm  # with regex fallback

router = APIRouter(prefix="/upload", tags=["upload"])


def get_coordinates_from_address(address: str):
    """
    Get coordinates using OpenStreetMap Nominatim API.
    Returns (lat, lon) or "" if not found.
    """
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json", "limit": 1}
        headers = {"User-Agent": "fra-doc-system"}  # required by Nominatim
        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            results = response.json()
            if results:
                lat = results[0]["lat"]
                lon = results[0]["lon"]
                return f"{lat}, {lon}"
    except Exception as e:
        print(f"Coordinate fetch error: {e}")
    return ""

@router.post("/")
async def upload_document(file: UploadFile = File(...)):
    try:
        # 1️⃣ Read file
        file_bytes = await file.read()

        # 2️⃣ OCR
        ocr_text = extract_text_from_file(file_bytes)

        # 3️⃣ Clean text
        data = clean_with_llm(ocr_text)
         
        insert_sql = text("""
INSERT INTO fra_documents (
  patta_holder_name,
  father_or_husband_name,
  age,
  gender,
  address,
  village_name,
  block,
  district,
  state,
  total_area_claimed,
  coordinates,
  land_use,
  claim_id,
  claim_type,
  date_of_application,
  water_bodies,
  forest_cover,
  homestead,
  status
)
VALUES (
  :patta_holder_name,
  :father_or_husband_name,
  :age,
  :gender,
  :address,
  :village_name,
  :block,
  :district,
  :state,
  :total_area_claimed,
  :coordinates,
  :land_use,
  :claim_id,
  :claim_type,
  :date_of_application,
  :water_bodies,
  :forest_cover,
  :homestead,
  'pending'
)
RETURNING id;
""")


        params = {
            "patta_holder_name": data.get("Patta-Holder Name", ""),
            "father_or_husband_name": data.get("Father/Husband Name", ""),
            "age": int(data.get("Age")) if data.get("Age") else None,
            "gender": data.get("Gender", ""),
            "address": data.get("Address", ""),
            "village_name": data.get("Village Name", ""),
            "block": data.get("Block", ""),
            "district": data.get("District", ""),
            "state": data.get("State", ""),
            "total_area_claimed": data.get("Total Area Claimed", ""),
            "coordinates": data.get("Coordinates", ""),
            "land_use": data.get("Land Use", ""),
            "claim_id": data.get("Claim ID", ""),
            "claim_type": data.get("Type of Claim", ""),
            "date_of_application": data.get("Date of Application", ""),
            "water_bodies": data.get("Water bodies", ""),
            "forest_cover": data.get("Forest cover", ""),
            "homestead": data.get("Homestead", "")
        }

        with engine.begin() as conn:
            result = conn.execute(insert_sql, params)
            doc_id = result.scalar()

        return {
            "status": "success",
            "doc_id": doc_id,
            "data": data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/all")
async def get_all_documents():
    try:
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
          status,
          land_use,
          date_of_application,
          created_at
        FROM fra_documents
        ORDER BY created_at DESC;
        """)

        with engine.connect() as conn:
            rows = conn.execute(query).mappings().all()

        return {
            "status": "success",
            "count": len(rows),
            "results": rows
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))