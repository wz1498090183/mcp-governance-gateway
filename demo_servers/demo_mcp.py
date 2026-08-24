# -*- coding: utf-8 -*-
"""Demo MCP 服务器：提供 echo 与 sleep 两个工具，支持 stdio / streamable-http。

启动方式：
    python demo_servers/demo_mcp.py --transport stdio
    python demo_servers/demo_mcp.py --transport streamable-http [--host 0.0.0.0 --port 8000]
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
    parser.add_argument("--host", default="127.0.0.1", help="streamable-http 监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=8000, help="streamable-http 监听端口（默认 8000）")
    args = parser.parse_args()
    if args.transport == "streamable-http":
        mcp.run(transport=args.transport, host=args.host, port=args.port)
    else:
        mcp.run(transport=args.transport)
