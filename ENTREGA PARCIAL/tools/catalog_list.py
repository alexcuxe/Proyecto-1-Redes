import json
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[1] / "catalog" / "catalog.json"

def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def tool_catalog_list(params: dict) -> dict:
    """Return minimal catalog view."""
    cat = load_catalog()
    items = [{"model": b["model"], "type": b["type"], "C_N": b["C_N"]} for b in cat.get("bearings", [])]
    return {"ok": True, "count": len(items), "items": items}
