# scripts/discover_official_tools.py
# List MCP tools exposed by an official server (Filesystem or Git) via tools/list.
# It prints each tool's name, description, and input schema (properties/required).
# Usage (Windows CMD):
#   set OFFICIAL_FS_CMD=...   (your filesystem server command)
#   set OFFICIAL_GIT_CMD=...  (your git server command)
#   py -m scripts.discover_official_tools --server fs
#   py -m scripts.discover_official_tools --server git

import os, argparse, json
from typing import Dict, Any
from pathlib import Path

# Reuse your stdio client
from client.stdio_client import StdioClient

def discover(server_cmd: str) -> Dict[str, Any]:
    """Start server, call tools/list, return the result dict."""
    c = StdioClient(server_cmd=server_cmd)
    try:
        # Standard MCP discovery call
        resp = c.call("tools/list", {})
        # Some servers return {"result": {...}} others inline; normalize
        return resp.get("result", resp)
    finally:
        c.close()

def pretty(d: Any) -> str:
    return json.dumps(d, indent=2, ensure_ascii=False)

def print_tools(data: Dict[str, Any]):
    # Expecting something like: {"tools": [ { "name": "...", "description": "...",
    #   "inputSchema": { "type":"object", "properties": {...}, "required": [...] } }, ... ] }
    tools = data.get("tools") or data.get("result") or []
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
                tpe = v.get("type")
                print(f"  - {k}: type={tpe}  (details: {json.dumps(v, ensure_ascii=False)})")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", choices=["fs","git"], required=True, help="Which official server to probe")
    args = ap.parse_args()

    if args.server == "fs":
        cmd = os.getenv("OFFICIAL_FS_CMD")
        if not cmd:
            raise SystemExit("OFFICIAL_FS_CMD not set. Example: set OFFICIAL_FS_CMD=npx @modelcontextprotocol/server-filesystem")
    else:
        cmd = os.getenv("OFFICIAL_GIT_CMD")
        if not cmd:
            raise SystemExit("OFFICIAL_GIT_CMD not set. Example: set OFFICIAL_GIT_CMD=npx @modelcontextprotocol/server-git")

    data = discover(cmd)
    print_tools(data)

if __name__ == "__main__":
    main()
