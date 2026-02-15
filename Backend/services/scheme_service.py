import re
from sqlalchemy import text
from db import engine


# -------------------------
# Helpers
# -------------------------

def parse_acres_from_text(area_text: str) -> float:
    if not area_text:
        return 0.0
    m = re.search(r"([\d\.]+)", str(area_text))
    return float(m.group(1)) if m else 0.0


def normalize_gender(g: str) -> str:
    if not g:
        return ""
    g = g.lower().strip()
    if g.startswith("m"):
        return "male"
    if g.startswith("f"):
        return "female"
    if g.startswith("o"):
        return "other"
    return g


def matches_criteria(record: dict, criteria: dict) -> bool:
    # --- Land Use (CRITICAL FIX) ---
    if criteria.get("land_use"):
        if not record.get("land_use"):
            return False
        if criteria["land_use"].lower() not in record["land_use"].lower():
            return False

    # --- Age ---
    age = None
    if record.get("age"):
        try:
            age = int(re.search(r"\d+", str(record["age"])).group(0))
        except Exception:
            age = None

    if criteria.get("min_age") is not None:
        if age is None or age < int(criteria["min_age"]):
            return False

    if criteria.get("max_age") is not None:
        if age is None or age > int(criteria["max_age"]):
            return False

    # --- State ---
    if criteria.get("state"):
        if not record.get("state") or criteria["state"].lower() != record["state"].lower():
            return False

    # --- Gender ---
    if criteria.get("gender"):
        if normalize_gender(criteria["gender"]) != normalize_gender(record.get("gender", "")):
            return False

    # --- Land Area ---
    if criteria.get("min_land_acres") is not None:
        acres = parse_acres_from_text(record.get("total_area_claimed", ""))
        if acres < float(criteria["min_land_acres"]):
            return False

    if criteria.get("max_land_acres") is not None:
        acres = parse_acres_from_text(record.get("total_area_claimed", ""))
        if acres > float(criteria["max_land_acres"]):
            return False

    return True


# -------------------------
# MAIN DSS FUNCTION
# -------------------------

def find_eligible_people_by_scheme(scheme, village=None, district=None, state=None):
    base_query = """
        SELECT *
        FROM fra_documents
        WHERE land_use ILIKE '%Homestead%'
    """

    params = {}

    if state:
        base_query += " AND LOWER(state) LIKE LOWER(:state)"
        params["state"] = f"%{state.strip().lower()}%"

    if district:
        base_query += " AND LOWER(district) LIKE LOWER(:district)"
        params["district"] = f"%{district.strip().lower()}%"

    if village:
        base_query += " AND LOWER(village_name) LIKE LOWER(:village)"
        params["village"] = f"%{village.strip().lower()}%"

    base_query += " ORDER BY created_at DESC"

    with engine.connect() as conn:
        rows = conn.execute(text(base_query), params).mappings().all()

    return [dict(r) for r in rows]
