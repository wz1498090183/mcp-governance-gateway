# -*- coding: utf-8 -*-
"""Demo MCP 服务器：提供 echo 与 sleep 两个工具，支持 stdio / streamable-http。

启动方式：
    python demo_servers/demo_mcp.py --transport stdio
    python demo_servers/demo_mcp.py --transport streamable-http
"""

import argparse
import time

from mcp.server import MCPServer

mcp = MCPServer(name="demo-mcp")


@mcp.tool()
def echo(text: str) -> str:
    """原样返回输入的文本。"""
    return text


@mcp.tool()
def sleep(seconds: float) -> str:
    """睡眠指定秒数后返回，用于演示调用超时。"""
    time.sleep(seconds)
    return f"slept {seconds}s"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo MCP server")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "streamable-http"])
    args = parser.parse_args()
    mcp.run(transport=args.transport)
