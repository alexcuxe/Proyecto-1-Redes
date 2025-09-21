# client/stdio_client.py
# Robust Windows-friendly JSON-RPC STDIO client that spawns the server by absolute path.
import json, subprocess, sys, threading, queue, os, shlex
from typing import Any, Dict, Optional
from pathlib import Path

class StdioClient:
    def __init__(self, server_cmd: Optional[str] = None, timeout_sec: float = 15.0):
        """
        - Launch server using absolute path to main.py
        - Set cwd to project root so imports and catalog paths resolve
        """
        self.timeout = timeout_sec
        base_dir = Path(__file__).resolve().parents[1]   # project root (where main.py should live)
        server_py = base_dir / "main.py"
        if not server_py.exists():
            raise FileNotFoundError(f"main.py not found at: {server_py}")

        if server_cmd is None:
            # Use current interpreter; Windows-safe quoting
            server_cmd = f'"{sys.executable}" "{server_py}"'

        # Start server process
        self.proc = subprocess.Popen(
            server_cmd if os.name == "nt" else shlex.split(server_cmd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(base_dir),          # <-- critical: run in project root
            shell=(os.name == "nt"),
            text=True, encoding="utf-8",
            bufsize=0
        )

        # Queues for stdout/stderr
        self._out_q = queue.Queue()
        self._err_q = queue.Queue()

        # Readers
        self._reader_out = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader_err = threading.Thread(target=self._read_stderr, daemon=True)
        self._reader_out.start()
        self._reader_err.start()

    def _read_stdout(self):
        # Read MCP-style framing (Content-Length) or raw JSON line
        while True:
            line = self.proc.stdout.readline()
            if not line:
                return
            s = line.strip()
            if s.startswith("{") or s.startswith("["):
                self._out_q.put(s)
                continue

            headers = {}
            if ":" in s:
                headers[s.split(":",1)[0].lower()] = s.split(":",1)[1].strip()
                # Read rest of headers
                while True:
                    l2 = self.proc.stdout.readline()
                    if not l2 or l2.strip() == "":
                        break
                    k,v = l2.split(":",1)
                    headers[k.strip().lower()] = v.strip()
                try:
                    length = int(headers.get("content-length","0"))
                except ValueError:
                    length = 0
                body = self.proc.stdout.read(length) if length > 0 else ""
                if body:
                    self._out_q.put(body)

    def _read_stderr(self):
        for line in self.proc.stderr:
            self._err_q.put(line.rstrip())

    def _drain_stderr(self) -> str:
        # Collect any stderr lines
        lines = []
        try:
            while True:
                lines.append(self._err_q.get_nowait())
        except queue.Empty:
            pass
        return "\n".join(lines)

    def call(self, method: str, params: Dict[str, Any]):
        # Build and send framed request
        req = {"jsonrpc":"2.0","id":"cli","method":method,"params":params}
        data = json.dumps(req, ensure_ascii=False)
        frame = f"Content-Length: {len(data.encode('utf-8'))}\r\n\r\n{data}"
        try:
            self.proc.stdin.write(frame)
            self.proc.stdin.flush()
        except Exception as e:
            err = self._drain_stderr()
            raise RuntimeError(f"Failed to write to server stdin: {e}\nServer stderr:\n{err}")

        # Wait for response or server crash
        try:
            resp = self._out_q.get(timeout=self.timeout)
        except queue.Empty:
            # If server died, surface stderr to help debugging
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
