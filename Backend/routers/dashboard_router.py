from fastapi import APIRouter
from sqlalchemy import text
from db import engine

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# ✅ Project scope: only these 4 states are supported
SUPPORTED_STATES = ["Madhya Pradesh", "Odisha", "Telangana", "Tripura"]

@router.get("/summary")
def get_dashboard_summary():
    with engine.connect() as conn:

        # KPI totals — scoped to supported states only
        kpi_query = text("""
            SELECT
                SUM(claims_total)  AS total_claims,
                SUM(titles_total)  AS verified_claims,
                COUNT(state_name)  AS states
            FROM fra_statewise_claims
            WHERE state_name = ANY(:states);
        """)
        kpi = conn.execute(kpi_query, {"states": SUPPORTED_STATES}).mappings().first()

        # Per-state breakdown — supported states only, sorted by claims desc
        state_query = text("""
            SELECT
                state_name,
                claims_total,
                titles_total,
                ROUND(
                    (titles_total::numeric / NULLIF(claims_total, 0)) * 100,
                    2
                ) AS progress
            FROM fra_statewise_claims
            WHERE state_name = ANY(:states)
            ORDER BY claims_total DESC;
        """)
        states = conn.execute(state_query, {"states": SUPPORTED_STATES}).mappings().all()

        # Recent uploads — valid documents in supported states only
        recent_query = text("""
            SELECT id, patta_holder_name, state, land_use, status, created_at
            FROM fra_documents
            WHERE
                patta_holder_name IS NOT NULL
                AND TRIM(patta_holder_name) != ''
                AND TRIM(patta_holder_name) != '":'
                AND state = ANY(:states)
            ORDER BY created_at DESC
            LIMIT 10;
        """)
        recent = conn.execute(recent_query, {"states": SUPPORTED_STATES}).mappings().all()

    return {
        "kpis": [
            {"title": "Total Claims",    "value": kpi["total_claims"]},
            {"title": "Verified Claims", "value": kpi["verified_claims"]},
            {"title": "States Covered",  "value": kpi["states"]},
        ],
        "statewise": [dict(r) for r in states],
        "recent":    [dict(r) for r in recent],
    }