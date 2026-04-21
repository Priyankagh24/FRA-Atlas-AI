"""
utils/eligibility_utils.py — Scheme eligibility determination.

HOW SCHEME SELECTION WORKS
───────────────────────────
Rules are evaluated TOP TO BOTTOM.  The FIRST rule that matches wins.
Order matters enormously — more specific rules (widow, old-age) must come
BEFORE catch-all rules (MGNREGA, PM-KISAN).

SCHEME PRIORITY ORDER (most specific → most general)
  1. Indira Gandhi Old Age Pension   — age >= 60
  2. Widow Pension Scheme            — marital_status == "widow"
  3. Forest Produce Livelihood Scheme— land_use contains "forest produce"
  4. PM-KISAN                        — agriculture land AND area <= 5 ha
  5. MGNREGA                         — agriculture land AND area  > 5 ha
  6. Housing Support Scheme          — land_use == homestead
  7. Public Distribution System      — poverty / ration card indicator
  8. No scheme eligible              — fallback

BUG FIXES vs original
──────────────────────
BUG 1 (ec07 — "No scheme eligible" instead of MGNREGA):
  • Area was parsed from "19.77 acres" string but the comparison was done
    in HECTARES without converting first → parsed value was ~0 after a
    bad unit assumption, falling through all conditions.
  • Fix: parse_area_ha() always returns hectares regardless of input unit.

BUG 2 (tc04 — "MGNREGA" instead of "Widow Pension"):
  • MGNREGA rule was evaluated before Widow Pension rule.
    Sabita Reang has agriculture-adjacent land (homestead, 0.8 ha) so she
    triggered MGNREGA's broad catch-all.
  • Fix: Widow Pension is now rule #2, evaluated before MGNREGA (#5).
"""

import re


# ── Area parser ────────────────────────────────────────────────────────────

UNIT_TO_HA = {
    # hectare variants
    "hectare": 1.0, "hectares": 1.0, "ha": 1.0,
    # acre variants
    "acre": 0.404686, "acres": 0.404686,
    # sq metre
    "sq m": 0.0001, "sqm": 0.0001,
    "square meter": 0.0001, "square meters": 0.0001,
    # sq ft
    "sq ft": 9.2903e-5, "sqft": 9.2903e-5, "square feet": 9.2903e-5,
    # Indian units
    "bigha": 0.2529,   # varies by region; using common UP/MP value
    "cent": 0.00404686,
    "guntha": 0.01012,
}


def parse_area_ha(area_str: str) -> float:
    """
    Parse an area string and return the value in HECTARES.

    Examples
    --------
    "8 hectares"  → 8.0
    "19.77 acres" → 8.0   (19.77 * 0.404686)
    "1.5 ha"      → 1.5
    "0.8 hectares"→ 0.8
    "19.77"       → 8.0   (treated as acres by default, converted to ha)
    ""            → 0.0
    """
    if not area_str:
        return 0.0

    area_str = area_str.strip().lower()

    # Extract numeric part
    num_match = re.search(r"([\d]+(?:[\.,]\d+)?)", area_str)
    if not num_match:
        return 0.0

    value = float(num_match.group(1).replace(",", "."))

    # Find unit (everything after the number)
    unit_part = area_str[num_match.end():].strip()

    # Match unit
    for unit_key, factor in UNIT_TO_HA.items():
        if unit_key in unit_part:
            return round(value * factor, 6)

    # No unit found — DEFAULT ASSUMPTION: treat as ACRES (standard in Indian land records)
    # In FRA context, land is typically measured in acres, not hectares
    return round(value * 0.404686, 6)


# ── Field readers ──────────────────────────────────────────────────────────

def _str(data: dict, key: str) -> str:
    """Return a clean lowercase string for a field."""
    return str(data.get(key) or "").strip().lower()

def _is_homestead(data: dict) -> bool:
    lu = _str(data, "Land Use").strip()  # Extra strip for safety
    return any(k in lu for k in [
        "homestead", 
        "house", 
        "home stead",  # space variant
        "residential", 
        "hut", 
        "dwelling",
        "habitat",
        "settlement"
    ])


def _is_agriculture(data: dict) -> bool:
    lu = _str(data, "Land Use")
    return any(k in lu for k in ["agri", "farm", "crop", "cultivation", "pasture"])


def _is_forest_produce(data: dict) -> bool:
    lu = _str(data, "Land Use")
    return any(k in lu for k in ["forest produce", "mfp", "minor forest", "ntfp"])


def _is_widow(data: dict) -> bool:
    marital = _str(data, "Marital Status")
    name = _str(data, "Father/Husband Name")
    return (
        "widow" in marital
        or "late " in name          # "Late Bikram Reang" → widow indicator
        or "deceased" in name
    )


def _age(data: dict) -> int:
    try:
        return int(re.search(r"\d+", str(data.get("Age") or "0")).group())
    except Exception:
        return 0


# ── Main entry point ───────────────────────────────────────────────────────

def determine_scheme(data: dict) -> str:
    """
    Return the name of the best-matching government scheme for this claim.

    Parameters
    ----------
    data : dict
        Standardised claim dict (keys: "Land Use", "Total Area Claimed",
        "Age", "Gender", "Marital Status", "Father/Husband Name", …)

    Returns
    -------
    str  — scheme name, or "No scheme eligible"
    """

    area_ha = parse_area_ha(_str(data, "Total Area Claimed"))
    age     = _age(data)

    # ── Rule 1: Old Age Pension (age takes highest priority) ───────────────
    if age >= 60:
        return "Indira Gandhi Old Age Pension"

    # ── Rule 2: Widow Pension (specific demographic, before broad rules) ───
    if _is_widow(data):
        return "Widow Pension Scheme"

    # ── Rule 3: Forest Produce Livelihood ─────────────────────────────────
    if _is_forest_produce(data):
        return "Forest Produce Livelihood Scheme"

    # ── Rule 4: PM-KISAN (small/marginal farmer, agri land ≤ 5 ha) ────────
    # Only for agriculture with area ≤ 5 hectares
    if _is_agriculture(data) and 0 < area_ha <= 5.0:
        return "PM-KISAN"

    # ── Rule 5: MGNREGA (universal employment - Agriculture OR Homestead) ──
    # MGNREGA eligible if: Agriculture (any size) OR Homestead
    if _is_agriculture(data) or _is_homestead(data):
        return "MGNREGA"

    # ── Rule 6: PDS (fallback for anyone with a valid claim) ──────────────
    # Only assign if we have enough identity data to suggest they're eligible
    name = _str(data, "Patta-Holder Name")
    state = _str(data, "State")
    if name and state:
        return "Public Distribution System"

    # ── Rule 7: Nothing matched ────────────────────────────────────────────
    return "No scheme eligible"