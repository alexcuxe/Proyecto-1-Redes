# main.py
# bearingpro-mcp: JSON-RPC over stdio (MCP-like) for bearing selection/verification

import sys, json
from pathlib import Path
from bearing_utils import adjusted_P, calc_l10h, round2

CATALOG_PATH = Path(__file__).parent / "catalog.json"
CAT = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
BEARINGS = CAT.get("bearings", [])

def _read_frame():
    # Read headers
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        s = line.decode("utf-8", "replace").strip()
        if s == "":
            break
        k, v = s.split(":", 1)
        headers[k.strip().lower()] = v.strip()
    length = int(headers.get("content-length", "0"))
    body = sys.stdin.buffer.read(length).decode("utf-8", "replace") if length > 0 else ""
    return json.loads(body) if body else None

def _write_frame(obj):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\nContent-Type: application/json\r\n\r\n".encode("utf-8"))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()

def _ok(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}

def _err(id_, code=-32601, msg="method not found"):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": msg}}

def _find_model(model):
    if not model: 
        return None
    m = str(model).strip().lower()
    for b in BEARINGS:
        if b.get("model","").lower() == m:
            return b
    # simple heuristic: allow bare '6205' to match '*6205*'
    for b in BEARINGS:
        if "6205" in m and "6205" in b.get("model","").lower():
            return b
    return None

def tool_catalog_list(_args):
    # Return full catalog
    return {"ok": True, "models": BEARINGS}

def tool_select_bearing(args):
    # Inputs: Fr_N, Fa_N, rpm, L10h_target (defaults allowed)
    Fr = float(args.get("Fr_N", 0) or 0)
    Fa = float(args.get("Fa_N", 0) or 0)
    rpm = float(args.get("rpm", 1800) or 1800)
    L10h_target = float(args.get("L10h_target", 12000) or 12000)

    P = adjusted_P(Fr, Fa)
    cands = []
    for it in BEARINGS:
        C = float(it.get("C_N", 0) or 0)
        L10h = calc_l10h(C, P, rpm)
        if L10h >= L10h_target:
            out = dict(it)
            out["L10h_pred"] = round2(L10h)
            out["margin_percent"] = round2((L10h - L10h_target) * 100.0 / max(L10h_target,1))
            cands.append(out)

    # sort by minimal oversize (closest to target)
    cands.sort(key=lambda x: x.get("L10h_pred", 0))
    return {"ok": True, "candidates": cands, "P_equiv_N": round2(P)}

def tool_verify_point(args):
    # Inputs: model (required), Fr_N/Fa_N, rpm, L10h_target (defaults allowed)
    model = args.get("model")
    b = _find_model(model)
    if not b:
        return {"ok": False, "error": f"model not found: {model}"}

    Fr = float(args.get("Fr_N", 0) or 0)
    Fa = float(args.get("Fa_N", 0) or 0)
    rpm = float(args.get("rpm", 1800) or 1800)
    L10h_target = float(args.get("L10h_target", 12000) or 12000)

    P = adjusted_P(Fr, Fa)
    L10h = calc_l10h(float(b.get("C_N",0)), P, rpm)
    res = {
        "ok": True,
        "model": b.get("model"),
        "type": b.get("type"),
        "C_N": b.get("C_N"),
        "d_mm": b.get("d_mm"), "D_mm": b.get("D_mm"), "B_mm": b.get("B_mm"),
        "P_equiv_N": round2(P),
        "L10h_pred": round2(L10h),
        "meets_target": bool(L10h >= L10h_target),
        "margin_percent": round2((L10h - L10h_target) * 100.0 / max(L10h_target,1))
    }
    return res

def main():
    while True:
        req = _read_frame()
        if req is None:
            return
        mid = req.get("id")
        m = req.get("method")
        if m == "initialize":
            resp = _ok(mid, {
                "protocolVersion": "2025-06-18",
                "tools": [
                    {"name": "select_bearing", "description": "Select bearing by loads"},
                    {"name": "verify_point",   "description": "Verify model at operating point"},
                    {"name": "catalog_list",   "description": "List catalog"}
                ]
            })
            _write_frame(resp)
            continue
        if m == "tools/call":
            name = (req.get("params") or {}).get("name")
            args = (req.get("params") or {}).get("arguments") or {}
            if name == "catalog_list":
                _write_frame(_ok(mid, tool_catalog_list(args))); continue
            if name == "select_bearing":
                _write_frame(_ok(mid, tool_select_bearing(args))); continue
            if name == "verify_point":
                _write_frame(_ok(mid, tool_verify_point(args))); continue
            _write_frame(_err(mid, -32601, f"unknown tool: {name}")); continue
        _write_frame(_err(mid))
        
if __name__ == "__main__":
    main()