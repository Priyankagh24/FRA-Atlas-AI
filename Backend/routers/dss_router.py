"""
dss_router.py  —  Decision Support System (ENHANCED)
=====================================================
New features vs original:
  1. Full CSS scheme set: PM-KISAN, MGNREGA, Jal Jeevan Mission,
     DAJGUA (MoTA/MoRD/MoA), Forest Produce Livelihood, Widow Pension,
     Old Age Pension, Housing Support, PDS
  2. Priority Intervention Engine:
     - Low water index → Jal Shakti / Jal Jeevan Mission borewell priority
     - Forest land → CFR / Forest Produce scheme recommendation
     - Large agriculture → PM-KISAN + irrigation
  3. /dss/interventions endpoint: returns ranked intervention list per village
  4. /dss/village-report endpoint: full DSS report for a village
  5. Retained original /dss/check and /dss/schemes
"""

from fastapi import APIRouter, HTTPException, Query
from db import insert_scheme, get_scheme_by_name, fetch_schemes, write_dss_log
from services.scheme_service import find_eligible_people_by_scheme
from utils.llm_utils import parse_dss_query, INDIAN_STATES
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from db import engine

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


# ─── Scheme keyword map (EXPANDED) ──────────────────────────────────────────
SCHEME_KEYWORDS = {
    "housing": "Housing Support Scheme",
    "house": "Housing Support Scheme",
    "homestead": "Housing Support Scheme",
    "minor forest produce": "Forest Produce Livelihood Scheme",
    "mfp": "Forest Produce Livelihood Scheme",
    "forest produce": "Forest Produce Livelihood Scheme",
    "forest": "Forest Produce Livelihood Scheme",
    "farm": "PM-KISAN",
    "agriculture": "PM-KISAN",
    "pm-kisan": "PM-KISAN",
    "kisan": "PM-KISAN",
    "pds": "Public Distribution System",
    "ration": "Public Distribution System",
    "water": "Jal Jeevan Mission",
    "jal jeevan": "Jal Jeevan Mission",
    "jal shakti": "Jal Jeevan Mission",
    "borewell": "Jal Jeevan Mission",
    "drinking water": "Jal Jeevan Mission",
    "mgnrega": "MGNREGA",
    "employment": "MGNREGA",
    "dajgua": "DAJGUA",
    "tribal": "DAJGUA",
    "adivasi": "DAJGUA",
    "widow": "Widow Pension Scheme",
    "old age": "Indira Gandhi Old Age Pension",
    "pension": "Indira Gandhi Old Age Pension",
    "senior": "Indira Gandhi Old Age Pension",
}

# ─── CSS Scheme Definitions (for auto-seeding) ─────────────────────────────
CSS_SCHEMES = [
    {
        "name": "PM-KISAN",
        "description": "Pradhan Mantri Kisan Samman Nidhi — ₹6000/year direct income support for small and marginal farmers with agricultural land ≤ 5 acres.",
        "eligibility": {"land_use": "Agriculture", "max_land_acres": 5.0, "min_age": 18}
    },
    {
        "name": "MGNREGA",
        "description": "Mahatma Gandhi National Rural Employment Guarantee Act — 100 days of guaranteed wage employment per household per year.",
        "eligibility": {"min_age": 18}
    },
    {
        "name": "Jal Jeevan Mission",
        "description": "Har Ghar Jal — piped water supply to every rural household. Priority for villages with low water index and near water bodies.",
        "eligibility": {"min_age": 18}
    },
    {
        "name": "DAJGUA",
        "description": "Development of Particularly Vulnerable Tribal Groups — convergence scheme by MoTA/MoRD/MoA for forest-dwelling tribal communities.",
        "eligibility": {"min_age": 18, "land_use": "Forest"}
    },
    {
        "name": "Forest Produce Livelihood Scheme",
        "description": "Minor Forest Produce support and community forest resource rights livelihood scheme for CFR holders.",
        "eligibility": {"land_use": "Forest", "min_age": 18}
    },
    {
        "name": "Housing Support Scheme",
        "description": "PM Awas Yojana (Gramin) for homestead / residential land FRA holders — housing construction support.",
        "eligibility": {"land_use": "Homestead", "min_age": 18}
    },
    {
        "name": "Widow Pension Scheme",
        "description": "Indira Gandhi National Widow Pension Scheme — monthly pension for widows aged 40-79.",
        "eligibility": {"gender": "Female", "min_age": 40, "max_age": 79}
    },
    {
        "name": "Indira Gandhi Old Age Pension",
        "description": "Monthly pension for senior citizens aged 60 and above from BPL households.",
        "eligibility": {"min_age": 60}
    },
    {
        "name": "Public Distribution System",
        "description": "Subsidised food grains under National Food Security Act for FRA patta holders.",
        "eligibility": {"min_age": 18}
    },
]


router = APIRouter(prefix="/dss", tags=["dss"])


# ─── Models ──────────────────────────────────────────────────────────────────

class EligibilityRules(BaseModel):
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    gender: Optional[str] = None
    state: Optional[str] = None
    min_land_acres: Optional[float] = None
    max_land_acres: Optional[float] = None
    land_use: Optional[str] = None

    class Config:
        extra = "forbid"


class SchemeCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    eligibility: EligibilityRules


# ─── Auto-seed CSS schemes on first call ────────────────────────────────────

def _seed_css_schemes():
    """Idempotently insert all CSS schemes into DB if not present."""
    try:
        existing = {s["name"] for s in fetch_schemes()}
        for scheme in CSS_SCHEMES:
            if scheme["name"] not in existing:
                insert_scheme(scheme["name"], scheme["description"], scheme["eligibility"])
    except Exception as e:
        print(f"⚠️ Could not seed CSS schemes: {e}")


# ─── Priority intervention engine ───────────────────────────────────────────

def _compute_interventions(records: list) -> List[Dict[str, Any]]:
    """
    Given a list of fra_documents records for a village/district,
    return a ranked list of intervention recommendations.
    """
    interventions = []
    total = len(records)
    if total == 0:
        return interventions

    # Count land use types
    land_uses = [str(r.get("land_use", "")).lower() for r in records]
    forest_count    = sum(1 for lu in land_uses if "forest" in lu)
    agri_count      = sum(1 for lu in land_uses if any(k in lu for k in ["agri", "crop", "cultivation"]))
    water_count     = sum(1 for lu in land_uses if any(k in lu for k in ["water", "river", "pond", "lake"]))
    homestead_count = sum(1 for lu in land_uses if any(k in lu for k in ["home", "residential"]))

    # Age stats
    ages = []
    for r in records:
        try:
            ages.append(int(r.get("age") or 0))
        except Exception:
            pass
    avg_age = sum(ages) / len(ages) if ages else 0
    senior_count = sum(1 for a in ages if a >= 60)
    
    # Gender
    female_count = sum(1 for r in records if str(r.get("gender", "")).lower().startswith("f"))

    # ── Rule-based priority scoring ──────────────────────────────────────────

    if water_count == 0 and total > 0:
        interventions.append({
            "priority": 1,
            "intervention": "Jal Jeevan Mission — Borewell / Piped Water",
            "reason": f"No water body land use detected in {total} claims. Village likely has low water index.",
            "scheme": "Jal Jeevan Mission",
            "urgency": "HIGH",
            "beneficiaries_estimated": total,
        })

    if forest_count > 0:
        interventions.append({
            "priority": 2,
            "intervention": "DAJGUA + Forest Produce Livelihood",
            "reason": f"{forest_count}/{total} claims involve forest land. CFR community eligible for DAJGUA convergence.",
            "scheme": "DAJGUA",
            "urgency": "HIGH",
            "beneficiaries_estimated": forest_count,
        })

    if agri_count > 0:
        interventions.append({
            "priority": 3,
            "intervention": "PM-KISAN + irrigation support",
            "reason": f"{agri_count}/{total} claims contain agricultural land. Farmers can benefit from PM-KISAN and irrigation support.",
            "scheme": "PM-KISAN",
            "urgency": "MEDIUM",
            "beneficiaries_estimated": agri_count,
        })

    if homestead_count > 0:
        interventions.append({
            "priority": 4,
            "intervention": "Housing Support / Homestead Development",
            "reason": f"{homestead_count}/{total} claims are homestead/residential, making them eligible for housing and livelihood support schemes.",
            "scheme": "Housing Support Scheme",
            "urgency": "MEDIUM",
            "beneficiaries_estimated": homestead_count,
        })

    if senior_count > 0:
        interventions.append({
            "priority": 5,
            "intervention": "Old Age Pension Outreach",
            "reason": f"{senior_count}/{total} claimants are seniors; priority pension and social security benefits should be offered.",
            "scheme": "Indira Gandhi Old Age Pension",
            "urgency": "MEDIUM",
            "beneficiaries_estimated": senior_count,
        })

    if not interventions:
        interventions.append({
            "priority": 10,
            "intervention": "Review FRA claim eligibility and local convergence",
            "reason": "No clear rule-based intervention was triggered; review local claim data and available schemes for this village/district.",
            "scheme": "Local FRA Support",
            "urgency": "LOW",
            "beneficiaries_estimated": total,
        })

    if senior_count > 0:
        interventions.append({
            "priority": 4,
            "intervention": "Indira Gandhi Old Age Pension",
            "reason": f"{senior_count} claimants aged 60+. Eligible for monthly old age pension.",
            "scheme": "Indira Gandhi Old Age Pension",
            "urgency": "MEDIUM",
            "beneficiaries_estimated": senior_count,
        })

    if female_count > 0:
        interventions.append({
            "priority": 5,
            "intervention": "Widow Pension / Women Welfare Schemes",
            "reason": f"{female_count} female claimants. Widow-eligible women (40+) qualify for pension.",
            "scheme": "Widow Pension Scheme",
            "urgency": "MEDIUM",
            "beneficiaries_estimated": female_count,
        })

    if homestead_count > 0:
        interventions.append({
            "priority": 6,
            "intervention": "PM Awas Yojana (Gramin) — Housing",
            "reason": f"{homestead_count} homestead claims. Eligible for housing construction support.",
            "scheme": "Housing Support Scheme",
            "urgency": "LOW",
            "beneficiaries_estimated": homestead_count,
        })

    # MGNREGA — always applicable
    interventions.append({
        "priority": 7,
        "intervention": "MGNREGA — 100 Days Employment Guarantee",
        "reason": f"All {total} adult claimants eligible for 100 days of guaranteed wage employment.",
        "scheme": "MGNREGA",
        "urgency": "LOW",
        "beneficiaries_estimated": total,
    })

    return sorted(interventions, key=lambda x: x["priority"])


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/schemes")
def create_scheme(payload: SchemeCreate):
    try:
        scheme_id = insert_scheme(payload.name, payload.description, payload.eligibility.dict())
        return {"status": "success", "id": scheme_id, "name": payload.name}
    except IntegrityError:
        raise HTTPException(status_code=409, detail=f"Scheme '{payload.name}' already exists.")


@router.get("/schemes")
def list_schemes():
    _seed_css_schemes()
    return fetch_schemes()


@router.get("/seed-schemes")
def seed_css_schemes():
    """Manually trigger seeding of all CSS schemes into the database."""
    _seed_css_schemes()
    return {"status": "ok", "seeded": [s["name"] for s in CSS_SCHEMES]}


@router.get("/interventions")
def get_interventions(
    village: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
):
    """
    Returns priority-ranked intervention recommendations for a village/district.
    Falls back through village → district → state → all-India if no results found.
    """
    # Try progressively broader location filters until we get records
    records = []
    used_scope = "none"

    if village or district or state:
        # Try exact location first
        records = find_eligible_people_by_scheme(
            scheme=None, village=village, district=district, state=state
        )
        if records:
            used_scope = "village" if village else ("district" if district else "state")

    # Fallback: try district only
    if not records and district:
        records = find_eligible_people_by_scheme(scheme=None, district=district, state=state)
        if records:
            used_scope = "district"

    # Fallback: try state only
    if not records and state:
        records = find_eligible_people_by_scheme(scheme=None, state=state)
        if records:
            used_scope = "state"

    # Final fallback: use all records to generate generic interventions
    if not records:
        from sqlalchemy import text as sql_text
        with engine.connect() as conn:
            rows = conn.execute(sql_text("SELECT * FROM fra_documents LIMIT 100")).mappings().all()
        records = [dict(r) for r in rows]
        used_scope = "all"

    interventions = _compute_interventions(records)

    # If still empty (no records at all in DB), return sensible defaults
    if not interventions:
        interventions = [
            {
                "priority": 1,
                "intervention": "MGNREGA — 100 Days Employment Guarantee",
                "reason": "Universal employment scheme applicable to all adult FRA patta holders.",
                "scheme": "MGNREGA",
                "urgency": "HIGH",
                "beneficiaries_estimated": 0,
            },
            {
                "priority": 2,
                "intervention": "Jal Jeevan Mission — Piped Water Supply",
                "reason": "Priority drinking water scheme for forest-dwelling communities.",
                "scheme": "Jal Jeevan Mission",
                "urgency": "HIGH",
                "beneficiaries_estimated": 0,
            },
            {
                "priority": 3,
                "intervention": "PM-KISAN Direct Benefit Transfer",
                "reason": "₹6000/year income support for small and marginal farmers.",
                "scheme": "PM-KISAN",
                "urgency": "MEDIUM",
                "beneficiaries_estimated": 0,
            },
        ]

    return {
        "status": "ok",
        "location": {"village": village, "district": district, "state": state},
        "scope_used": used_scope,
        "total_claims": len(records),
        "interventions": interventions,
    }


@router.get("/village-report")
def village_report(
    village: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
):
    """
    Full DSS village report: demographics + scheme distribution + interventions.
    Used for policy formulation and scheme layering.
    """
    if not any([village, district, state]):
        raise HTTPException(400, "Provide at least one location filter")

    records = find_eligible_people_by_scheme(
        scheme=None, village=village, district=district, state=state
    )

    if not records:
        return {
            "status": "ok",
            "location": {"village": village, "district": district, "state": state},
            "total_claims": 0,
            "message": "No claims found for this location",
        }

    # Scheme distribution
    scheme_counts: Dict[str, int] = {}
    for r in records:
        s = r.get("eligible_scheme") or "Unclassified"
        scheme_counts[s] = scheme_counts.get(s, 0) + 1

    # Land use distribution
    land_use_counts: Dict[str, int] = {}
    for r in records:
        lu = r.get("land_use") or "Unknown"
        land_use_counts[lu] = land_use_counts.get(lu, 0) + 1

    # Claim type distribution
    claim_type_counts: Dict[str, int] = {}
    for r in records:
        ct = r.get("claim_type") or "Unknown"
        claim_type_counts[ct] = claim_type_counts.get(ct, 0) + 1

    interventions = _compute_interventions(records)

    return {
        "status": "ok",
        "location": {"village": village, "district": district, "state": state},
        "total_claims": len(records),
        "scheme_distribution": scheme_counts,
        "land_use_distribution": land_use_counts,
        "claim_type_distribution": claim_type_counts,
        "interventions": interventions,
        "claims_sample": records[:5],  # preview first 5
    }


@router.get("/check")
def dss_check(
    q: str = Query(
        ...,
        description="Ask in natural language, e.g. 'Who is eligible for Jal Jeevan Mission in Koraput, Odisha?'",
        example="Who is eligible for MGNREGA in Mayurbhanj, Odisha?",
    )
):
    _seed_css_schemes()

    q_normalized = " ".join(q.lower().split())

    out_of_scope_keywords = [
        "weather", "temperature", "forecast", "time", "date",
        "news", "politics", "sports", "entertainment",
        "buy", "purchase", "price", "cost", "sell",
        "travel", "flight", "hotel", "booking",
        "music", "movie", "game", "play",
        "joke", "funny", "laugh", "meme"
    ]
    if any(keyword in q_normalized for keyword in out_of_scope_keywords):
        return {
            "status": "error",
            "message": "I can only help with FRA scheme eligibility queries. Please ask about government schemes, claims, or beneficiaries."
        }

    if len(q_normalized) < 3 or not any(c.isalpha() for c in q_normalized):
        return {
            "status": "error",
            "message": "Could not understand your query. Try: 'Who is eligible for MGNREGA in Odisha?'"
        }

    parsed = parse_dss_query(q)
    scheme_name = parsed.get("scheme")
    village  = parsed.get("village")
    district = parsed.get("district")
    state    = parsed.get("state")

    # Keyword fallback for scheme
    if not scheme_name:
        q_lower = q.lower()
        for keyword, mapped_scheme in SCHEME_KEYWORDS.items():
            if keyword in q_lower:
                scheme_name = mapped_scheme
                parsed["scheme"] = scheme_name
                break

    # DB scheme name fallback
    if not scheme_name:
        try:
            schemes = fetch_schemes()
            for s in schemes:
                if s["name"].lower() in q_normalized:
                    scheme_name = s["name"]
                    parsed["scheme"] = scheme_name
                    break
        except Exception:
            pass

    # Validate state
    if state and state.lower() not in INDIAN_STATES:
        return {
            "status": "error",
            "message": f"State '{state}' is not supported. Supported: {', '.join(sorted(INDIAN_STATES))}"
        }

    # Intervention query detection
    if any(word in q_normalized for word in ["intervention", "priority", "recommend", "suggest", "what scheme"]):
        records = find_eligible_people_by_scheme(
            scheme=None, village=village, district=district, state=state
        )
        interventions = _compute_interventions(records)
        return {
            "status": "ok",
            "type": "interventions",
            "location": {"village": village, "district": district, "state": state},
            "interventions": interventions,
        }

    if scheme_name:
        scheme = get_scheme_by_name(scheme_name)
        if not scheme:
            return {"status": "error", "message": f"Scheme '{scheme_name}' not found in database. Try GET /dss/seed-schemes first."}

        try:
            results = find_eligible_people_by_scheme(
                scheme=scheme, village=village, district=district, state=state
            )
        except Exception as e:
            return {"status": "error", "message": f"Database error: {str(e)}"}

        if not results:
            loc_parts = [p for p in [state, district, village] if p]
            loc_str = " in " + ", ".join(loc_parts) if loc_parts else ""
            return {
                "status": "ok",
                "scheme": scheme_name,
                "filters": parsed,
                "count": 0,
                "results": [],
                "message": f"No beneficiaries found for {scheme_name}{loc_str}",
            }

        return {
            "status": "ok",
            "scheme": scheme_name,
            "filters": parsed,
            "count": len(results),
            "results": results,
        }

    # Location-only query
    try:
        results = find_eligible_people_by_scheme(
            scheme=None, village=village, district=district, state=state
        )
        loc_parts = []
        if state:    loc_parts.append(f"State: {state}")
        if district: loc_parts.append(f"District: {district}")
        if village:  loc_parts.append(f"Village: {village}")

        return {
            "status": "ok",
            "scheme": f"All Claims — {', '.join(loc_parts)}" if loc_parts else "All Claims",
            "filters": parsed,
            "count": len(results),
            "results": results,
        }
    except Exception as e:
        return {"status": "error", "message": f"Database error: {str(e)}"}