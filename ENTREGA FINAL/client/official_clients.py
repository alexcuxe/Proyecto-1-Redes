# client/official_clients.py
# Official MCP servers client using proper handshake:
#   initialize -> (optional notifications/initialized) -> tools/call

import os, json
from pathlib import Path
from typing import Dict, Any
from .stdio_client import StdioClient

MAP_PATH = Path("config") / "official_tools_map.json"
PROTO_VERSIONS = ["2025-06-18", "2024-11-05", "2024-10-07"]

def load_toolmap() -> Dict[str, Any]:
    if not MAP_PATH.exists():
        raise FileNotFoundError(f"Missing mapping file: {MAP_PATH}")
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))

def get_client_from_env(var_name: str) -> StdioClient:
    cmd = os.getenv(var_name)
    if not cmd:
        raise RuntimeError(f"{var_name} not set.")
    return StdioClient(server_cmd=cmd, timeout_sec=25.0)


PROTO_VERSIONS = ["2025-06-18", "2024-11-05", "2024-10-07"]

def get_client_from_env(var_name: str) -> StdioClient:
    cmd = os.getenv(var_name)
    if not cmd:
        raise RuntimeError(f"{var_name} not set.")
    return StdioClient(server_cmd=cmd, timeout_sec=60.0)

def do_initialize(c: StdioClient) -> dict:
    import time
    time.sleep(2.0)  # pequeña espera
    last_err = None
    init_params_base = {
        "clientInfo": {"name": "BearingProHost", "version": "0.1.0"},
        "capabilities": {"roots": {"listChanged": False}, "tools": {}},
        "roots": {"type": "list", "roots": []}
    }
    for ver in PROTO_VERSIONS:
        try:
            params = {"protocolVersion": ver, **init_params_base}
            resp = c.call("initialize", params)
            try:
                c.call("notifications/initialized", {})
            except Exception:
                pass
            return resp.get("result", resp)
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"initialize failed with all protocol versions {PROTO_VERSIONS}. Last error: {last_err}")


def tools_call(client: StdioClient, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    params = {"name": tool_name, "arguments": arguments}
    return client.call("tools/call", params)

def scenario_create_repo_with_readme(repo_path: str, readme_content: str):
    """
    Flujo exigido por la guía:
      - git_init(repo_path)
      - filesystem.write_file(path=repo/README.md, content=...)
      - git_add(repo_path, files=[README.md])
      - git_commit(repo_path, message="Initial commit")
    """
    mp = load_toolmap()

    # Git init
    gitc = get_client_from_env("OFFICIAL_GIT_CMD")
    try:
        do_initialize(gitc)
        t_init = mp["git"]["init"]["tool_name"]
        k_init = mp["git"]["init"]["arg_keys"]  # ["repo_path"]
        tools_call(gitc, t_init, {k_init[0]: repo_path})

        # Filesystem write README.md
        fsc = get_client_from_env("OFFICIAL_FS_CMD")
        try:
            do_initialize(fsc)
            t_wf = mp["filesystem"]["write_file"]["tool_name"]
            k_wf = mp["filesystem"]["write_file"]["arg_keys"]  # ["path","content"]
            from pathlib import Path
            readme_path = str(Path(repo_path) / "README.md")
            tools_call(fsc, t_wf, {k_wf[0]: readme_path, k_wf[1]: readme_content})
        finally:
            fsc.close()

        # Git add (⚠️ 'files' es un array de rutas relativas o absolutas)
        t_add = mp["git"]["add"]["tool_name"]
        k_add = mp["git"]["add"]["arg_keys"]  # ["repo_path","files"]
        tools_call(gitc, t_add, {k_add[0]: repo_path, k_add[1]: ["README.md"]})

        # Git commit
        t_commit = mp["git"]["commit"]["tool_name"]
        k_commit = mp["git"]["commit"]["arg_keys"]  # ["repo_path","message"]
        tools_call(gitc, t_commit, {k_commit[0]: repo_path, k_commit[1]: "Initial commit"})

    finally:
        gitc.close()

