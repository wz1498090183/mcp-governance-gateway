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

    redis_failure_mode: Literal["fail_open", "fail_closed"] = "fail_open"
    """Redis 故障时行为：fail_open 放行，fail_closed 拒绝（503）。"""


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


class JWTSettings(BaseModel):
    """JWT 校验配置（开发环境 HS256）。

    secret_env 只保存环境变量名，密钥本身从环境变量读取，禁止硬编码进配置文件。
    """

    algorithm: Literal["HS256"] = "HS256"
    issuer: str
    audience: str
    secret_env: str = "JWT_SECRET"


class ToolPolicyRule(BaseModel):
    """工具权限策略规则：tenant + role + server + tool 四维定位，actions 声明允许的动作。

    无通配符、无 Deny、无权限继承，未命中的角色默认拒绝。
    """

    tenant: str
    role: str
    server: str
    tool: str
    actions: list[Literal["discover", "call"]]


class AuthSettings(BaseModel):
    """认证配置。"""

    jwt: JWTSettings


class RedisSettings(BaseModel):
    """Redis 连接配置：只存环境变量名，运行时从环境读取真实地址。"""

    url_env: str = "REDIS_URL"


class ToolRateLimitRule(BaseModel):
    """工具级限流规则（固定窗口）。"""

    enabled: bool = True
    window_seconds: int = 60
    requests: int = 10


class ToolGovernanceRule(BaseModel):
    """工具级治理规则：绑定 server + tool，可含超时与限流。"""

    server: str
    tool: str
    timeout_ms: int | None = None
    rate_limit: ToolRateLimitRule | None = None


class GatewayConfig(BaseModel):
    """网关配置根结构：auth / policies / redis / tool_governance 均为顶层治理配置。"""

    gateway: GatewaySettings = Field(default_factory=GatewaySettings)
    servers: list[ServerConfig] = Field(default_factory=list)
    auth: AuthSettings | None = None
    policies: list[ToolPolicyRule] = Field(default_factory=list)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    tool_governance: list[ToolGovernanceRule] = Field(default_factory=list)


def load_config(path: str | Path) -> GatewayConfig:
    """从 YAML 文件加载网关配置。"""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return GatewayConfig.model_validate(data)
