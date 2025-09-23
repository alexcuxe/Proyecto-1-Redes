# BearingPro-MCP Host (Console)

A console chatbot host integrating **MCP** (Model Context Protocol) tools:
- **Local MCP (STDIO)**: BearingPro (bearing selection/verification using a local catalog)
- **Remote MCP (HTTP/Cloud Run)**: demo tools (`echo`, `time_now`, `add`)
- **LLM (Anthropic)** on/off
- **Planner mode**: the LLM proposes a JSON plan (`call_tool|answer`), the host executes MCP calls and feeds results back.

## Features
- Contextual chat with optional LLM
- MCP local server via STDIO (binary framing with `Content-Length` + `Content-Type`)
- MCP remote server via HTTP (JSON-RPC over `/mcp`)
- Planner that lets the LLM decide when to call tools
- Logs to `logs/chat.log`
- Modular clients: `client/local_clients.py`, `client/remote_clients.py`

## Requirements
- Python 3.11+
- `pip install anthropic requests`

## Environment variables (Windows CMD/PowerShell)
```bat
:: LLM (optional)
set ANTHROPIC_API_KEY=...
set ANTHROPIC_MODEL=claude-...

:: Local MCP (BearingPro)
set BEARINGPRO_CMD=python local_servers/bearingpro/main.py

:: Remote MCP (Cloud Run)
set REMOTE_MCP_URL=https://<service>.run.app/mcp


```bat
:: RUN
py -m host.chat

```



## Commands
- Planner: modo planner on/off
- Local (BearingPro): catálogo, selección Fr=.. Fa=.. rpm=.. L10h=.., verificar <modelo> con Fr=.. rpm=..
- Remoto: remoto init, remoto hora, remoto suma 3 4
- LLM: modo llm on/off


## Project Structure
```bat
host/ chat.py, llm_anthropic.py
client/ stdio_client.py, local_clients.py, remote_clients.py
local_servers/bearingpro/ main.py, bearing_utils.py, catalog.json
config/ official_tools_map.json
scripts/ remote_smoke.py, discover_official_tools.py
logs/
docs/img/ (Wireshark screenshots)
docs/artifacts/ (pcap/keys)
```