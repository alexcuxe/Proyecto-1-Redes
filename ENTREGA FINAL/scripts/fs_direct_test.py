# scripts/fs_direct_test.py
# Simple smoke test for the official Filesystem MCP server over stdio.
# It performs: initialize -> create_directory -> write_file -> list_directory

import os, time, json, sys
from client.stdio_client import StdioClient

PROTO_VERSIONS = ["2025-06-18", "2024-11-05", "2024-10-07"]

def do_initialize(c: StdioClient):
    init_params = {
        "clientInfo": {"name": "BearingProHost", "version": "0.1.0"},
        "capabilities": {"roots": {"listChanged": False}, "tools": {}},
        "roots": {"type": "list", "roots": []}
    }
    last = None
    for ver in PROTO_VERSIONS:
        try:
            resp = c.call("initialize", {"protocolVersion": ver, **init_params})
            try:
                c.call("notifications/initialized", {})
            except Exception:
                pass
            return resp.get("result", resp)
        except Exception as e:
            last = e
            continue
    raise RuntimeError(f"initialize failed: {last}")

def tools_call(c: StdioClient, name: str, arguments: dict):
    return c.call("tools/call", {"name": name, "arguments": arguments})

def main():
    cmd = os.getenv("OFFICIAL_FS_CMD")
    if not cmd:
        print("Set OFFICIAL_FS_CMD first.")
        sys.exit(1)

    # Ajusta este path a un directorio permitido en el comando
    base = os.getenv("FS_DEMO_DIR", r"C:\Temp\mcp_fs_demo")
    readme_path = os.path.join(base, "README.md")

    c = StdioClient(server_cmd=cmd, timeout_sec=60.0)
    try:
        time.sleep(2.0)  # pequeño margen a npx
        do_initialize(c)

        # 1) create_directory
        print("create_directory =>", base)
        r1 = tools_call(c, "create_directory", {"path": base})
        print("OK:", "result" in r1)

        # 2) write_file
        print("write_file =>", readme_path)
        r2 = tools_call(c, "write_file", {"path": readme_path, "content": "# Demo\nHola MCP Filesystem"})
        print("OK:", "result" in r2)

        # 3) list_directory
        print("list_directory =>", base)
        r3 = tools_call(c, "list_directory", {"path": base})
        print(json.dumps(r3, indent=2, ensure_ascii=False))

    finally:
        c.close()

if __name__ == "__main__":
    main()
