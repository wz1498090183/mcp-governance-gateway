# -*- coding: utf-8 -*-
"""MCP 传输适配器协议与公共基类。

定义网关与 MCP 服务器之间的统一传输接口，屏蔽 streamable_http / stdio 差异。
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Protocol

from mcp import ClientSession, types

logger = logging.getLogger(__name__)


class MCPTransportAdapter(Protocol):
    """MCP 传输适配器协议。

    所有传输实现（streamable_http / stdio / 测试 Fake）都满足此接口。
    """

    @property
    def server_id(self) -> str: ...

    async def initialize(self) -> None:
        """建立连接并完成 MCP 握手。"""
        ...

    async def list_tools(self) -> list[types.Tool]:
        """列出服务器提供的工具元数据。"""
        ...

    async def call_tool(self, name: str, arguments: dict[str, Any], timeout_seconds: float | None = None) -> types.CallToolResult:
        """调用指定工具并返回原始结果。timeout_seconds 为逐调用读超时。"""
        ...

    async def close(self) -> None:
        """关闭连接并释放资源。"""
        ...


class _BaseAdapter(MCPTransportAdapter):
    """传输适配器公共基类：复用连接、失效自动重建。

    所有 SDK 连接操作都在同一个后台 worker 任务内执行，以满足 anyio
    ``TaskGroup`` 的 cancel scope 必须在同一任务内进入/退出的约束——否则在
    FastAPI 每个请求独立任务的环境下，跨任务退出会抛
    ``RuntimeError: Attempted to exit cancel scope in a different task``。

    子类只需实现 ``_open()``：进入传输上下文并返回已完成握手的会话。
    调用失败（超时/传输/解析）会在 worker 内关闭连接，下次调用前自动重建。
    """

    def __init__(self, server_id: str, timeout_seconds: float | None) -> None:
        self._server_id = server_id
        self._timeout_seconds = timeout_seconds
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        # 以下状态仅由 worker 任务访问
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    @property
    def server_id(self) -> str:
        return self._server_id

    # ---- 子类实现：如何建立一条连接 ----
    async def _open(self) -> ClientSession:
        """进入传输上下文并返回完成握手的 ClientSession。子类实现。"""
        raise NotImplementedError

    # ---- 外部接口：把命令提交给 worker 任务并等待结果 ----
    async def _submit(self, cmd: str, *args: Any) -> Any:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._worker_loop())
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._queue.put((cmd, args, future))
        return await future

    async def initialize(self) -> None:
        await self._submit("init")

    async def list_tools(self) -> list[types.Tool]:
        return await self._submit("list_tools")

    async def call_tool(self, name: str, arguments: dict[str, Any], timeout_seconds: float | None = None) -> types.CallToolResult:
        return await self._submit("call_tool", name, arguments, timeout_seconds)

    async def close(self) -> None:
        await self._submit("shutdown")
        if self._worker is not None:
            await self._worker

    # ---- worker 内部：所有连接操作在同一个任务内执行 ----
    async def _worker_loop(self) -> None:
        while True:
            cmd, args, future = await self._queue.get()
            if cmd == "shutdown":
                try:
                    await self._close_conn()
                finally:
                    future.set_result(None)
                break

            try:
                if cmd == "init":
                    await self._close_conn()
                    await self._open_conn()
                    future.set_result(None)
                elif cmd == "list_tools":
                    await self._ensure_open()
                    result = await self._session.list_tools()
                    future.set_result(result.tools)
                elif cmd == "call_tool":
                    await self._ensure_open()
                    name, arguments, timeout_seconds = args
                    result = await self._session.call_tool(name, arguments, read_timeout_seconds=timeout_seconds)
                    future.set_result(result)
            except BaseException as exc:
                # 调用失败标记连接失效，下次调用前由 _ensure_open 自动重建
                await self._close_conn()
                future.set_exception(exc)

    async def _open_conn(self) -> None:
        self._stack = AsyncExitStack()
        self._session = await self._open()

    async def _close_conn(self) -> None:
        if self._stack is not None:
            stack, self._stack = self._stack, None
            self._session = None
            try:
                await stack.aclose()
            except BaseException:
                logger.exception("关闭连接失败（忽略）")

    async def _ensure_open(self) -> None:
        if self._session is None:
            await self._open_conn()
