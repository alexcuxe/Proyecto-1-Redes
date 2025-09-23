import json
from pathlib import Path
from models.bearing import Bearing
from models.calculator import equivalent_dynamic_load, life_L10, life_hours, apply_adjustments

CATALOG_PATH = Path(__file__).resolve().parents[1] / "catalog" / "catalog.json"

def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def tool_select_bearing(params: dict) -> dict:
    """
    Input:
      Fr_N, Fa_N, rpm, L10h_target, reliability_percent, temperature_C, lubrication
    Output:
      { ok, candidates:[{model,type,C_N,L10h_pred,margin_percent}], notes:[...] }
    """
    Fr = float(params.get("Fr_N", 0.0))
    Fa = float(params.get("Fa_N", 0.0))
    rpm = float(params.get("rpm", 0.0))
    L10h_target = float(params.get("L10h_target", 0.0))
    reliability = int(params.get("reliability_percent", 90))
    tempC = float(params.get("temperature_C", 25.0))
    lubrication = str(params.get("lubrication", "grease"))

    if rpm <= 0 or (Fr <= 0 and Fa <= 0) or L10h_target <= 0:
        return {"ok": False, "error": "Invalid parameters. Ensure rpm>0, (Fr or Fa)>0, L10h_target>0."}

    cat = load_catalog()
    candidates = []

    for b in cat.get("bearings", []):
        bearing = Bearing(model=b["model"], type=b["type"], C_N=float(b["C_N"]),
                          d_mm=b.get("d_mm"), D_mm=b.get("D_mm"), B_mm=b.get("B_mm"))

        P = equivalent_dynamic_load(Fr, Fa, bearing.type)
        L10 = life_L10(bearing.C_N, P, bearing.type)
        L10h = life_hours(L10, rpm)
        L10h_adj = apply_adjustments(L10h, reliability, tempC, lubrication)

        margin = (L10h_adj / L10h_target - 1.0) * 100.0
        if L10h_adj >= L10h_target:
            candidates.append({
                "model": bearing.model,
                "type": bearing.type,
                "C_N": bearing.C_N,
                "L10h_pred": round(L10h_adj, 2),
                "margin_percent": round(margin, 2)
            })

    candidates.sort(key=lambda c: c["margin_percent"], reverse=True)
    return {
        "ok": True,
        "candidates": candidates,
        "notes": [
            "Simplified P = Fr + Fa (conservative).",
            "Reliability/temperature factors are placeholders; replace with catalog standards."
        ]
    }