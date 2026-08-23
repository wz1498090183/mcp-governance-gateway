# -*- coding: utf-8 -*-
"""stdio 客户端：以子进程方式启动 demo_server.py 并调用 echo 工具。

使用 sys.executable 保证子进程使用与当前相同的解释器（项目 .venv）。
"""

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    # 以子进程方式启动服务器（stdio 传输）
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["spike/demo_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 完成 MCP 握手
            await session.initialize()
            # 调用 echo 工具
            result = await session.call_tool("echo", {"text": "hello mcp"})
            # 输出结果文本
            print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
