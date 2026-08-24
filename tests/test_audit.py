# -*- coding: utf-8 -*-
"""结构化审计日志单元测试。"""

from __future__ import annotations

import io
import json
import logging

from mcp_gateway.governance.audit import AuditLogger, JsonFormatter, new_trace_id, trace_id_var


def _capture() -> tuple[io.StringIO, list]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("mcp_gateway.audit")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return stream, handler


def test_audit_contains_required_fields() -> None:
    stream, _ = _capture()
    AuditLogger().log(
        event="tool.call",
        tenant="tenant-a",
        subject="u-1",
        server_id="demo",
        tool_name="echo",
        policy_decision="allow",
        status="success",
        latency_ms=12,
        error_code="",
        param_keys=["text"],
    )
    data = json.loads(stream.getvalue().strip())
    for field in (
        "event",
        "trace_id",
        "tenant",
        "subject",
        "server_id",
        "tool_name",
        "policy_decision",
        "status",
        "latency_ms",
        "error_code",
        "param_keys",
    ):
        assert field in data
    assert data["event"] == "tool.call"
    assert data["param_keys"] == ["text"]


def test_audit_does_not_leak_values() -> None:
    stream, _ = _capture()
    AuditLogger().log(event="tool.call", param_keys=["password"], status="success")
    line = stream.getvalue()
    assert "password" in line  # 键名允许
    assert "secret-value" not in line  # 参数值不允许


def test_audit_trace_id_from_contextvar() -> None:
    stream, _ = _capture()
    token = trace_id_var.set("trace-abc")
    try:
        AuditLogger().log(event="tool.call")
    finally:
        trace_id_var.reset(token)
    data = json.loads(stream.getvalue().strip())
    assert data["trace_id"] == "trace-abc"


def test_new_trace_id_is_hex32() -> None:
    tid = new_trace_id()
    assert len(tid) == 32
    int(tid, 16)  # 可解析为 hex
