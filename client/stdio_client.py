# Simple JSON-RPC STDIO client that spawns the server as a subprocess on Windows/Linux.
import json, subprocess, sys, threading, queue, os, shlex
from typing import Any, Dict

class StdioClient:
    def __init__(self, server_cmd: str = None):
        # Use current interpreter to run main.py
        if server_cmd is None:
            # Windows-friendly command: py main.py
            server_cmd = f'"{sys.executable}" main.py'
        self.proc = subprocess.Popen(
            server_cmd if os.name == "nt" else shlex.split(server_cmd),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=(os.name == "nt"), text=True, encoding="utf-8", bufsize=0
        )
        self._out_q = queue.Queue()
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

    def _read_stdout(self):
        # Read headers then body by Content-Length
        while True:
            line = self.proc.stdout.readline()
            if not line:
                return
            line_s = line.strip()
            if line_s.startswith("{") or line_s.startswith("["):
                self._out_q.put(line_s)
                continue
            headers = {}
            if ":" in line_s:
                # Read header block
                headers[line_s.split(":",1)[0].lower()] = line_s.split(":",1)[1].strip()
                while True:
                    l2 = self.proc.stdout.readline()
                    if not l2 or l2.strip() == "":
                        break
                    k,v = l2.split(":",1)
                    headers[k.strip().lower()] = v.strip()
                length = int(headers.get("content-length","0"))
                body = self.proc.stdout.read(length)
                self._out_q.put(body)

    def call(self, method: str, params: Dict[str, Any]):
        req = {"jsonrpc":"2.0","id":"cli","method":method,"params":params}
        data = json.dumps(req, ensure_ascii=False)
        out = f"Content-Length: {len(data.encode('utf-8'))}\r\n\r\n{data}"
        self.proc.stdin.write(out)
        self.proc.stdin.flush()
        resp = self._out_q.get(timeout=5)
        return json.loads(resp)

    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass
