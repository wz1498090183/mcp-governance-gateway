# -*- coding: utf-8 -*-
"""网关配置模型与 YAML 加载。

配置结构严格对应 configs/gateway.yaml，不额外引入字段。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class GatewaySettings(BaseModel):
    """网关全局设置。"""

    default_timeout_ms: int = 3000
    """会话级读超时毫秒数，0 表示不超时。"""


class ServerConfig(BaseModel):
    """单个 MCP 服务器配置。"""

    id: str
    enabled: bool = True
    required: bool = False
    transport: Literal["stdio", "streamable_http"]
    endpoint: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_transport_fields(self) -> ServerConfig:
        """校验 transport 对应的必填字段。"""
        if self.transport == "streamable_http" and not self.endpoint:
            raise ValueError(f"服务器 {self.id}: streamable_http 必须提供 endpoint")
        if self.transport == "stdio" and not self.command:
            raise ValueError(f"服务器 {self.id}: stdio 必须提供 command")
        return self


class GatewayConfig(BaseModel):
    """网关配置根结构。"""

    gateway: GatewaySettings = Field(default_factory=GatewaySettings)
    servers: list[ServerConfig] = Field(default_factory=list)


def load_config(path: str | Path) -> GatewayConfig:
    """从 YAML 文件加载网关配置。"""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return GatewayConfig.model_validate(data)
