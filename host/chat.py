# Conversational console host for BearingPro-MCP.
# - Reads user messages
# - Detects intent (rule-based)
# - Calls MCP tools via StdioClient
# - Maintains simple context and logs
# - Optional: later we can plug an LLM to paraphrase/ask clarifications

import json, time
from pathlib import Path
from typing import List, Dict, Any
from client.stdio_client import StdioClient
from host.intent import detect_intent

LOG_DIR = Path("logs"); LOG_DIR.mkdir(exist_ok=True)
CHAT_LOG = LOG_DIR / "chat.log"

def log(line: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    CHAT_LOG.open("a", encoding="utf-8").write(f"[{ts}] {line}\n")

def pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)

def handle_intent(client: StdioClient, intent: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Route intent to the right MCP method."""
    if intent == "croesus_xref":
        return client.call("croesus_xref", params)
    if intent == "select_bearing":
        return client.call("select_bearing", params)
    if intent == "verify_point":
        return client.call("verify_point", params)
    if intent == "catalog_list":
        return client.call("catalog_list", {})
    # smalltalk fallback
    return {"jsonrpc":"2.0","id":"host","result":{"ok":True,"message":"Puedo ayudarte con selección/verificación de rodamientos o referencias SKF (Croesus)."}}

def main():
    print("=== BearingPro-MCP · Chat en consola ===")
    print("Tips: pide 'referencia SKF de FAG 6205', 'selección de rodamiento Fr=3500 Fa=1200 rpm=1800 L10h=12000', 'verificar 6205 con Fr=.. rpm=..', 'catálogo'.")
    ctx: List[Dict[str, Any]] = []  # simple context list
    client = StdioClient()  # spawns the MCP server (main.py)

    try:
        while True:
            user = input("\nTú: ").strip()
            if user.lower() in {"salir","exit","quit"}:
                print("Host: ¡Hasta luego!")
                break

            # Detect intent and collect params
            d = detect_intent(user)
            intent, params, needs = d["intent"], d["params"], d["needs"]
            log(f"USER: {user}")
            log(f"INTENT: {intent} PARAMS: {params} NEEDS: {needs}")

            if needs:
                # Ask for missing info (no LLM yet; simple prompt chain)
                print(f"Host: me falta {', '.join(needs)}. ¿Me lo das?")
                # try to fill with next user turn
                user2 = input("Tú: ").strip()
                d2 = detect_intent(user2)
                # merge numeric/model/brand if provided
                params.update(d2.get("params", {}))
                needs2 = [n for n in needs if n not in params]
                if needs2:
                    print(f"Host: aún me falta {', '.join(needs2)}. Intentemos de nuevo.")
                    log(f"MISSING_AFTER_PROMPT: {needs2}")
                    continue

            # Call MCP tool
            resp = handle_intent(client, intent, params)
            # Normalize for display
            if "result" in resp:
                payload = resp["result"]
            else:
                payload = resp  # in case our fallback shape is already result-like

            # Show concise outputs
            if intent == "catalog_list" and payload.get("ok"):
                items = payload.get("items", [])
                print(f"Host: {len(items)} modelos en catálogo.")
                for it in items[:10]:
                    print(f"  - {it['model']} ({it['type']}) C={it['C_N']} N")
                if len(items) > 10:
                    print(f"  ... y {len(items)-10} más")
            elif intent == "select_bearing" and payload.get("ok"):
                cands = payload.get("candidates", [])
                if not cands:
                    print("Host: ningún candidato cumple el objetivo.")
                else:
                    print("Host: candidatos (top 5):")
                    for c in cands[:5]:
                        print(f"  - {c['model']} L10h={c['L10h_pred']}h margin={c['margin_percent']}%")
            elif intent == "verify_point" and payload.get("ok"):
                print(f"Host: {payload.get('model')} → L10h={payload.get('L10h_pred')}h")
                if "meets_target" in payload:
                    ok = "sí" if payload["meets_target"] else "no"
                    print(f"      ¿cumple objetivo? {ok}  (margen={payload.get('margin_percent','-')}%)")
            elif intent == "croesus_xref" and payload.get("ok"):
                hits = payload.get("hits", [])
                if not hits:
                    print("Host: no encontré referencias. Prueba otra marca/designación.")
                else:
                    print("Host: referencias (top 5):")
                    for h in hits[:5]:
                        print(f"  - {h.get('brand_code')} {h.get('non_skf_designation')} ⇒ SKF {h.get('skf_designation')} ({h.get('category')})")
            else:
                # print generic payload
                print("Host:", pretty(payload))

            # Keep turn in context
            ctx.append({"user": user, "intent": intent, "params": params, "resp": payload})
            log(f"RESP: {pretty(payload)}")

    finally:
        client.close()

if __name__ == "__main__":
    main()
