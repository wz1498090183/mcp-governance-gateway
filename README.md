# MCP Gateway（阶段二：JWT 鉴权与工具级权限）

把多个 MCP 服务器（streamable_http / stdio）聚合为统一 REST API，并在阶段一纯透传基础上叠加 JWT 认证与工具级权限控制。

## 目录结构

```
configs/gateway.yaml           # 网关配置（servers / auth / policies）
demo_servers/demo_mcp.py       # Demo MCP 服务器（echo + sleep）
scripts/gen_token.py           # 生成测试 JWT Token（HS256）
src/mcp_gateway/               # 网关实现
  config.py                    # YAML 配置模型
  errors.py                    # 错误 + HTTP 状态码 + 稳定错误码
  schemas.py                   # 响应模型
  registry.py                  # 适配器生命周期 + 工具元数据缓存
  service.py                   # 应用服务层（叠加两级权限校验）
  main.py                      # FastAPI 应用 + REST API + 鉴权依赖
  security/                    # JWT 验证 + 两级权限校验
    verifier.py                # HS256TokenVerifier
    policy.py                  # PolicyEngine（Scope 层 + Tool Policy 层）
    security.py                # Security 门面（from_config）
  transports/                  # streamable_http / stdio 适配器
tests/                         # FakeAdapter 单元 / 集成测试
```

## 鉴权模型

- **认证**：`Authorization: Bearer <JWT>`，HS256 本地验证，校验签名 / 算法 / issuer / audience / expiration。
- **Scope 层**（接口级能力，来自 Token `scope` claim）：`tools:list` 控制发现、`tools:call` 控制调用。
- **Tool Policy 层**（工具级动作，来自 `configs/gateway.yaml` 的 `policies`）：按 `tenant + role + server + tool + action` 五维精确匹配，任一角色命中即允许，未命中默认拒绝（无通配符 / 无 Deny / 无继承）。

## 安装

```bash
uv pip install -e .
```

## 运行

1. 设置 JWT 密钥（网关与 gen_token 使用同一个环境变量）：

```bash
# Windows cmd
set JWT_SECRET=dev-secret-change-me-0123456789abcdef
# PowerShell
$env:JWT_SECRET = "dev-secret-change-me-0123456789abcdef"
```

2. 启动 streamable-http 版 Demo MCP 服务器（另开终端，127.0.0.1:8000/mcp）：

```bash
.venv/Scripts/python.exe demo_servers/demo_mcp.py --transport streamable-http
```

（stdio 版由网关按配置以子进程拉起，无需单独启动。）

3. 启动网关（127.0.0.1:9000）：

```bash
.venv/Scripts/python.exe -m mcp_gateway.main
# 或
.venv/Scripts/python.exe -m uvicorn mcp_gateway.main:build_default_app --factory --host 127.0.0.1 --port 9000
```

4. 生成测试 Token 并调用：

```bash
.venv/Scripts/python.exe scripts/gen_token.py analyst
# 可选：guest / no-scope / wrong-audience

curl http://127.0.0.1:9000/api/v1/tools -H "Authorization: Bearer <token>"
curl -X POST http://127.0.0.1:9000/api/v1/tools/demo-http/echo/call \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"text":"hello"}'
```

## 测试

```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```
