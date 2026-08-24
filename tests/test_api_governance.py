# -*- coding: utf-8 -*-
"""治理能力下的 REST API 集成测试（FakeAdapter + 内存/故障限流后端）。"""

from __future__ import annotations

import io
import json
import logging

from mcp_gateway.config import ToolGovernanceRule, ToolRateLimitRule
from mcp_gateway.governance import Governance
from mcp_gateway.governance.audit import AuditLogger, JsonFormatter
from mcp_gateway.governance.ratelimit import RateLimiter

from jwt_helpers import build_token, make_auth_client


class _BrokenPipeline:
    def incr(self, key):
        return self

    def expire(self, key, ttl):
        return self

    async def execute(self):
        raise ConnectionError("redis down")


class _BrokenRedis:
    def pipeline(self, transaction=True):
        return _BrokenPipeline()


class _InMemoryPipeline:
    """极简内存 pipeline：仅支持 transaction=True 的 INCR + EXPIRE。"""

    def __init__(self, store: dict):
        self._store = store
        self._ops: list[tuple] = []

    def incr(self, key):
        self._ops.append(("incr", key))
        return self

    def expire(self, key, ttl):
        self._ops.append(("expire", key, ttl))
        return self

    async def execute(self):
        results = []
        for op, key, *rest in self._ops:
            if op == "incr":
                self._store[key] = self._store.get(key, 0) + 1
                results.append(self._store[key])
            else:
                results.append(True)
        return results


class _InMemoryRedis:
    """内存版 async Redis，无事件循环亲和问题，供 TestClient 线程使用。"""

    def __init__(self):
        self._store: dict = {}

    def pipeline(self, transaction=True):
        return _InMemoryPipeline(self._store)


def _governance(rate_limiter=None, rules=None, default_timeout_ms=3000):
    return Governance(default_timeout_ms, rules or [], rate_limiter, AuditLogger())


def _rate_limit_governance(requests=1, failure_mode="fail_open", client=None):
    rule = ToolGovernanceRule(
        server="demo",
        tool="echo",
        rate_limit=ToolRateLimitRule(enabled=True, window_seconds=60, requests=requests),
    )
    limiter = RateLimiter(client if client is not None else _InMemoryRedis(), failure_mode)
    return _governance(rate_limiter=limiter, rules=[rule])


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _analyst_token() -> str:
    return build_token(roles=["analyst"], scope="tools:list tools:call")


def test_call_tool_timeout_504() -> None:
    gov = _governance()
    with make_auth_client(tool_names=["echo"], fail_timeout=True, governance=gov) as client:
        resp = client.post("/api/v1/tools/demo/echo/call", headers=_bearer(_analyst_token()), json={"text": "hi"})
        assert resp.status_code == 504
        assert resp.json()["code"] == "TOOL_TIMEOUT"


def test_rate_limit_429_with_retry_after() -> None:
    gov = _rate_limit_governance(requests=1)
    with make_auth_client(tool_names=["echo"], governance=gov) as client:
        token = _analyst_token()
        r1 = client.post("/api/v1/tools/demo/echo/call", headers=_bearer(token), json={"text": "hi"})
        assert r1.status_code == 200
        r2 = client.post("/api/v1/tools/demo/echo/call", headers=_bearer(token), json={"text": "hi"})
        assert r2.status_code == 429
        assert r2.json()["code"] == "RATE_LIMIT_EXCEEDED"
        assert "Retry-After" in r2.headers


def test_rate_limit_fail_closed_503() -> None:
    gov = _rate_limit_governance(failure_mode="fail_closed", client=_BrokenRedis())
    with make_auth_client(tool_names=["echo"], governance=gov) as client:
        resp = client.post("/api/v1/tools/demo/echo/call", headers=_bearer(_analyst_token()), json={"text": "hi"})
        assert resp.status_code == 503
        assert resp.json()["code"] == "RATE_LIMIT_BACKEND_UNAVAILABLE"


def test_rate_limit_fail_open_passes() -> None:
    gov = _rate_limit_governance(failure_mode="fail_open", client=_BrokenRedis())
    with make_auth_client(tool_names=["echo"], governance=gov) as client:
        resp = client.post("/api/v1/tools/demo/echo/call", headers=_bearer(_analyst_token()), json={"text": "hi"})
        assert resp.status_code == 200


def test_tool_without_rate_limit_not_limited() -> None:
    # 只给 sleep 配限流，echo 无规则 → 不限流
    rule = ToolGovernanceRule(
        server="demo",
        tool="sleep",
        rate_limit=ToolRateLimitRule(enabled=True, window_seconds=60, requests=1),
    )
    gov = _governance(rate_limiter=RateLimiter(_InMemoryRedis(), "fail_open"), rules=[rule])
    with make_auth_client(tool_names=["echo", "sleep"], governance=gov) as client:
        token = _analyst_token()
        for _ in range(3):
            resp = client.post("/api/v1/tools/demo/echo/call", headers=_bearer(token), json={"text": "hi"})
            assert resp.status_code == 200


def test_audit_logged_on_denied() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("mcp_gateway.audit")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    gov = _governance()
    with make_auth_client(tool_names=["echo"], governance=gov) as client:
        guest = build_token(roles=["guest"], scope="tools:list tools:call")
        resp = client.post("/api/v1/tools/demo/echo/call", headers=_bearer(guest), json={"text": "hi"})
        assert resp.status_code == 403

    data = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert data["status"] == "denied"
    assert data["policy_decision"] == "deny"
    assert data["error_code"] == "POLICY_TOOL_DENIED"
    assert data["param_keys"] == ["text"]
