# Proyecto CC3067 — Uso de un protocolo existente (MCP)
**Estudiante:** Eber Cuxé - 22648  
**Curso:** CC3067 Redes — Universidad del Valle de Guatemala

## 1. Antecedentes
Este proyecto implementa un anfitrión conversacional que integra servidores MCP (Model Context Protocol) para ampliar capacidades de un LLM mediante herramientas interoperables sobre JSON-RPC. MCP separa **host**, **cliente** y **servidor** para que las herramientas sean reutilizables entre agentes/LLMs.

## 2. Objetivos
- Implementar un protocolo basado en estándares (MCP/JSON-RPC).
- Comprender MCP y sus servicios.
- Implementar un **servidor MCP local** y un **servidor MCP remoto** y consumirlos desde el host.
- Interactuar con un LLM por API con **modo planificador** (planner).
- Analizar con Wireshark la comunicación host ↔ servidor remoto, clasificando **sincronización/solicitud/respuesta** y explicando por **capas**.

## 3. Arquitectura y flujo
- **Host** (chat por terminal): LLM on/off, **planner** que propone llamar tools, logs.
- **Cliente STDIO**: framing `Content-Length` + `Content-Type: application/json` (Windows-friendly).
- **Servidor MCP Local**: BearingPro-MCP (selección/verificación con catálogo local, listo para migrar a API SKF).
- **Servidor MCP Remoto**: Cloud Run (`POST /mcp`) con tools demo (`echo`, `time_now`, `add`).

## 4. Implementación

### 4.1 Host (console)
- LLM Anthropic (toggle).
- **Planner**: la LLM devuelve un **plan JSON** (`action: call_tool|answer`). Si `call_tool`, el host llama MCP y realimenta la “observación” a la LLM para la respuesta final.

### 4.2 MCP Local — BearingPro-MCP
- **Tools**:
  - `catalog_list()`
  - `select_bearing(Fr_N, Fa_N, rpm, L10h_target)`
  - `verify_point(model, Fr_N, Fa_N, rpm, L10h_target)`
- **Cálculos (demo)**: `P = Fr + 1.5*Fa`; `L10h = (C/P)^3 * 1e6 / (60*rpm)`.
- **Catálogo**: `catalog.json` ampliable.

### 4.3 MCP Remoto — Cloud Run
- `POST /mcp` (JSON-RPC: `initialize`, `tools/call`).
- Tools: `echo`, `time_now`, `add`.

## 5. Pruebas
- Local: selección/verificación con pocos datos; planner operativo.
- Remoto: `remoto init`, `remoto hora`, `remoto suma 3 4`.

## 6. Análisis Wireshark (Punto 8)

### 6.1 Procedimiento
- Filtros:  
  - SNI: `tls.handshake.extensions_server_name contains "remote-mcp"`  
  - TCP 443: `tcp.port == 443`  
  - Stream: `tcp.stream == N`  
  - QUIC/HTTP3: `quic || http3`

### 6.2 Evidencias (Figuras)
- **Figura 1 – SNI/Client Hello (Cloud Run):** `docs/img/cap1_sni_handshake.png`
- **Figura 2 – TCP 3-way handshake:** `docs/img/cap2_tcp_3way.png`
- **Figura 3 – TLS 1.3 (Client/Server Hello):**  
  `docs/img/cap3_tls_handshake_clientHello.png` y `docs/img/cap3_tls_handshake_serverHello.png`
- **Figuras 4 y 5 – initialize / tools.call (equivalente TLS/QUIC):**  
  `docs/img/cap4y5_equivalente_quic.png`

**Clasificación JSON-RPC:**
- **Sincronización**: `initialize` (primer POST `/mcp`).
- **Solicitud**: `tools/call` (p.ej., `time_now`, `add`).
- **Respuesta**: `{"result": {...}}` / `{"error": {...}}`.

> Si no hay descifrado TLS/QUIC, se correlaciona por temporalidad, dirección y tamaños de paquetes al ejecutar cada comando desde el host.

### 6.3 Explicación por capas
- **Enlace**: tramas Ethernet/802.11 entre NIC y AP.
- **Red (IP)**: IPv6 pública hacia `*.run.app`.
- **Transporte**: TCP/443 (SYN/SYN-ACK/ACK) o QUIC/UDP con “Protected Payload”.
- **Aplicación**: HTTP/2 o HTTP/3 sobre TLS 1.3; cuerpo con JSON-RPC (`initialize` / `tools/call` / `result`).

### 6.4 Artefactos
- PCAP/PCAPNG: `docs/artifacts/mcp_cloudRun_stream_22648.pcapng`
- (Opcional) `sslkeys.log` si se hizo descifrado.

## 7. Especificación de servidores desarrollados

### 7.1 BearingPro-MCP (Local, STDIO)
- **Protocolo**: JSON-RPC por STDIO (framing binario).
- **Tools**:
  - `catalog_list() -> { ok, models: [...] }`
  - `select_bearing(...) -> { ok, candidates:[...], P_equiv_N }`
  - `verify_point(...) -> { ok, model, L10h_pred, meets_target, ... }`
- **Ejemplos de uso (host)**: `catálogo`, `selección ...`, `verificar ...`.
- **Migración a SKF**: misma interfaz; cambiar catálogo/cálculos en el server.

### 7.2 MCP Remoto (Cloud Run)
- **Endpoint**: `POST /mcp` (initialize, tools/call).
- **Tools**: `echo`, `time_now`, `add`.
- **Host**: `REMOTE_MCP_URL=https://<service>.run.app/mcp`.

## 8. Conclusiones
- La arquitectura modular permite que la LLM use datos locales mediante MCP (planner).
- Se validó un servidor MCP remoto en Cloud Run y su consumo desde el host.
- La captura en Wireshark permite clasificar sincronización/solicitud/respuesta y explicar por capas.

## 9. Comentarios
- El framing STDIO (`Content-Length` + `Content-Type`) eliminó problemas de timeout en Windows.
- El diseño facilita agregar más MCPs locales/remotos y migrar a API SKF sin tocar el host.

## 10. Referencias
- JSON-RPC — https://www.jsonrpc.org/  
- MCP Architecture — https://modelcontextprotocol.io/docs/learn/architecture  
- MCP Specification — https://modelcontextprotocol.io/specification/2025-06-18  
- MCP servers & SDKs — https://github.com/modelcontextprotocol/servers  
- Cloud Run tutorial — https://cloud.google.com/blog/topics/developers-practitioners/build-and-deploy-a-remote-mcp-server-to-google-cloud-run-in-under-10-minutes
