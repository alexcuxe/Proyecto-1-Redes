# client/official_clients.py
# Generic caller for official MCP servers (Filesystem / Git) via STDIO.
# Reads server commands from environment variables and method mapping from JSON.
# Designed to be launched from host.chat ("crear repo") or standalone.

import os, json
from pathlib import Path
from typing import Dict, Any
from .stdio_client import StdioClient  # your existing stdio JSON-RPC client

MAP_PATH = Path("config") / "official_tools_map.json"

def load_toolmap() -> Dict[str, Any]:
    """Load JSON mapping of official tool methods and param names."""
    if not MAP_PATH.exists():
        raise FileNotFoundError(f"Missing mapping file: {MAP_PATH}")
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))

def get_fs_client() -> StdioClient:
    """
    Start the official Filesystem MCP server as a subprocess over stdio.
    Command is taken from env var OFFICIAL_FS_CMD.
    Example (you must adjust to README):
      OFFICIAL_FS_CMD="npx @modelcontextprotocol/server-filesystem"
    """
    cmd = os.getenv("OFFICIAL_FS_CMD")
    if not cmd:
        raise RuntimeError("OFFICIAL_FS_CMD not set. Define it in your environment.")
    return StdioClient(server_cmd=cmd)

def get_git_client() -> StdioClient:
    """
    Start the official Git MCP server as a subprocess over stdio.
    Command is taken from env var OFFICIAL_GIT_CMD.
    Example (you must adjust to README):
      OFFICIAL_GIT_CMD="npx @modelcontextprotocol/server-git"
    """
    cmd = os.getenv("OFFICIAL_GIT_CMD")
    if not cmd:
        raise RuntimeError("OFFICIAL_GIT_CMD not set. Define it in your environment.")
    return StdioClient(server_cmd=cmd)

def call_tool(client: StdioClient, method: str, params: Dict[str, Any]):
    """Send a generic JSON-RPC request using our stdio client."""
    return client.call(method, params)

def scenario_create_repo_with_readme(repo_path: str, readme_content: str):
    """
    Required demo (guide): create repo, create README, add and commit.
    Steps (mapping-driven; replace method names/params in config JSON):
      - git.init(path=repo_path)
      - filesystem.write_file(path=repo_path/README.md, content=readme_content)
      - git.add(path=repo_path)
      - git.commit(message="Initial commit")
    """
    toolmap = load_toolmap()

    # 1) Git init
    gitc = get_git_client()
    try:
        m_init   = toolmap["git"]["init"]["method"]
        p_init   = toolmap["git"]["init"]["params"]  # e.g., ["path"]
        resp = call_tool(gitc, m_init, {p_init[0]: repo_path})
        # Optional: validate resp["result"]

        # 2) Filesystem write README.md
        fsc = get_fs_client()
        try:
            m_wf = toolmap["filesystem"]["write_file"]["method"]
            p_wf = toolmap["filesystem"]["write_file"]["params"]  # e.g., ["path","content"]
            readme_path = str(Path(repo_path) / "README.md")
            resp = call_tool(fsc, m_wf, {p_wf[0]: readme_path, p_wf[1]: readme_content})
        finally:
            fsc.close()

        # 3) Git add
        m_add   = toolmap["git"]["add"]["method"]
        p_add   = toolmap["git"]["add"]["params"]  # e.g., ["path"] or ["files"]
        resp = call_tool(gitc, m_add, {p_add[0]: repo_path})

        # 4) Git commit
        m_commit = toolmap["git"]["commit"]["method"]
        p_commit = toolmap["git"]["commit"]["params"]  # e.g., ["message"]
        resp = call_tool(gitc, m_commit, {p_commit[0]: "Initial commit"})

    finally:
        gitc.close()
