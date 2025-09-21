# rpc_handler.py
# Robust JSON-RPC 2.0 over STDIO with Content-Length framing (binary I/O).
# Works reliably on Windows (no newline translation issues).

import sys, json
from typing import Dict, Any, Callable, Optional

JSONRPC_VERSION = "2.0"

class StdioJsonRpcServer:
    def __init__(self, methods: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]], logger=None):
        self.methods = methods
        self.log = logger
        # Short hello line in log
        if self.log:
            self.log.info("Server started and waiting for requests...")

    def _readline_bytes(self) -> Optional[bytes]:
        """Read a single line (bytes) from stdin.buffer."""
        line = sys.stdin.buffer.readline()
        if line == b"":
            return None  # EOF
        return line

    def _read_message(self) -> Optional[str]:
        """
        Read one framed JSON message:
          Content-Length: <bytes>\r\n
          \r\n
          <body (exactly N bytes)>
        Returns decoded UTF-8 string, or None on EOF.
        """
        headers = {}
        # Read header lines until blank line
        while True:
            line = self._readline_bytes()
            if line is None:
                return None  # EOF
            # normalize line endings
            s = line.strip().decode("utf-8", errors="replace")
            if s == "":
                break  # end of headers
            if ":" in s:
                k, v = s.split(":", 1)
                headers[k.strip().lower()] = v.strip()
            else:
                # If someone sent raw JSON without headers:
                if s.startswith("{") or s.startswith("["):
                    # This is a compatibility fallback: treat as whole JSON line
                    return s

        # Parse content-length
        cl = headers.get("content-length")
        if cl is None:
            return None  # No content to read (ignore)
        try:
            n = int(cl)
        except ValueError:
            return None

        # Read exactly n bytes (loop until complete)
        remaining = n
        chunks = []
        while remaining > 0:
            chunk = sys.stdin.buffer.read(remaining)
            if not chunk:
                # EOF mid-body
                return None
            chunks.append(chunk)
            remaining -= len(chunk)

        body_bytes = b"".join(chunks)
        try:
            return body_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # If not UTF-8, try latin1 as a last resort (should not happen with JSON)
            return body_bytes.decode("latin-1", errors="replace")

    def _write_message(self, payload: dict):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
        sys.stdout.buffer.write(header)
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()

    def _err(self, _id, code: int, message: str):
        return {"jsonrpc": JSONRPC_VERSION, "id": _id, "error": {"code": code, "message": message}}

    def _ok(self, _id, result: dict):
        return {"jsonrpc": JSONRPC_VERSION, "id": _id, "result": result}

    def serve_forever(self):
        while True:
            raw = self._read_message()
            if raw is None:
                # EOF or invalid; stop server
                if self.log:
                    self.log.info("EOF or invalid frame. Exiting.")
                return
            try:
                req = json.loads(raw)
            except json.JSONDecodeError:
                if self.log:
                    self.log.warning("Received non-JSON payload.")
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
