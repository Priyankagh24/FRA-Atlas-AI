from fastapi import APIRouter
from sqlalchemy import text
from db import engine

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/summary")
def get_dashboard_summary():
    with engine.connect() as conn:
        kpi_query = text("""
            SELECT
                SUM(claims_total) AS total_claims,
                SUM(titles_total) AS verified_claims,
                COUNT(state_name) AS states
            FROM fra_statewise_claims;
        """)
        kpi = conn.execute(kpi_query).mappings().first()

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
            ORDER BY claims_total DESC;
        """)
        states = conn.execute(state_query).mappings().all()

    return {
        "kpis": [
            {"title": "Total Claims", "value": kpi["total_claims"]},
            {"title": "Verified Claims", "value": kpi["verified_claims"]},
            {"title": "States Covered", "value": kpi["states"]}
        ],
        "statewise": states
    }
