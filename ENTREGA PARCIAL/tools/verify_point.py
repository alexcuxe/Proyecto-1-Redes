import json
from pathlib import Path
from models.calculator import equivalent_dynamic_load, life_L10, life_hours, apply_adjustments

CATALOG_PATH = Path(__file__).resolve().parents[1] / "catalog" / "catalog.json"

def load_catalog_index():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {b["model"]: b for b in data.get("bearings", [])}

def tool_verify_point(params: dict) -> dict:
    """
    Input:
      model, Fr_N, Fa_N, rpm, reliability_percent, temperature_C, lubrication, L10h_target?
    Output:
      { ok, model, type, C_N, L10h_pred, meets_target?, margin_percent? }
    """
    model = str(params.get("model", "")).strip()
    if not model:
        return {"ok": False, "error": "Missing 'model'."}

    idx = load_catalog_index()
    b = idx.get(model)
    if not b:
        return {"ok": False, "error": f"Model not found: {model}"}

    Fr = float(params.get("Fr_N", 0.0))
    Fa = float(params.get("Fa_N", 0.0))
    rpm = float(params.get("rpm", 0.0))
    reliability = int(params.get("reliability_percent", 90))
    tempC = float(params.get("temperature_C", 25.0))
    lubrication = str(params.get("lubrication", "grease"))
    target = params.get("L10h_target")

    if rpm <= 0 or (Fr <= 0 and Fa <= 0):
        return {"ok": False, "error": "Invalid parameters. Ensure rpm>0 and (Fr or Fa)>0."}

    P = equivalent_dynamic_load(Fr, Fa, b["type"])
    L10 = life_L10(float(b["C_N"]), P, b["type"])
    L10h = life_hours(L10, rpm)
    L10h_adj = apply_adjustments(L10h, reliability, tempC, lubrication)

    out = {
        "ok": True, "model": model, "type": b["type"],
        "C_N": b["C_N"], "L10h_pred": round(L10h_adj, 2)
    }
    if target is not None:
        target = float(target)
        meets = L10h_adj >= target
        margin = (L10h_adj / target - 1.0) * 100.0
        out["meets_target"] = bool(meets)
        out["margin_percent"] = round(margin, 2)
    return out