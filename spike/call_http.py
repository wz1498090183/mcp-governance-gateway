# -*- coding: utf-8 -*-
"""Streamable HTTP 客户端：连接已启动的服务器并调用 echo 工具。

mcp 2.0.0 中 streamable_http_client 返回 (read, write) 二元组。
"""

import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

# 与 demo_server.py 默认的 host/port/streamable_http_path 保持一致
SERVER_URL = "http://127.0.0.1:8000/mcp"


async def main() -> None:
    async with streamable_http_client(SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            # 完成 MCP 握手
            await session.initialize()
            # 调用 echo 工具
            result = await session.call_tool("echo", {"text": "hello mcp"})
            # 输出结果文本
            print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
