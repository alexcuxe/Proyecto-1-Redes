# host/chat.py
# Conversational console host:
# - Uses Anthropic LLM for general Q&A with context (toggle on/off)
# - Orchestrates official servers scenario "crear repo" (Filesystem + Git)
# - Logs conversation to logs/chat.log

import json, time, os
from pathlib import Path
from typing import List, Dict, Any
# ADD: planner helpers and MCP local clients
import re, json
from client.local_clients import bearingpro_select, bearingpro_verify, bearingpro_catalog
# ADD: remote MCP client
from client.remote_clients import initialize as remote_init, remote_echo, remote_time, remote_add


# LLM wrapper
try:
    from host.llm_anthropic import LLMAnthropic
except Exception:
    LLMAnthropic = None  # if not installed

LOG_DIR = Path("logs"); LOG_DIR.mkdir(exist_ok=True)
CHAT_LOG = LOG_DIR / "chat.log"

def log(line: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    CHAT_LOG.open("a", encoding="utf-8").write(f"[{ts}] {line}\n")

def pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)

def try_run_repo_scenario():
    """Run official Filesystem/Git scenario via official_clients."""
    try:
        from client.official_clients import scenario_create_repo_with_readme
    except Exception as e:
        print("Host: falta client/official_clients.py o config/env. Detalle:", e)
        return
    repo_path = input("Ruta de repo (ej. C:\\Temp\\mcp-demo-repo): ").strip()
    if not repo_path:
        print("Host: ruta inválida."); return
    content = input("Contenido README (una línea): ").strip() or "# Demo\n"
    try:
        scenario_create_repo_with_readme(repo_path, content)
        print("Host: escenario completado. Revisa el repo y el commit.")
    except Exception as e:
        print("Host: error en escenario:", e)


def _parse_args_selection(text: str):
    # very simple key=value parser, english comments are basic
    # ex: "selección Fr=3500 Fa=1200 rpm=1800 L10h=12000"
    get = lambda k, default=None: (re.search(rf"{k}\s*=\s*([0-9\.]+)", text, re.I) or [None,None])[1] or default
    args = {
        "Fr_N": float(get("fr", 0) or 0),
        "Fa_N": float(get("fa", 0) or 0),
        "rpm":  float(get("rpm", 1800) or 1800),
        "L10h_target": float(get("l10h", 12000) or 12000)
    }
    return args

def _parse_args_verify(text: str):
    # ex: "verificar 6205 con Fr=3000 rpm=1800"
    m_model = re.search(r"verificar\s+([A-Za-z0-9_]+)", text, re.I)
    model = m_model.group(1) if m_model else None
    base = _parse_args_selection(text)
    base["model"] = model
    return base

def handle_bearing_selection(user_text: str):
    # call local MCP select_bearing
    args = _parse_args_selection(user_text)
    res = bearingpro_select(args)
    return res

def handle_bearing_verify(user_text: str):
    # call local MCP verify_point
    args = _parse_args_verify(user_text)
    need = []
    if not args.get("model"): need.append("model")
    if args.get("Fr_N", 0) == 0 and args.get("Fa_N", 0) == 0: need.append("Fr_N o Fa_N")
    if not args.get("rpm"): need.append("rpm")
    if need:
        # short prompt for missing inputs
        return {"ok": False, "message": f"me falta {', '.join(need)}. ¿Me lo das?"}
    res = bearingpro_verify(args)
    return res





# === Planner spec: tools the LLM may use ===
TOOLS_SPEC = {
    "tools": [
        {
            "name": "select_bearing",
            "description": "Select bearing candidates by loads",
            "args_schema": {
                "Fr_N": "float (radial load, N)",
                "Fa_N": "float (axial load, N)",
                "rpm": "float (speed)",
                "L10h_target": "float (target life in hours)"
            }
        },
        {
            "name": "verify_point",
            "description": "Verify model at operating point",
            "args_schema": {
                "model": "string (e.g. SKF_6205)",
                "Fr_N": "float",
                "Fa_N": "float",
                "rpm": "float",
                "L10h_target": "float"
            }
        },
        {
            "name": "catalog_list",
            "description": "List catalog models",
            "args_schema": {}
        }
    ],
    "response_format": {
        "action": "call_tool | answer",
        "tool": "name when action=call_tool",
        "args": "object with tool args",
        "text": "final message to user when action=answer"
    }
}

def planner_prompt(user_text: str) -> str:
    # Keep prompt short and deterministic
    return (
        "Eres un asistente técnico. Dispones de herramientas (tools) que debes usar "
        "cuando el usuario pida selección o verificación de rodamientos. "
        "Responde SIEMPRE con un JSON válido con este esquema:\n"
        '{"action":"call_tool|answer","tool":"...","args":{...},"text":"..."}\n'
        "Si necesitas datos del catálogo o cálculos, usa una tool. "
        "No inventes datos. Si faltan parámetros, pide SOLO lo necesario.\n"
        f"TOOLS_SPEC={json.dumps(TOOLS_SPEC, ensure_ascii=False)}\n"
        f"USUARIO: {user_text}"
    )

def planner_observation_prompt(plan_json: dict, observation: dict) -> str:
    # Feed tool result back for final answer
    return (
        "Observación de tool (resultado JSON a continuación). "
        "Ahora produce una respuesta final breve y clara para el usuario, "
        "sin JSON, solo texto. Observación:\n"
        + json.dumps({"plan": plan_json, "observation": observation}, ensure_ascii=False)
    )

def try_parse_json(s: str):
    try:
        return json.loads(s)
    except Exception:
        # try to find first JSON object
        import re
        m = re.search(r"\{.*\}", s, re.S)
        if m:
            try: return json.loads(m.group(0))
            except Exception: pass
    return None





def run_planner_turn(llm, ctx_llm, user_text: str):
    # 1) Ask LLM for a plan
    plan_txt = llm.chat(ctx_llm, planner_prompt(user_text))
    plan = try_parse_json(plan_txt) or {"action": "answer", "text": plan_txt}

    if plan.get("action") == "call_tool":
        tool = (plan.get("tool") or "").strip()
        args = plan.get("args") or {}
        # 2) Execute requested tool via local MCP
        if tool == "select_bearing":
            obs = bearingpro_select(args)
        elif tool == "verify_point":
            obs = bearingpro_verify(args)
        elif tool == "catalog_list":
            obs = bearingpro_catalog()
        else:
            obs = {"ok": False, "error": f"unknown tool requested: {tool}"}

        # 3) Feed observation back to LLM for final natural answer
        final_txt = llm.chat(ctx_llm + [{"role":"user","content": user_text}], planner_observation_prompt(plan, obs))
        return final_txt, {"plan": plan, "observation": obs}

    # If action == answer, return as-is
    return plan.get("text") or "(sin respuesta)", {"plan": plan}



def main():
    print("=== BearingPro-MCP · Chat en consola ===")
    print("Tips: 'catálogo' · 'selección Fr=3500 Fa=1200 rpm=1800 L10h=12000' · 'verificar 6205 con Fr=.. rpm=..'.")
    print("Comandos: 'modo llm on/off' · 'modo planner on/off' · 'salir'")


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
        print("(LLM deshabilitado: falta host/llm_anthropic.py o 'anthropic').")
        use_llm = False

    # LLM context
    ctx_llm: List[Dict[str, str]] = []

    planner_on = False


    while True:
        user = input("\nTú: ").strip()
        if user.lower() in {"salir","exit","quit"}:
            print("Host: ¡Hasta luego!")
            break

        if user.lower() == "modo llm off":
            use_llm = False
            print("Host: LLM desactivado.")
            continue
        if user.lower() == "modo llm on":
            if llm is None and LLMAnthropic is not None:
                try:
                    llm = LLMAnthropic()
                except Exception as e:
                    print(f"No pude activar LLM: {e}")
                    continue
            use_llm = llm is not None
            print(f"Host: LLM {'activado' if use_llm else 'no disponible'}.")
            continue


        # Planner toggle
        if user.lower() == "modo planner on":
            planner_on = True
            print("Host: planificador activado (LLM orquesta MCP).")
            continue
        if user.lower() == "modo planner off":
            planner_on = False
            print("Host: planificador desactivado.")
            continue


        if user.lower().startswith("crear repo"):
            try_run_repo_scenario()
            continue


        # BearingPro: catálogo
        if user.lower().startswith(("catalogo","catálogo","catalog","lista")):
            out = bearingpro_catalog()
            print("Host:", json.dumps(out, ensure_ascii=False, indent=2))
            log(f"RESP(BEARINGPRO.catalog): {pretty(out)}")
            continue

        # BearingPro: selección
        if user.lower().startswith(("seleccion", "selección", "seleccionar")):
            out = handle_bearing_selection(user)
            print("Host:", json.dumps(out, ensure_ascii=False, indent=2))
            log(f"RESP(BEARINGPRO.select): {pretty(out)}")
            continue

        # BearingPro: verificación
        if user.lower().startswith(("verificar", "check", "validar")):
            out = handle_bearing_verify(user)
            print("Host:", json.dumps(out, ensure_ascii=False, indent=2))
            log(f"RESP(BEARINGPRO.verify): {pretty(out)}")
            continue



        # Planner path: LLM decides tools -> host calls MCP -> LLM final answer
        if planner_on and use_llm and llm:
            answer, dbg = run_planner_turn(llm, ctx_llm, user)
            print("Host (Planner):", answer)
            # log + context
            log(f"USER: {user}")
            log(f"PLAN: {pretty(dbg.get('plan'))}")
            if 'observation' in dbg:
                log(f"OBS: {pretty(dbg['observation'])}")
            ctx_llm.append({"role":"user","content":user})
            ctx_llm.append({"role":"assistant","content":answer})
            continue


                # Remote MCP: initialize
        if user.lower().startswith(("remoto init","remote init","mcp remoto init")):
            try:
                out = remote_init()
                print("Host (Remote):", json.dumps(out, ensure_ascii=False, indent=2))
                log(f"RESP(REMOTE.init): {pretty(out)}")
            except Exception as e:
                print("Host (Remote): error ->", e)
            continue

        # Remote MCP: echo
        if user.lower().startswith(("remoto echo","remote echo")):
            txt = user.split(" ", 2)[-1] if " " in user else ""
            out = remote_echo(txt)
            print("Host (Remote):", json.dumps(out, ensure_ascii=False, indent=2))
            log(f"RESP(REMOTE.echo): {pretty(out)}")
            continue

        # Remote MCP: time
        if user.lower().strip() in {"remoto hora","remoto time","remote time"}:
            out = remote_time()
            print("Host (Remote):", json.dumps(out, ensure_ascii=False, indent=2))
            log(f"RESP(REMOTE.time): {pretty(out)}")
            continue

        # Remote MCP: add
        if user.lower().startswith(("remoto suma","remote add")):
            # expected pattern: "remoto suma 3 4"
            parts = user.split()
            try:
                a = float(parts[-2]); b = float(parts[-1])
            except Exception:
                print("Host (Remote): usa 'remoto suma 3 4'")
                continue
            out = remote_add(a, b)
            print("Host (Remote):", json.dumps(out, ensure_ascii=False, indent=2))
            log(f"RESP(REMOTE.add): {pretty(out)}")
            continue




        # Default path: smalltalk/general QA via LLM
        if use_llm and llm:
            answer = llm.chat(ctx_llm, user)
            print("Host (LLM):", answer)
            ctx_llm.append({"role":"user","content":user})
            ctx_llm.append({"role":"assistant","content":answer})
            log(f"USER: {user}")
            log(f"RESP(LLM): {pretty({'answer': answer})}")
        else:
            print("Host: LLM no disponible. Usa 'modo llm on' tras configurar ANTHROPIC_API_KEY.")

if __name__ == "__main__":
    main()
