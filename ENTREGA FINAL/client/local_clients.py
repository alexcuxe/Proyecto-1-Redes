# client/local_clients.py
# Generic local MCP client over stdio for custom servers (e.g., BearingPro)

from typing import Any, Dict
import time, os
from .stdio_client import StdioClient

PROTO_VERSIONS = ["2025-06-18", "2024-11-05", "2024-10-07"]

def _init(c: StdioClient) -> dict:
    # Basic MCP-like initialize
    time.sleep(0.8)  # small wait for startup
    init_params = {
        "clientInfo": {"name": "BearingProHost", "version": "0.1.0"},
        "capabilities": {"tools": {}, "roots": {"listChanged": False}},
        "roots": {"type": "list", "roots": []}
    }
    last = None
    for ver in PROTO_VERSIONS:
        try:
            resp = c.call("initialize", {"protocolVersion": ver, **init_params})
            return resp.get("result", resp)
        except Exception as e:
            last = e
            continue
    raise RuntimeError(f"initialize failed: {last}")

def tools_call(c: StdioClient, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    return c.call("tools/call", {"name": name, "arguments": arguments})

# Convenience API for BearingPro
def bearingpro_client_from_env() -> StdioClient:
    cmd = os.getenv("BEARINGPRO_CMD")
    if not cmd:
        raise RuntimeError("BEARINGPRO_CMD not set. Example: python local_servers/bearingpro/main.py")
    return StdioClient(server_cmd=cmd, timeout_sec=30.0)

def bearingpro_select(args: Dict[str, Any]) -> Dict[str, Any]:
    c = bearingpro_client_from_env()
    try:
        _init(c)
        return tools_call(c, "select_bearing", args).get("result", {})
    finally:
        c.close()

def bearingpro_verify(args: Dict[str, Any]) -> Dict[str, Any]:
    c = bearingpro_client_from_env()
    try:
        _init(c)
        return tools_call(c, "verify_point", args).get("result", {})
    finally:
        c.close()

def bearingpro_catalog() -> Dict[str, Any]:
    c = bearingpro_client_from_env()
    try:
        _init(c)
        return tools_call(c, "catalog_list", {}).get("result", {})
    finally:
        c.close()
