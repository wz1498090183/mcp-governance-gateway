# -*- coding: utf-8 -*-
"""JWT 验证器（开发环境 HS256）。

仅实现本地对称密钥验证，不依赖 JWKS / OIDC Discovery / 授权服务器。
算法固定为 HS256，禁止根据 Token Header 动态选择算法。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import jwt

from mcp_gateway.errors import AuthenticationError


@dataclass(frozen=True)
class Principal:
    """已验证身份：从 Token 提取的最小字段集。"""

    sub: str
    tenant_id: str = ""
    roles: tuple[str, ...] = ()
    scopes: frozenset[str] = field(default_factory=frozenset)


def _as_list(value: object) -> tuple[str, ...]:
    """把 roles 归一为字符串元组：str 视为单元素，list 逐项展开。"""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def _as_scope_set(value: object) -> frozenset[str]:
    """scope 既可能是空格分隔的字符串，也可能是列表，统一为集合。"""
    if isinstance(value, str):
        return frozenset(part for part in value.split() if part)
    return frozenset(part for part in _as_list(value) if part)


class HS256TokenVerifier:
    """HS256 Token 验证器：校验签名、算法、issuer、audience、expiration。"""

    def __init__(self, secret: str, issuer: str, audience: str, algorithm: str = "HS256") -> None:
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._algorithm = algorithm

    def verify(self, token: str) -> Principal:
        """校验并解析 Token，返回 Principal；任何失败统一抛 AuthenticationError。"""
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],  # 固定算法，不读 header 动态选择
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["sub", "exp"]},
            )
        except jwt.PyJWTError:
            # 统一 401，不向外部暴露签名失败 / 过期等细粒度原因
            raise AuthenticationError() from None

        return Principal(
            sub=str(payload.get("sub", "")),
            tenant_id=str(payload.get("tenant_id", "")),
            roles=_as_list(payload.get("roles")),
            scopes=_as_scope_set(payload.get("scope")),
        )
