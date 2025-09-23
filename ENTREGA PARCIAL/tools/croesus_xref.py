# tools/croesus_xref.py
# MCP tool to call Croesus and return cross references.
from external.croesus_client import CroesusClient

def tool_croesus_xref(params: dict) -> dict:
    """Input: brand_code, non_skf_designation. Output: hits[]"""
    brand = str(params.get("brand_code", "")).strip()
    desig = str(params.get("non_skf_designation", "")).strip()
    if not brand or not desig:
        return {"ok": False, "error": "brand_code and non_skf_designation are required."}

    client = CroesusClient()
    hits = client.search(brand, desig)
    # Keep essential fields only (to keep output concise)
    pruned = []
    for h in hits:
        pruned.append({
            "category": h.get("category"),
            "brand_code": h.get("brand_code"),
            "brand_name": h.get("brand_name"),
            "non_skf_designation": h.get("non_skf_designation"),
            "skf_designation": h.get("skf_designation"),
            "short_description": h.get("short_description"),
            "attributes": h.get("attributes", []),
        })
    return {"ok": True, "count": len(pruned), "hits": pruned}
