# -*- coding: utf-8 -*-
"""FastAPI 应用入口：lifespan 管理注册表生命周期，暴露 REST API。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Body, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from mcp_gateway.config import load_config
from mcp_gateway.errors import AuthenticationError, GatewayError
from mcp_gateway.registry import MCPRegistry
from mcp_gateway.security import Principal, Security
from mcp_gateway.service import GatewayService

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("configs/gateway.yaml")


async def get_principal(request: Request) -> Principal | None:
    """从 Authorization: Bearer 头解析并校验 Token，返回 Principal。

    未启用鉴权（security 为 None）时直接返回 None，保持阶段一纯透传行为。
    """
    security: Security | None = request.app.state.security
    if security is None:
        return None
    header = request.headers.get("Authorization", "")
    scheme, sep, token = header.partition(" ")
    if not sep or scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError()
    return security.verify(token.strip())


def create_app(registry: MCPRegistry, security: Security | None = None) -> FastAPI:
    """创建 FastAPI 应用，并注入注册表与鉴权门面。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await registry.initialize()
        app.state.service = GatewayService(registry, security)
        app.state.security = security
        yield
        await registry.close()

    app = FastAPI(title="MCP Gateway", lifespan=lifespan)

    @app.exception_handler(GatewayError)
    async def gateway_error_handler(request: Request, exc: GatewayError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "error": exc.message},
        )

    @app.get("/api/v1/tools")
    async def list_tools(
        request: Request,
        principal: Principal | None = Depends(get_principal),
    ) -> dict[str, Any]:
        service: GatewayService = request.app.state.service
        return {"tools": [tool.model_dump() for tool in service.list_tools(principal)]}

    @app.post("/api/v1/tools/{server_id}/{tool_name}/call")
    async def call_tool(
        server_id: str,
        tool_name: str,
        request: Request,
        arguments: dict[str, Any] = Body(default_factory=dict),
        principal: Principal | None = Depends(get_principal),
    ) -> dict[str, Any]:
        service: GatewayService = request.app.state.service
        return await service.call_tool(server_id, tool_name, arguments, principal)

    return app


def build_default_app() -> FastAPI:
    """从默认配置文件构建应用（供 uvicorn --factory 或 python -m 使用）。"""
    config = load_config(DEFAULT_CONFIG_PATH)
    registry = MCPRegistry.from_config(config)
    security = Security.from_config(config)
    return create_app(registry, security)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(build_default_app(), host="127.0.0.1", port=9000)
