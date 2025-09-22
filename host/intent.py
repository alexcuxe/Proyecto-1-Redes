# Simple intent detection & param extraction from free text.
# This is rule-based (regex/keywords) and can be upgraded to LLM later.

import re
from typing import Dict, Any, Optional

BRANDS = ["FAG", "NTN", "NSK", "KOYO", "TIMKEN", "NACHI", "SKF"]

NUM = r"[-+]?\d+(?:\.\d+)?"

def parse_floats(text: str) -> Dict[str, float]:
    """Extract common numeric parameters (Fr, Fa, rpm, L10h_target, temperature)."""
    out = {}
    # crude patterns like: Fr=3500, Fa=1200, rpm 1800, L10h 12000, T=40C
    patterns = {
        "Fr_N": r"(?:Fr[_\s]*=|Fr[_\s]*:|Fr\s*)(%s)" % NUM,
        "Fa_N": r"(?:Fa[_\s]*=|Fa[_\s]*:|Fa\s*)(%s)" % NUM,
        "rpm": r"(?:rpm[_\s]*=|rpm[_\s]*:|rpm\s*)(%s)" % NUM,
        "L10h_target": r"(?:L10h[_\s]*=|L10h[_\s]*:|L10h\s*)(%s)" % NUM,
        "temperature_C": r"(?:T\s*=?\s*|temp(?:erature)?\s*)(%s)" % NUM,
    }
    for k, pat in patterns.items():
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            out[k] = float(m.group(1))
    return out

def extract_model(text: str) -> Optional[str]:
    # capture like 6205, 6205C3, 6205-ZZ, etc.
    m = re.search(r"\b(6\d{3}[A-Z0-9\-]*)\b", text.upper())
    return m.group(1) if m else None

def extract_brand(text: str) -> Optional[str]:
    up = text.upper()
    for b in BRANDS:
        if re.search(rf"\b{b}\b", up):
            return b
    return None

def detect_intent(text: str) -> Dict[str, Any]:
    """
    Returns:
      { "intent": "...", "params": {...}, "needs": [ ... ] }
    """
    t = text.strip()
    up = t.upper()
    params: Dict[str, Any] = {}

    # 1) Croesus cross reference (brand + non_skf_designation) -> croesus_xref
    if any(k in up for k in ["REFER", "EQUIV", "CRUCE", "SKF"]) or "CROESUS" in up:
        brand = extract_brand(t)
        desig = extract_model(t)
        if brand and desig:
            return {"intent": "croesus_xref", "params": {"brand_code": brand, "non_skf_designation": desig}, "needs": []}
        needs = []
        if not brand: needs.append("brand_code")
        if not desig: needs.append("non_skf_designation")
        return {"intent": "croesus_xref", "params": {}, "needs": needs}

    # 2) Select bearing (select_bearing)
    if any(k in up for k in ["SELEC", "ELEGIR", "ESCOGER"]) and "RODAM" in up:
        params.update(parse_floats(t))
        # optional reliability, lubrication
        if re.search(r"\b95%\b|\b95\b", up): params["reliability_percent"] = 95
        if "ACEITE" in up: params["lubrication"] = "oil"
        if "GRASA" in up: params["lubrication"] = "grease"
        needs = []
        for req in ["rpm", "L10h_target"]:
            if req not in params: needs.append(req)
        if not ("Fr_N" in params or "Fa_N" in params): needs.append("Fr_N or Fa_N")
        return {"intent": "select_bearing", "params": params, "needs": needs}

    # 3) Verify point (verify_point)
    if "VERIF" in up and "RODAM" in up:
        model = extract_model(t)
        if model: params["model"] = model
        params.update(parse_floats(t))
        needs = []
        if "model" not in params: needs.append("model")
        if not ("Fr_N" in params or "Fa_N" in params): needs.append("Fr_N or Fa_N")
        if "rpm" not in params: needs.append("rpm")
        return {"intent": "verify_point", "params": params, "needs": needs}

    # 4) Catalog list
    if "CATÁLOG" in up or "CATALOG" in up:
        return {"intent": "catalog_list", "params": {}, "needs": []}

    # Fallback
    return {"intent": "smalltalk", "params": {}, "needs": []}
