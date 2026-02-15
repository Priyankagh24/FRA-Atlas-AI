from fastapi import APIRouter, HTTPException, Query
from db import insert_scheme, get_scheme_by_name, fetch_schemes, write_dss_log
from services.scheme_service import find_eligible_people_by_scheme
from utils.llm_utils import parse_dss_query  # your LLM query parser


SCHEME_KEYWORDS = {
    "housing": "Housing Support Scheme",
    "house": "Housing Support Scheme",
    "homestead": "Housing Support Scheme",
    "minor forest produce": "Minor Forest Produce Scheme",
    "mfp": "Minor Forest Produce Scheme",
    "farm": "Farm Support Scheme",
    "agriculture": "Farm Support Scheme",
    "pds": "Public Distribution System",
    "ration": "Public Distribution System"
}


router = APIRouter(prefix="/dss", tags=["dss"])


@router.post("/schemes")
def create_scheme(payload: dict):
    name = payload.get("name")
    eligibility = payload.get("eligibility")
    if not name or not eligibility:
        raise HTTPException(status_code=400, detail="name and eligibility required")

    scheme_id = insert_scheme(name, payload.get("description", ""), eligibility)
    return {"id": scheme_id, "name": name}


@router.get("/schemes")
def list_schemes():
    return fetch_schemes()


@router.get("/check")

def dss_check(
    q: str = Query(
        ...,
        title="Eligibility Question",
        description="Ask in natural language, e.g. Who is eligible for Farm Support Scheme in Koraput, Odisha?",
        example="Who is eligible for Farm Support Scheme in Koraput, Odisha?"
    )
):
    # 1️⃣ Run LLM parser
    parsed = parse_dss_query(q)

    scheme_name = parsed.get("scheme")
    village = parsed.get("village")
    district = parsed.get("district")
    state = parsed.get("state")

    # 2️⃣ 🔁 FALLBACK: keyword-based scheme detection
    if not scheme_name:
        q_lower = q.lower()
        for keyword, mapped_scheme in SCHEME_KEYWORDS.items():
            if keyword in q_lower:
                scheme_name = mapped_scheme
                parsed["scheme"] = scheme_name
                break

    # 3️⃣ Still not found → error
    if not scheme_name:
        return {
            "status": "error",
            "message": "Could not extract scheme name from query"
        }

    # 4️⃣ Fetch scheme from DB
    scheme = get_scheme_by_name(scheme_name)
    if not scheme:
        return {
            "status": "error",
            "message": f"Scheme '{scheme_name}' not found"
        }

    # 5️⃣ Find eligible people
    try:
        results = find_eligible_people_by_scheme(
    scheme=scheme,
    village=parsed.get("village"),
    district=parsed.get("district"),
    state=parsed.get("state")
)

    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}"
        }

    return {
        "status": "ok",
        "scheme": scheme_name,
        "filters": parsed,
        "count": len(results),
        "results": results
    }
