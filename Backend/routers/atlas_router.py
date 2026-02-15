from fastapi import APIRouter
from sqlalchemy import text
from db import engine

router = APIRouter(prefix="/atlas", tags=["Atlas"])

@router.get("/claims")
def get_all_claims_for_atlas():
    """
    Returns all FRA claims with coordinates for map visualization
    """
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
        'verified' AS status,
        land_use,
        date_of_application,
        created_at
       FROM fra_documents
    WHERE coordinates IS NOT NULL
      AND coordinates <> ''
""")


    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
        return {"results": [dict(row) for row in rows]}

