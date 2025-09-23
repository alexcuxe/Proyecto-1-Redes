# client/remote_clients.py
# Simple HTTP JSON-RPC client for remote MCP server (Cloud Run)

import os, json, requests
from typing import Any, Dict

DEFAULT_TIMEOUT = 15.0

def _url() -> str:
    url = os.getenv("REMOTE_MCP_URL", "").strip()
    if not url:
        raise RuntimeError("REMOTE_MCP_URL not set. Example: https://remote-mcp-xxxx-uc.a.run.app/mcp")
    return url

def _post(payload: Dict[str, Any]) -> Dict[str, Any]:
    # basic HTTP POST
    r = requests.post(_url(), json=payload, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    return r.json()

def initialize() -> Dict[str, Any]:
    payload = {"jsonrpc": "2.0", "id": "cli", "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}
    return _post(payload).get("result", {})

def tools_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"jsonrpc": "2.0", "id": "cli", "method": "tools/call", "params": {"name": name, "arguments": arguments}}
    return _post(payload).get("result", {})

# Convenience wrappers
def remote_echo(text: str) -> Dict[str, Any]:
    return tools_call("echo", {"text": text})

def remote_time() -> Dict[str, Any]:
    return tools_call("time_now", {})

def remote_add(a: float, b: float) -> Dict[str, Any]:
    return tools_call("add", {"a": a, "b": b})
