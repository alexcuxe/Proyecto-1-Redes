# client/stdio_client.py
# Robust stdio JSON-RPC client that can spawn a server subprocess (Windows-friendly).

import json, subprocess, sys, threading, queue, os, shlex
from typing import Any, Dict, Optional
from pathlib import Path

class StdioClient:
    def __init__(self, server_cmd: Optional[str] = None, timeout_sec: float = 15.0):
        """
        Launch server by absolute path or custom command.
        - If server_cmd is None: default to run main.py in repo root (your local MCP server).
        - For official servers: pass the command via env and pass it here.
        """
        self.timeout = timeout_sec
        self.base_dir = Path.cwd()
        # If no explicit command, assume main.py in project root (optional in v2)
        if server_cmd is None:
            server_py = self.base_dir / "main.py"
            if not server_py.exists():
                raise FileNotFoundError(f"main.py not found at: {server_py}")
            server_cmd = f'"{sys.executable}" "{server_py}"'

        self.proc = subprocess.Popen(
            server_cmd if os.name == "nt" else shlex.split(server_cmd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self.base_dir),
            shell=(os.name == "nt"),
            text=False,  # binary I/O
            bufsize=0
        )

        self._out_q = queue.Queue()
        self._err_q = queue.Queue()
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _readline_bytes(self) -> Optional[bytes]:
        line = self.proc.stdout.readline()
        if line == b"":
            return None
        return line

    def _read_stdout(self):
        while True:
            # Read headers until blank line
            headers = {}
            line = self._readline_bytes()
            if line is None:
                return
            s = line.strip().decode("utf-8", errors="replace")
            if s.startswith("{") or s.startswith("["):
                self._out_q.put(s)
                continue
            if ":" in s:
                k, v = s.split(":", 1)
                headers[k.strip().lower()] = v.strip()
                # read remaining headers
                while True:
                    l2 = self._readline_bytes()
                    if l2 is None:
                        return
                    if l2.strip() == b"":
                        break
                    k2, v2 = l2.decode("utf-8", errors="replace").split(":", 1)
                    headers[k2.strip().lower()] = v2.strip()
                try:
                    length = int(headers.get("content-length", "0"))
                except ValueError:
                    length = 0
                body = self.proc.stdout.read(length) if length > 0 else b""
                if body:
                    self._out_q.put(body.decode("utf-8", errors="replace"))

    def _read_stderr(self):
        while True:
            data = self.proc.stderr.readline()
            if not data:
                return
            try:
                self._err_q.put(data.decode("utf-8", errors="replace").rstrip())
            except Exception:
                self._err_q.put(repr(data))

    def _drain_stderr(self) -> str:
        lines = []
        try:
            while True:
                lines.append(self._err_q.get_nowait())
        except queue.Empty:
            pass
        return "\n".join(lines)

    def call(self, method: str, params: Dict[str, Any]):
        req = {"jsonrpc":"2.0","id":"cli","method":method,"params":params}
        data = json.dumps(req, ensure_ascii=False).encode("utf-8")
        # ⬇⬇⬇ AÑADIR Content-Type
        header = (
            b"Content-Length: " + str(len(data)).encode("ascii") + b"\r\n"
            b"Content-Type: application/json\r\n"
            b"\r\n"
        )
        frame = header + data
        try:
            self.proc.stdin.write(frame)
            self.proc.stdin.flush()
        except Exception as e:
            err = self._drain_stderr()
            raise RuntimeError(f"Failed to write to server stdin: {e}\nServer stderr:\n{err}")

        try:
            resp = self._out_q.get(timeout=self.timeout)
        except queue.Empty:
            code = self.proc.poll()
            err = self._drain_stderr()
            if code is not None:
                raise RuntimeError(f"Server exited (code={code}). Stderr:\n{err}")
            raise TimeoutError(f"No response within {self.timeout}s. Stderr so far:\n{err}")

        return json.loads(resp)


    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass