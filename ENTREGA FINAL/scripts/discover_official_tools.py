# scripts/discover_official_tools.py
import os, argparse, json, time
from client.stdio_client import StdioClient

PROTO_VERSIONS = ["2025-06-18", "2024-11-05", "2024-10-07"]

def do_initialize(c: StdioClient) -> dict:
    last_err = None
    init_params_base = {
        "clientInfo": {"name": "BearingProHost", "version": "0.1.0"},
        "capabilities": {
            "roots": {"listChanged": False},  # declare we handle roots notifications (optional)
            "tools": {}                       # generic
        },
        # Si el server ignora roots cuando se pasan dirs por CLI, igual no molesta
        "roots": {
            "type": "list",
            "roots": []
        }
    }
    for ver in PROTO_VERSIONS:
        try:
            params = {"protocolVersion": ver, **init_params_base}
            resp = c.call("initialize", params)
            try:
                c.call("notifications/initialized", {})
            except Exception:
                pass
            return resp.get("result", resp)
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"initialize failed with all protocol versions {PROTO_VERSIONS}. Last error: {last_err}")

def discover(server_cmd: str):
    # timeout amplio por npx/arranque
    c = StdioClient(server_cmd=server_cmd, timeout_sec=60.0)
    try:
        # pequeña espera para que el server termine de levantar
        time.sleep(3.0)
        do_initialize(c)
        resp = c.call("tools/list", {})
        return resp.get("result", resp)
    finally:
        c.close()

def pretty(d): return json.dumps(d, indent=2, ensure_ascii=False)

def print_tools(data):
    tools = data.get("tools") or []
    if not tools:
        print("No tools found or unexpected payload:\n", pretty(data))
        return
    for t in tools:
        name = t.get("name")
        desc = t.get("description", "")
        schema = t.get("inputSchema") or {}
        props = (schema.get("properties") or {})
        req = schema.get("required") or []
        print(f"\n=== TOOL: {name} ===")
        print(f"desc: {desc}")
        print("required:", req)
        if props:
            print("properties:")
            for k, v in props.items():
                print(f"  - {k}: type={v.get('type')} details={json.dumps(v, ensure_ascii=False)}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", choices=["fs","git"], required=True)
    args = ap.parse_args()

    if args.server == "fs":
        cmd = os.getenv("OFFICIAL_FS_CMD")
        if not cmd: raise SystemExit("OFFICIAL_FS_CMD not set.")
    else:
        cmd = os.getenv("OFFICIAL_GIT_CMD")
        if not cmd: raise SystemExit("OFFICIAL_GIT_CMD not set.")

    data = discover(cmd)
    print_tools(data)

if __name__ == "__main__":
    main()
