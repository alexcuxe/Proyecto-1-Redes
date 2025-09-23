# Conversational console host for BearingPro-MCP.
# - Reads user messages (free text)
# - Detects intent (rule-based)
# - Calls MCP tools via StdioClient
# - Maintains simple context and logs
# - Uses Anthropic LLM for smalltalk/general Q&A with context (toggle on/off)
# - Can orchestrate official MCP servers (Filesystem/Git) via "crear repo" command

import json, time
from pathlib import Path
from typing import List, Dict, Any

from client.stdio_client import StdioClient
from host.intent import detect_intent

# LLM wrapper (Anthropic) is optional; we handle missing key gracefully
try:
    from host.llm_anthropic import LLMAnthropic
except Exception as _e:
    LLMAnthropic = None  # noqa

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
    # smalltalk fallback (will be overridden by LLM path in main)
    return {"jsonrpc":"2.0","id":"host","result":{
        "ok": True,
        "message": "Puedo ayudarte con selección/verificación de rodamientos o referencias SKF (Croesus)."
    }}

def try_run_repo_scenario():
    """
    Try to run the official MCP scenario:
      - git.init(path)
      - filesystem.write_file(path/README.md, content)
      - git.add(path)
      - git.commit(message)
    This requires you to have client/official_clients.py configured.
    """
    try:
        from client.official_clients import scenario_create_repo_with_readme
    except Exception as e:
        print("Host: no encontré el módulo oficial (client/official_clients.py).")
        print("      Añádelo y configura OFFICIAL_FS_CMD / OFFICIAL_GIT_CMD y config/official_tools_map.json.")
        print(f"      Detalle: {e}")
        return
    repo_path = input("Ruta de repo (ej. C:\\Temp\\mcp-demo-repo): ").strip()
    if not repo_path:
        print("Host: ruta inválida.")
        return
    content = input("Contenido README (una línea): ").strip() or "# Demo\n"
    try:
        scenario_create_repo_with_readme(repo_path, content)
        print("Host: escenario Filesystem/Git completado. Revisa el repo y el commit.")
    except Exception as e:
        print(f"Host: error en escenario: {e}")

def main():
    print("=== BearingPro-MCP · Chat en consola (con LLM) ===")
    print("Comandos: 'modo llm on/off' para alternar el LLM · 'crear repo' para demo Filesystem/Git · 'salir' para cerrar.")
    print("Tips: 'referencia skf de FAG 6205' · 'selección de rodamiento Fr=3500 Fa=1200 rpm=1800 L10h=12000' · 'verificar 6205 con Fr=.. rpm=..' · 'catálogo'.")

    # Contexts
    ctx_llm: List[Dict[str, str]] = []  # LLM history: [{"role":"user"/"assistant","content":...}]
    convo_log: List[Dict[str, Any]] = []  # MCP conversation turns (optional)

    # LLM setup
    use_llm = True
    llm = None
    if LLMAnthropic is not None:
        try:
            llm = LLMAnthropic()  # reads ANTHROPIC_API_KEY / ANTHROPIC_MODEL
        except Exception as e:
            print(f"(LLM deshabilitado: {e})")
            use_llm = False
    else:
        print("(LLM deshabilitado: falta host/llm_anthropic.py o dependencia.)")
        use_llm = False

    # MCP server (your local BearingPro-MCP) via stdio
    client = StdioClient()  # spawns the MCP server (main.py)

    try:
        while True:
            user = input("\nTú: ").strip()

            # Exit command
            if user.lower() in {"salir","exit","quit"}:
                print("Host: ¡Hasta luego!")
                break

            # Toggle LLM mode
            if user.lower() == "modo llm off":
                use_llm = False
                print("Host: LLM desactivado.")
                continue
            if user.lower() == "modo llm on":
                if llm is None and LLMAnthropic is not None:
                    try:
                        llm = LLMAnthropic()
                    except Exception as e:
                        print(f"Host: no pude activar el LLM: {e}")
                        continue
                use_llm = llm is not None
                print(f"Host: LLM {'activado' if use_llm else 'no disponible'}.")
                continue

            # Official MCP scenario (Filesystem + Git)
            if user.lower().startswith("crear repo"):
                try_run_repo_scenario()
                continue

            # Detect intent / params from free text
            d = detect_intent(user)
            intent, params, needs = d["intent"], d["params"], d["needs"]
            log(f"USER: {user}")
            log(f"INTENT: {intent} PARAMS: {params} NEEDS: {needs}")

            # Ask for missing params (simple prompt chain)
            if needs:
                print(f"Host: me falta {', '.join(needs)}. ¿Me lo das?")
                user2 = input("Tú: ").strip()
                d2 = detect_intent(user2)
                params.update(d2.get("params", {}))
                needs2 = [n for n in needs if n not in params]
                if needs2:
                    print(f"Host: aún me falta {', '.join(needs2)}. Intentemos de nuevo.")
                    log(f"MISSING_AFTER_PROMPT: {needs2}")
                    continue

            # If smalltalk/general Q&A, use the LLM (do not call MCP)
            if intent == "smalltalk":
                if use_llm and llm:
                    answer = llm.chat(ctx_llm, user)
                    print("Host (LLM):", answer)
                    ctx_llm.append({"role": "user", "content": user})
                    ctx_llm.append({"role": "assistant", "content": answer})
                    convo_log.append({"user": user, "intent": intent, "params": params, "resp": {"llm": answer}})
                    log(f"RESP(LLM): {pretty({'answer': answer})}")
                else:
                    print("Host: LLM no disponible. Activa 'modo llm on' tras configurar ANTHROPIC_API_KEY.")
                continue

            # Otherwise route to MCP tool
            resp = handle_intent(client, intent, params)

            # Normalize for display
            payload = resp["result"] if "result" in resp else resp

            # Concise outputs
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
                # Generic payload (errors, etc.)
                print("Host:", pretty(payload))

            # Save turn in MCP context and log
            convo_log.append({"user": user, "intent": intent, "params": params, "resp": payload})
            log(f"RESP: {pretty(payload)}")

    finally:
        # Ensure the stdio client (MCP server process) is closed
        try:
            client.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
