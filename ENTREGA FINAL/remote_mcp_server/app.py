# app.py
# Minimal remote MCP-like server over HTTP JSON-RPC (Cloud Run friendly).

import json, datetime
from flask import Flask, request, make_response

app = Flask(__name__)

def jsonrpc_ok(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}

def jsonrpc_err(id_, code=-32601, msg="method not found"):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": msg}}

def tool_echo(args):
    # demo tool: echo the text
    return {"ok": True, "text": str(args.get("text", ""))}

def tool_time_now(_args):
    # demo tool: current server time
    return {"ok": True, "iso": datetime.datetime.utcnow().isoformat() + "Z"}

def tool_add(args):
    # demo tool: add a + b
    try:
        a = float(args.get("a", 0))
        b = float(args.get("b", 0))
        return {"ok": True, "sum": a + b}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.route("/mcp", methods=["POST"])
def mcp():
    try:
        req = request.get_json(force=True, silent=False)
    except Exception:
        return make_response({"error": "invalid json"}, 400)

    _id = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}

    if method == "initialize":
        result = {
            "protocolVersion": "2025-06-18",
            "tools": [
                {"name": "echo", "description": "Return back provided text"},
                {"name": "time_now", "description": "Current UTC time"},
                {"name": "add", "description": "Add two numbers a+b"}
            ]
        }
        return jsonrpc_ok(_id, result)

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name == "echo":
            return jsonrpc_ok(_id, tool_echo(args))
        if name == "time_now":
            return jsonrpc_ok(_id, tool_time_now(args))
        if name == "add":
            return jsonrpc_ok(_id, tool_add(args))
        return jsonrpc_err(_id, -32601, f"unknown tool: {name}")

    return jsonrpc_err(_id)

@app.route("/", methods=["GET"])
def health():
    return {"ok": True, "service": "remote-mcp", "status": "ready"}
