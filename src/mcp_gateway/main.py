# -*- coding: utf-8 -*-
"""FastAPI 应用入口：lifespan 管理注册表生命周期，暴露 REST API。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse

from mcp_gateway.config import load_config
from mcp_gateway.errors import GatewayError
from mcp_gateway.registry import MCPRegistry
from mcp_gateway.service import GatewayService

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("configs/gateway.yaml")


def create_app(registry: MCPRegistry) -> FastAPI:
    """创建 FastAPI 应用，并注入注册表。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await registry.initialize()
        app.state.service = GatewayService(registry)
        yield
        await registry.close()

    app = FastAPI(title="MCP Gateway", lifespan=lifespan)

    @app.exception_handler(GatewayError)
    async def gateway_error_handler(request: Request, exc: GatewayError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.message})

    @app.get("/api/v1/tools")
    async def list_tools(request: Request) -> dict[str, Any]:
        service: GatewayService = request.app.state.service
        return {"tools": [tool.model_dump() for tool in service.list_tools()]}

    @app.post("/api/v1/tools/{server_id}/{tool_name}/call")
    async def call_tool(
        server_id: str,
        tool_name: str,
        request: Request,
        arguments: dict[str, Any] = Body(default_factory=dict),
    ) -> dict[str, Any]:
        service: GatewayService = request.app.state.service
        return await service.call_tool(server_id, tool_name, arguments)

    return app


def build_default_app() -> FastAPI:
    """从默认配置文件构建应用（供 uvicorn --factory 或 python -m 使用）。"""
    config = load_config(DEFAULT_CONFIG_PATH)
    registry = MCPRegistry.from_config(config)
    return create_app(registry)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(build_default_app(), host="127.0.0.1", port=9000)
