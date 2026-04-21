"""
Search_router.py — Full-text search across fra_documents.

Fixes vs original:
  • Import write_dss_log from db (single source of truth).
  • Removed broken import from routers.dss_helpers (wrong module name).
  • Kept all existing search/filter logic unchanged.
"""

from fastapi import APIRouter, Query
from typing import Optional
from sqlalchemy import text
from db import engine, write_dss_log   # ← single import source

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/")
async def search_claims(
    q: Optional[str] = Query(None, description="General search query"),
    status: Optional[str] = Query(None, description="Filter by claim status"),
    state: Optional[str] = Query(None, description="Filter by state"),
    district: Optional[str] = Query(None, description="Filter by district"),
):
    base_query = "SELECT * FROM fra_documents WHERE 1=1"
    params: dict = {}

    if q:
        base_query += """
            AND (
                patta_holder_name ILIKE :q1
                OR village_name   ILIKE :q2
                OR district       ILIKE :q3
                OR state          ILIKE :q4
                OR claim_id       ILIKE :q5
            )"""
        like_q = f"%{q}%"
        params.update(q1=like_q, q2=like_q, q3=like_q, q4=like_q, q5=like_q)

    if status:
        base_query += " AND status ILIKE :status"
        params["status"] = f"%{status}%"

    if state:
        base_query += " AND state ILIKE :state"
        params["state"] = f"%{state}%"

    if district:
        base_query += " AND district ILIKE :district"
        params["district"] = f"%{district}%"

    with engine.connect() as conn:
        rows = conn.execute(text(base_query), params).mappings().all()

    results = [dict(r) for r in rows]

    # Log DSS usage (best-effort; never crash the search endpoint)
    try:
        write_dss_log(
            user_query=q or "",
            parsed={"status": status, "state": state, "district": district},
            scheme_id=None,
            count=len(results),
            sample=results[:3],
        )
    except Exception as e:
        print("⚠️ DSS log failed:", e)

    return {"count": len(results), "results": results}


@router.get("/statewise")
def get_statewise_claims():
    query = text("SELECT * FROM fra_statewise_claims;")
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return {"count": len(rows), "results": [dict(r) for r in rows]}