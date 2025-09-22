#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BearingPro-MCP: JSON-RPC server over STDIO with Content-Length framing.
Exposes: select_bearing, verify_point, catalog_list, ping
Logs all requests/responses to logs/server.log
"""

import sys
from rpc_handler import StdioJsonRpcServer
from logger import get_logger
from tools.select_bearing import tool_select_bearing
from tools.verify_point import tool_verify_point
from tools.catalog_list import tool_catalog_list
from tools.croesus_xref import tool_croesus_xref

methods = {
    "select_bearing": tool_select_bearing,
    "verify_point": tool_verify_point,
    "catalog_list": tool_catalog_list,
    "croesus_xref": tool_croesus_xref,   # <--- NUEVO
    "ping": lambda params: {"pong": True},
}


def main():
    log = get_logger("server")
    methods = {
        "select_bearing": tool_select_bearing,
        "verify_point": tool_verify_point,
        "catalog_list": tool_catalog_list,
        "ping": lambda params: {"pong": True},
    }

    server = StdioJsonRpcServer(methods=methods, logger=log)
    server.serve_forever()

if __name__ == "__main__":
    # Run: py main.py
    main()
