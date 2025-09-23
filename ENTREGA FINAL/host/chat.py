# host/chat.py
# Terminal UI with colors + menu (HCI-aware), planner, and MCP local/remote integration.
# - LLM on/off (Anthropic wrapper)
# - Planner mode (LLM proposes tool calls; host executes MCP)
# - Local BearingPro MCP (catalog/select/verify)
# - Remote MCP (Cloud Run demo: init/time/add)
# - Colors + menu + help + status line (UI/UX improvements)
#


import os, re, json, time
from pathlib import Path
from typing import List, Dict, Any

# LLM wrapper (optional)
try:
    from host.llm_anthropic import LLMAnthropic
except Exception:
    LLMAnthropic = None

# UI colors on Windows
try:
    import colorama
    colorama.just_fix_windows_console()
except Exception:
    pass


# Local MCP helpers (BearingPro)
from client.local_clients import bearingpro_select, bearingpro_verify, bearingpro_catalog

# Remote MCP helpers (Cloud Run)
from client.remote_clients import initialize as remote_init, remote_echo, remote_time, remote_add

LOG_DIR = Path("logs"); LOG_DIR.mkdir(exist_ok=True)
CHAT_LOG = LOG_DIR / "chat.log"

def log(line: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    CHAT_LOG.open("a", encoding="utf-8").write(f"[{ts}] {line}\n")

def pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)

# =========================
# Colors / Theme (HCI)
# =========================
ANSI = {
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    # Foreground
    "FG_BLACK": "\033[30m",
    "FG_RED": "\033[31m",
    "FG_GREEN": "\033[32m",
    "FG_YELLOW": "\033[33m",
    "FG_BLUE": "\033[34m",
    "FG_MAGENTA": "\033[35m",
    "FG_CYAN": "\033[36m",
    "FG_WHITE": "\033[37m",
}

THEMES = {
    "DARK": {
        "TITLE": ANSI["FG_CYAN"] + ANSI["BOLD"],
        "OK": ANSI["FG_GREEN"],
        "WARN": ANSI["FG_YELLOW"],
        "ERR": ANSI["FG_RED"] + ANSI["BOLD"],
        "INFO": ANSI["FG_BLUE"],
        "MUTED": ANSI["FG_MAGENTA"],
        "INPUT": ANSI["FG_CYAN"] + ANSI["BOLD"],
        "RESET": ANSI["RESET"],
    },
    "LIGHT": {
        "TITLE": ANSI["FG_BLUE"] + ANSI["BOLD"],
        "OK": ANSI["FG_GREEN"],
        "WARN": ANSI["FG_YELLOW"],
        "ERR": ANSI["FG_RED"] + ANSI["BOLD"],
        "INFO": ANSI["FG_CYAN"],
        "MUTED": ANSI["FG_MAGENTA"],
        "INPUT": ANSI["FG_BLUE"] + ANSI["BOLD"],
        "RESET": ANSI["RESET"],
    },
}

def c(txt: str, key: str) -> str:
    # color helper
    return THEME[key] + txt + THEME["RESET"]

# =========================
# Planner spec + prompts
# =========================
TOOLS_SPEC = {
    "tools": [
        {
            "name": "select_bearing",
            "description": "Select bearing candidates by loads",
            "args_schema": {"Fr_N": "float", "Fa_N": "float", "rpm": "float", "L10h_target": "float"}
        },
        {
            "name": "verify_point",
            "description": "Verify model at operating point",
            "args_schema": {"model":"string","Fr_N":"float","Fa_N":"float","rpm":"float","L10h_target":"float"}
        },
        {
            "name": "catalog_list",
            "description": "List catalog models",
            "args_schema": {}
        }
    ],
    "response_format": {"action":"call_tool|answer","tool":"name if call_tool","args":"object","text":"answer text"}
}

def planner_prompt(user_text: str) -> str:
    # LLM: propose a JSON plan to use tools when needed
    return (
        "Eres un asistente técnico. Usa herramientas cuando el usuario pida selección/verificación de rodamientos. "
        "Responde SIEMPRE con JSON válido: {\"action\":\"call_tool|answer\",\"tool\":\"...\",\"args\":{...},\"text\":\"...\"}. "
        "No inventes datos; si faltan parámetros, pide SOLO lo necesario. "
        f"TOOLS_SPEC={json.dumps(TOOLS_SPEC, ensure_ascii=False)} "
        f"USUARIO: {user_text}"
    )

def planner_observation_prompt(plan_json: dict, observation: dict) -> str:
    # LLM: produce final natural answer using the observation
    return (
        "Observación de tool (JSON abajo). Genera respuesta final breve y clara para el usuario (solo texto):\n"
        + json.dumps({"plan": plan_json, "observation": observation}, ensure_ascii=False)
    )

def try_parse_json(s: str):
    try:
        return json.loads(s)
    except Exception:
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
        # 2) Execute tool via local MCP
        if tool == "select_bearing":
            obs = bearingpro_select(args)
        elif tool == "verify_point":
            obs = bearingpro_verify(args)
        elif tool == "catalog_list":
            obs = bearingpro_catalog()
        else:
            obs = {"ok": False, "error": f"unknown tool requested: {tool}"}

        # 3) Feed observation back to LLM for final answer
        final_txt = llm.chat(ctx_llm + [{"role":"user","content": user_text}], planner_observation_prompt(plan, obs))
        return final_txt, {"plan": plan, "observation": obs}

    # If no call_tool, return direct answer
    return plan.get("text") or "(sin respuesta)", {"plan": plan}

# =========================
# Simple guided forms (HCI)
# =========================
def ask_float(prompt: str, default: float) -> float:
    # simple numeric question with default
    raw = input(c(f"{prompt} [{default}]: ", "INPUT")).strip()
    if not raw: return float(default)
    try:
        return float(raw)
    except:
        print(c("Valor inválido. Usaré el default.", "WARN"))
        return float(default)

def ask_text(prompt: str, default: str = "") -> str:
    raw = input(c(f"{prompt}{f' [{default}]' if default else ''}: ", "INPUT")).strip()
    return raw or default

def guided_selection():
    # Ask for selection parameters with defaults
    print(c("\nSelección guiada (valores por defecto entre corchetes):", "INFO"))
    Fr = ask_float("Fr (N)", 3500.0)
    Fa = ask_float("Fa (N)", 1200.0)
    rpm = ask_float("rpm", 1800.0)
    L10h = ask_float("L10h objetivo (h)", 12000.0)
    args = {"Fr_N": Fr, "Fa_N": Fa, "rpm": rpm, "L10h_target": L10h}
    out = bearingpro_select(args)
    return out

def guided_verify():
    print(c("\nVerificación guiada:", "INFO"))
    model = ask_text("Modelo (ej. SKF_6205)")
    Fr = ask_float("Fr (N)", 3000.0)
    Fa = ask_float("Fa (N)", 0.0)
    rpm = ask_float("rpm", 1800.0)
    L10h = ask_float("L10h objetivo (h)", 12000.0)
    args = {"model": model, "Fr_N": Fr, "Fa_N": Fa, "rpm": rpm, "L10h_target": L10h}
    out = bearingpro_verify(args)
    return out

# =========================
# UI: banner, status, menu, help
# =========================
def ui_banner():
    print(c("\n=== BearingPro · Chat MCP (UI mejorada) ===", "TITLE"))

def ui_status(use_llm: bool, planner_on: bool):
    remote = os.getenv("REMOTE_MCP_URL", "")
    bits = [
        ("LLM", "OK" if use_llm else "ERR"),
        ("Planner", "OK" if planner_on else "WARN"),
        ("Remoto", "OK" if bool(remote) else "WARN"),
    ]
    line = " | ".join([f"{k}: {c(v, 'OK' if v=='OK' else ('WARN' if v=='WARN' else 'ERR'))}" for k, v in bits])
    print(c("Estado:", "MUTED"), line)

def ui_menu():
    print(c("\nMenú rápido", "TITLE"))
    print("  1) Catálogo (local)")
    print("  2) Selección guiada (local)")
    print("  3) Verificación guiada (local)")
    print("  4) Remoto: init")
    print("  5) Remoto: hora")
    print("  6) Remoto: suma (a b)")
    print("  7) Planner ON/OFF (toggle)")
    print("  8) LLM ON/OFF (toggle)")
    print("  9) Ayuda")
    print("  0) Salir")

def ui_help():
    print(c("\nAyuda:", "TITLE"))
    print(c("Comandos directos:", "INFO"))
    print("- catálogo")
    print("- selección Fr=.. Fa=.. rpm=.. L10h=..")
    print("- verificar <modelo> con Fr=.. Fa=.. rpm=.. L10h=..")
    print("- remoto init | remoto hora | remoto suma A B")
    print("- modo planner on/off | modo llm on/off | tema oscuro | tema claro | menu | ayuda")
    print(c("\nAtajos:", "INFO"))
    print("1..9, 0 (ver Menú)")
    print(c("\nNotas HCI:", "MUTED"))
    print("- Colores consistentes: éxito/advertencia/error/info.")
    print("- Menú visible, atajos numéricos, feedback inmediato.")
    print("- Formularios guiados para reducir carga cognitiva y errores.")

def _parse_args_selection(text: str):
    get = lambda k, default=None: (re.search(rf"{k}\s*=\s*([0-9\.]+)", text, re.I) or [None,None])[1] or default
    args = {
        "Fr_N": float(get("fr", 0) or 0),
        "Fa_N": float(get("fa", 0) or 0),
        "rpm":  float(get("rpm", 1800) or 1800),
        "L10h_target": float(get("l10h", 12000) or 12000)
    }
    return args

def _parse_args_verify(text: str):
    m_model = re.search(r"verificar\s+([A-Za-z0-9_]+)", text, re.I)
    model = m_model.group(1) if m_model else None
    base = _parse_args_selection(text)
    base["model"] = model
    return base

def handle_bearing_selection(user_text: str):
    args = _parse_args_selection(user_text)
    return bearingpro_select(args)

def handle_bearing_verify(user_text: str):
    args = _parse_args_verify(user_text)
    need = []
    if not args.get("model"): need.append("model")
    if args.get("Fr_N", 0) == 0 and args.get("Fa_N", 0) == 0: need.append("Fr_N o Fa_N")
    if not args.get("rpm"): need.append("rpm")
    if need:
        return {"ok": False, "message": f"me falta {', '.join(need)}. ¿Me lo das?"}
    return bearingpro_verify(args)

# =========================
# Main
# =========================
THEME = THEMES["DARK"]  # default theme

def main():
    global THEME

    # LLM setup
    use_llm = True
    llm = None
    if LLMAnthropic is not None:
        try:
            llm = LLMAnthropic()
        except Exception as e:
            print(c(f"(LLM deshabilitado: {e})", "WARN"))
            use_llm = False
    else:
        print(c("(LLM deshabilitado: falta host/llm_anthropic.py o 'anthropic').", "WARN"))
        use_llm = False

    planner_on = False
    ctx_llm: List[Dict[str, str]] = []

    ui_banner()
    ui_status(use_llm, planner_on)
    ui_menu()
    print(c("\nEscribe un número (0–9) o un comando. 'ayuda' para más info.", "MUTED"))

    while True:
        user = input(c("\nTú: ", "INPUT")).strip()

        # Quick menu actions (shortcuts)
        if user == "0" or user.lower() in {"salir","exit","quit"}:
            print(c("Hasta luego 👋", "INFO"))
            break

        # Theme toggle
        if user.lower() == "tema oscuro":
            THEME = THEMES["DARK"]; ui_banner(); ui_status(use_llm, planner_on); continue
        if user.lower() == "tema claro":
            THEME = THEMES["LIGHT"]; ui_banner(); ui_status(use_llm, planner_on); continue

        # Show menu/help
        if user == "9" or user.lower() in {"ayuda","help"}:
            ui_help(); continue
        if user.lower() == "menu":
            ui_menu(); continue

        # Planner toggle
        if user == "7" or user.lower() == "modo planner on":
            planner_on = True; print(c("Planner activado.", "OK")); ui_status(use_llm, planner_on); continue
        if user.lower() == "modo planner off":
            planner_on = False; print(c("Planner desactivado.", "WARN")); ui_status(use_llm, planner_on); continue

        # LLM toggle
        if user == "8" or user.lower() == "modo llm on":
            if llm is None and LLMAnthropic is not None:
                try:
                    llm = LLMAnthropic()
                except Exception as e:
                    print(c(f"No pude activar LLM: {e}", "ERR"))
                    continue
            use_llm = llm is not None
            print(c(f"LLM {'activado' if use_llm else 'no disponible'}.", "INFO")); ui_status(use_llm, planner_on); continue
        if user.lower() == "modo llm off":
            use_llm = False; print(c("LLM desactivado.", "WARN")); ui_status(use_llm, planner_on); continue

        # Menu numeric actions
        if user == "1":
            out = bearingpro_catalog()
            print(c("Catálogo:", "INFO"), pretty(out)); log(f"RESP(BEARINGPRO.catalog): {pretty(out)}"); continue
        if user == "2":
            out = guided_selection()
            print(c("Selección:", "INFO"), pretty(out)); log(f"RESP(BEARINGPRO.select): {pretty(out)}"); continue
        if user == "3":
            out = guided_verify()
            print(c("Verificación:", "INFO"), pretty(out)); log(f"RESP(BEARINGPRO.verify): {pretty(out)}"); continue
        if user == "4":
            try:
                out = remote_init()
                print(c("Remoto init:", "INFO"), pretty(out)); log(f"RESP(REMOTE.init): {pretty(out)}")
            except Exception as e:
                print(c(f"Error remoto init: {e}", "ERR"))
            continue
        if user == "5":
            try:
                out = remote_time()
                print(c("Remoto hora:", "INFO"), pretty(out)); log(f"RESP(REMOTE.time): {pretty(out)}")
            except Exception as e:
                print(c(f"Error remoto hora: {e}", "ERR"))
            continue
        if user.startswith("6"):
            # Accept "6" or "6 3 4"
            parts = user.split()
            if len(parts) == 3:
                try:
                    a = float(parts[1]); b = float(parts[2])
                    out = remote_add(a, b)
                    print(c("Remoto suma:", "INFO"), pretty(out)); log(f"RESP(REMOTE.add): {pretty(out)}")
                except Exception as e:
                    print(c(f"Uso: 6 <a> <b> (ej. '6 3 4') | Error: {e}", "ERR"))
            else:
                print(c("Uso: 6 <a> <b> (ej. '6 3 4')", "WARN"))
            continue

        # Direct commands (compatibility with previous)
        if user.lower().startswith(("catalogo","catálogo","catalog","lista")):
            out = bearingpro_catalog()
            print(c("Catálogo:", "INFO"), pretty(out)); log(f"RESP(BEARINGPRO.catalog): {pretty(out)}"); continue
        if user.lower().startswith(("seleccion", "selección", "seleccionar")):
            out = handle_bearing_selection(user)
            print(c("Selección:", "INFO"), pretty(out)); log(f"RESP(BEARINGPRO.select): {pretty(out)}"); continue
        if user.lower().startswith(("verificar", "check", "validar")):
            out = handle_bearing_verify(user)
            print(c("Verificación:", "INFO"), pretty(out)); log(f"RESP(BEARINGPRO.verify): {pretty(out)}"); continue
        if user.lower().startswith(("remoto init","remote init","mcp remoto init")):
            try:
                out = remote_init()
                print(c("Remoto init:", "INFO"), pretty(out)); log(f"RESP(REMOTE.init): {pretty(out)}")
            except Exception as e:
                print(c(f"Error remoto init: {e}", "ERR"))
            continue
        if user.lower().startswith(("remoto hora","remoto time","remote time")):
            try:
                out = remote_time()
                print(c("Remoto hora:", "INFO"), pretty(out)); log(f"RESP(REMOTE.time): {pretty(out)}")
            except Exception as e:
                print(c(f"Error remoto hora: {e}", "ERR"))
            continue
        if user.lower().startswith(("remoto suma","remote add")):
            parts = user.split()
            try:
                a = float(parts[-2]); b = float(parts[-1])
                out = remote_add(a, b)
                print(c("Remoto suma:", "INFO"), pretty(out)); log(f"RESP(REMOTE.add): {pretty(out)}")
            except Exception:
                print(c("Uso: remoto suma 3 4", "WARN"))
            continue

        # Planner path: LLM decides and calls tools
        if planner_on and use_llm and llm:
            answer, dbg = run_planner_turn(llm, ctx_llm, user)
            print(c("Host (Planner):", "OK"), answer)
            log(f"USER: {user}")
            log(f"PLAN: {pretty(dbg.get('plan'))}")
            if 'observation' in dbg:
                log(f"OBS: {pretty(dbg['observation'])}")
            ctx_llm.append({"role":"user","content":user})
            ctx_llm.append({"role":"assistant","content":answer})
            continue

        # Default: small talk via LLM (if enabled)
        if use_llm and llm:
            answer = llm.chat(ctx_llm, user)
            print(c("Host (LLM):", "OK"), answer)
            ctx_llm.append({"role":"user","content":user})
            ctx_llm.append({"role":"assistant","content":answer})
            log(f"USER: {user}")
            log(f"RESP(LLM): {pretty({'answer': answer})}")
        else:
            print(c("LLM no disponible. Usa '8' o 'modo llm on' tras configurar ANTHROPIC_API_KEY.", "WARN"))

if __name__ == "__main__":
    main()
