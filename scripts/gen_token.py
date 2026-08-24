# -*- coding: utf-8 -*-
"""生成测试用 JWT Token（HS256，开发环境）。

四种画像：
    analyst        —— roles=analyst，具备 tools:list tools:call，可正常发现/调用
    guest          —— roles=guest，具备 scope 但无任何工具策略，调用被 Tool Policy 拒绝
    no-scope       —— roles=analyst，但 scope 为空，调用被 Scope 层拒绝
    wrong-audience —— aud 指向其他受众，验证时 401

用法（Windows cmd）：
    set JWT_SECRET=dev-secret-change-me
    python scripts/gen_token.py analyst
"""

import argparse
import os
import sys
import time

import jwt

ISSUER = "mcp-gateway-dev"
AUDIENCE = "mcp-gateway"
SECRET_ENV = "JWT_SECRET"

PROFILES = {
    "analyst": {
        "sub": "u-1001",
        "tenant_id": "tenant-a",
        "roles": ["analyst"],
        "scope": "tools:list tools:call",
    },
    "guest": {
        "sub": "u-1002",
        "tenant_id": "tenant-a",
        "roles": ["guest"],
        "scope": "tools:list tools:call",
    },
    "no-scope": {
        "sub": "u-1003",
        "tenant_id": "tenant-a",
        "roles": ["analyst"],
        "scope": "",
    },
    "wrong-audience": {
        "sub": "u-1004",
        "tenant_id": "tenant-a",
        "roles": ["analyst"],
        "scope": "tools:list tools:call",
        "aud": "other-audience",
    },
}


def build_token(profile: str, secret: str, expires_in: int = 3600) -> str:
    """按画像构造 payload 并签发 HS256 Token。"""
    info = PROFILES[profile]
    now = int(time.time())
    payload = {
        "sub": info["sub"],
        "tenant_id": info["tenant_id"],
        "roles": info["roles"],
        "scope": info["scope"],
        "iss": ISSUER,
        "aud": info.get("aud", AUDIENCE),
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成测试 JWT Token")
    parser.add_argument("profile", choices=list(PROFILES), help="Token 画像")
    parser.add_argument("--expires-in", type=int, default=3600, help="有效期秒数，默认 3600")
    args = parser.parse_args()

    secret = os.environ.get(SECRET_ENV)
    if not secret:
        print(f"错误：请先设置环境变量 {SECRET_ENV}，例如 set {SECRET_ENV}=dev-secret-change-me", file=sys.stderr)
        return 1

    print(build_token(args.profile, secret, args.expires_in))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
