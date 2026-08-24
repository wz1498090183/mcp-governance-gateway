#!/usr/bin/env bash
# -*- coding: utf-8 -*-
# 一键演示脚本：等待网关 /ready 就绪后，依次执行 7 个治理场景并断言 HTTP 状态码。
# 任一断言失败立即退出（exit 1）；全部通过后输出统一成功提示。
#
# 依赖：curl 与任一 Python 3（仅用标准库签发 HS256 JWT，无需 pyjwt）。
# 环境变量：JWT_SECRET（可从 .env 读取）、GATEWAY_URL（默认 http://127.0.0.1:9000）。

set -euo pipefail

BASE_URL="${GATEWAY_URL:-http://127.0.0.1:9000}"
READY_TIMEOUT="${READY_TIMEOUT:-60}"

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

# 寻找可用的 Python 解释器（Windows 上 python3 可能是应用商店占位符，需跳过）
find_python() {
  local c
  for c in python3 python .venv/Scripts/python.exe .venv/bin/python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys' >/dev/null 2>&1; then
      printf '%s\n' "$c"
      return 0
    fi
  done
  echo "错误：未找到可用的 Python 解释器（签发 JWT 需要）" >&2
  return 1
}
PYTHON="$(find_python)"

# 从环境变量或 .env 读取 JWT_SECRET
if [ -z "${JWT_SECRET:-}" ] && [ -f .env ]; then
  JWT_SECRET="$(grep -E '^JWT_SECRET=' .env | head -1 | cut -d= -f2- | tr -d '\r')"
fi
: "${JWT_SECRET:?缺少 JWT_SECRET：请先复制 .env.example 为 .env 并填写，或 export JWT_SECRET=...}"

# 使用标准库签发 HS256 JWT（与 scripts/gen_token.py 等价，避免依赖 pyjwt）
build_token() {
  local roles="$1" scope="$2"
  "$PYTHON" - "$JWT_SECRET" "$roles" "$scope" <<'PY'
import base64, hashlib, hmac, json, sys, time

secret = sys.argv[1]
roles = sys.argv[2].split(",") if sys.argv[2] else []
scope = sys.argv[3]

def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
now = int(time.time())
payload = {
    "sub": "u-demo",
    "tenant_id": "tenant-a",
    "roles": roles,
    "scope": scope,
    "iss": "mcp-gateway-dev",
    "aud": "mcp-gateway",
    "iat": now,
    "exp": now + 3600,
}
body = b64(json.dumps(payload, separators=(",", ":")).encode())
msg = (header + "." + body).encode()
sig = b64(hmac.new(secret.encode(), msg, hashlib.sha256).digest())
print(header + "." + body + "." + sig)
PY
}

# 响应体临时文件
RESP_FILE="$(mktemp)"
trap 'rm -f "$RESP_FILE"' EXIT

# 发起请求：响应体写入临时文件，HTTP 状态码输出到 stdout
request() {
  # 用法：request <方法> <路径> [Authorization] [JSON 请求体]
  local method="$1" path="$2" auth="${3:-}" data="${4:-}"
  local args=(-s -o "$RESP_FILE" -w '%{http_code}' -X "$method" "$BASE_URL$path")
  [ -n "$auth" ] && args+=(-H "Authorization: Bearer $auth")
  [ -n "$data" ] && args+=(-H "Content-Type: application/json" -d "$data")
  curl "${args[@]}"
}

# 断言 HTTP 状态码
assert_status() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$actual" != "$expected" ]; then
    echo "[失败] ${desc}：期望 ${expected}，实际 ${actual}" >&2
    exit 1
  fi
  echo "[通过] ${desc} -> ${actual}"
}

# 断言响应体包含指定子串（用于校验稳定错误码）
assert_contains() {
  local desc="$1" body="$2" needle="$3"
  case "$body" in
    *"$needle"*) echo "[通过] ${desc}" ;;
    *) echo "[失败] ${desc}：响应未包含 ${needle}，实际：${body}" >&2; exit 1 ;;
  esac
}

# ---------------------------------------------------------------------------
# 0. 等待 /ready 就绪
# ---------------------------------------------------------------------------
echo "== 0. 等待网关就绪 (/ready) =="
ready=""
for _ in $(seq 1 "$READY_TIMEOUT"); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/ready" 2>/dev/null || true)"
  if [ "$code" = "200" ]; then
    ready="ok"
    break
  fi
  sleep 1
done
if [ "$ready" != "ok" ]; then
  echo "[失败] 网关在 ${READY_TIMEOUT}s 内未就绪（最后状态码：${code:-无}）" >&2
  exit 1
fi
echo "[通过] 网关已就绪 -> 200"

ANALYST="$(build_token "analyst" "tools:list tools:call")"
GUEST="$(build_token "guest" "tools:list tools:call")"
[ -n "$ANALYST" ] && [ -n "$GUEST" ] || { echo "[失败] JWT 签发失败" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 场景断言
# ---------------------------------------------------------------------------

echo "== 1. 列工具 =="
code="$(request GET /api/v1/tools "$ANALYST" || true)"
body="$(cat "$RESP_FILE")"
assert_status "列工具（analyst）" 200 "$code"
assert_contains "列工具返回工具列表" "$body" '"tools"'

echo "== 2. 成功调用（stdio echo） =="
code="$(request POST /api/v1/tools/demo-stdio/echo/call "$ANALYST" '{"text":"hello"}' || true)"
body="$(cat "$RESP_FILE")"
assert_status "成功调用 demo-stdio/echo" 200 "$code"

echo "== 3. 无 Token 401 =="
code="$(request GET /api/v1/tools || true)"
body="$(cat "$RESP_FILE")"
assert_status "无 Token 调用" 401 "$code"
assert_contains "401 错误码" "$body" "AUTH_INVALID_TOKEN"

echo "== 4. 无权限 403 =="
code="$(request POST /api/v1/tools/demo-http/echo/call "$GUEST" '{"text":"hi"}' || true)"
body="$(cat "$RESP_FILE")"
assert_status "无权限调用（guest）" 403 "$code"
assert_contains "403 错误码" "$body" "POLICY_TOOL_DENIED"

echo "== 5. 触发 429 限流 =="
# requests=1：首次放行建立计数，第二次触发限流
code="$(request POST /api/v1/tools/demo-http/echo/call "$ANALYST" '{"text":"prime"}' || true)"
assert_status "限流预热调用（首次放行）" 200 "$code"
code="$(request POST /api/v1/tools/demo-http/echo/call "$ANALYST" '{"text":"trigger"}' || true)"
body="$(cat "$RESP_FILE")"
assert_status "触发限流（第二次）" 429 "$code"
assert_contains "429 错误码" "$body" "RATE_LIMIT_EXCEEDED"

echo "== 6. 超时 504 =="
code="$(request POST /api/v1/tools/demo-http/sleep/call "$ANALYST" '{"seconds":5}' || true)"
body="$(cat "$RESP_FILE")"
assert_status "调用 sleep(5s) 触发超时" 504 "$code"
assert_contains "504 错误码" "$body" "TOOL_TIMEOUT"

echo "== 7. 超时后恢复调用 =="
code="$(request POST /api/v1/tools/demo-http/sleep/call "$ANALYST" '{"seconds":0.1}' || true)"
body="$(cat "$RESP_FILE")"
assert_status "超时后恢复（sleep 0.1s）" 200 "$code"

echo ""
echo "All MCP Governance Gateway demo scenarios passed."
