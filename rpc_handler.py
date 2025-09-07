# Minimal JSON-RPC 2.0 over STDIO with Content-Length framing (LSP/MCP style).
# Focus: stability and clear errors; suitable for Windows and Linux.
import sys, json
from typing import Dict, Any, Callable, Optional

JSONRPC_VERSION = "2.0"

class StdioJsonRpcServer:
    def __init__(self, methods: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]], logger=None):
        self.methods = methods
        self.log = logger

    def _read_message(self) -> Optional[str]:
        """
        Read a single message using Content-Length framing.
        Fallback to single-line raw JSON if header not present.
        """
        headers = {}
        while True:
            line = sys.stdin.readline()
            if not line:
                return None  # EOF
            s = line.strip()
            if s == "":
                break
            if ":" in s:
                k, v = s.split(":", 1)
                headers[k.strip().lower()] = v.strip()
            if s.startswith("{") or s.startswith("["):
                # raw JSON single line
                return s

        length = headers.get("content-length")
        if length is None:
            return None
        try:
            n = int(length)
        except ValueError:
            return None
        body = sys.stdin.read(n)
        return body

    def _write_message(self, payload: dict):
        data = json.dumps(payload, ensure_ascii=False)
        out = f"Content-Length: {len(data.encode('utf-8'))}\r\n\r\n{data}"
        sys.stdout.write(out)
        sys.stdout.flush()

    def _err(self, _id, code: int, message: str):
        return {"jsonrpc": JSONRPC_VERSION, "id": _id, "error": {"code": code, "message": message}}

    def _ok(self, _id, result: dict):
        return {"jsonrpc": JSONRPC_VERSION, "id": _id, "result": result}

    def serve_forever(self):
        while True:
            raw = self._read_message()
            if raw is None:
                return  # EOF or invalid framing
            try:
                req = json.loads(raw)
            except json.JSONDecodeError:
                continue

            _id = req.get("id")
            method = req.get("method")
            params = req.get("params", {}) or {}

            if req.get("jsonrpc") != JSONRPC_VERSION:
                self._write_message(self._err(_id, -32600, "Invalid Request: jsonrpc must be '2.0'"))
                continue
            if method not in self.methods:
                self._write_message(self._err(_id, -32601, f"Method not found: {method}"))
                continue

            if self.log:
                self.log.info(f">>> {method} {params}")

            try:
                result = self.methods[method](params)
                if self.log:
                    self.log.info(f"<<< {method} OK")
                self._write_message(self._ok(_id, result))
            except Exception as ex:
                if self.log:
                    self.log.exception(f"Exception in method {method}")
                self._write_message(self._err(_id, -32603, "Internal error"))
