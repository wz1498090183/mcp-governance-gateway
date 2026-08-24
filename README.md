# MCP Gateway（阶段三：限流、超时与审计）

把多个 MCP 服务器（streamable_http / stdio）聚合为统一 REST API，叠加 JWT 认证、工具级权限、固定窗口限流、工具超时与结构化审计日志。

## 目录结构

```
configs/gateway.yaml           # 网关配置（servers / auth / policies / redis / tool_governance）
demo_servers/demo_mcp.py       # Demo MCP 服务器（echo + sleep）
scripts/gen_token.py           # 生成测试 JWT Token（HS256）
src/mcp_gateway/               # 网关实现
  config.py                    # YAML 配置模型
  errors.py                    # 错误 + HTTP 状态码 + 稳定错误码
  schemas.py                   # 响应模型
  registry.py                  # 适配器生命周期 + 工具元数据缓存 + 超时映射
  service.py                   # 应用服务层（鉴权 + 限流 + 超时 + 审计编排）
  main.py                      # FastAPI 应用 + REST API + trace_id 中间件
  security/                    # JWT 验证 + 两级权限校验
  governance/                  # 限流 + 超时解析 + 结构化审计
    ratelimit.py               # RateLimiter（固定窗口，Redis 事务管道）
    audit.py                   # JsonFormatter + AuditLogger
    governance.py              # Governance 门面（from_config）
  transports/                  # streamable_http / stdio 适配器
tests/                         # FakeAdapter 单元 / 集成测试
```

## 治理模型

- **认证**：`Authorization: Bearer <JWT>`，HS256 本地验证，校验签名 / 算法 / issuer / audience / expiration。
- **Scope 层**（来自 Token `scope` claim）：`tools:list` 控制发现、`tools:call` 控制调用。
- **Tool Policy 层**（`policies`）：按 `tenant + role + server + tool + action` 五维精确匹配，任一角色命中即允许，未命中默认拒绝。
- **工具超时**（`tool_governance` 逐工具 `timeout_ms` → `gateway.default_timeout_ms`）：超时返回 504 `TOOL_TIMEOUT`，适配器失效后下次调用自动重建。
- **固定窗口限流**（`tool_governance` 逐工具 `rate_limit`）：key `rl:{tenant}:{server}:{tool}:{bucket}`，Redis 事务管道 `INCR + EXPIRE(2×窗口)`；超限 429 + `Retry-After`；Redis 故障按 `gateway.redis_failure_mode` 分支（`fail_open` 放行 / `fail_closed` 503）。
- **结构化审计**：标准 logging + JSON 输出 stdout，字段含 event/trace_id/tenant/subject/server_id/tool_name/policy_decision/status/latency_ms/error_code/param_keys（仅参数键名）。

## 安装

```bash
uv pip install -e .
```

## 运行

1. 设置 JWT 密钥（网关与 gen_token 使用同一环境变量）：

```bash
set JWT_SECRET=dev-secret-change-me-0123456789abcdef   # Windows cmd
```

2. （仅启用限流时）设置 Redis 地址环境变量：

```bash
set REDIS_URL=redis://127.0.0.1:6379/0
```

3. 启动 streamable-http 版 Demo MCP 服务器（127.0.0.1:8000/mcp）：

```bash
.venv/Scripts/python.exe demo_servers/demo_mcp.py --transport streamable-http
```

4. 启动网关（127.0.0.1:9000）：

```bash
.venv/Scripts/python.exe -m mcp_gateway.main
```

5. 生成测试 Token 并调用：

```bash
.venv/Scripts/python.exe scripts/gen_token.py analyst
curl http://127.0.0.1:9000/api/v1/tools -H "Authorization: Bearer <token>"
curl -X POST http://127.0.0.1:9000/api/v1/tools/demo-http/echo/call \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"text":"hello"}'
```

## 测试

```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```
