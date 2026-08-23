# -*- coding: utf-8 -*-
"""MCP 探针服务器：仅提供 echo(text) 工具。

mcp 2.0.0 中 FastMCP 已移除，改用 mcp.server.MCPServer。

启动方式：
    python spike/demo_server.py                     # stdio 模式（默认）
    python spike/demo_server.py streamable-http     # Streamable HTTP 模式
"""

import sys

from mcp.server import MCPServer

# 创建 MCP 服务器实例
mcp = MCPServer(name="echo-server")


@mcp.tool()
def echo(text: str) -> str:
    """原样返回输入的文本。"""
    return text


if __name__ == "__main__":
    # 通过命令行参数选择传输方式，默认 stdio
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    mcp.run(transport=transport)
