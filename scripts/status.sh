#!/bin/bash
#
# status.sh — Check service status
# Usage: ./scripts/status.sh
#

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$PROJECT_ROOT/.run"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log_ok()    { echo -e "  ${GREEN}●${NC} $1"; }
log_dead()  { echo -e "  ${RED}●${NC} $1"; }
log_na()    { echo -e "  ${YELLOW}○${NC} $1"; }

echo ""
echo -e "${CYAN}══════════════════════════════════════${NC}"
echo -e "${CYAN}  量化交易系统 — 服务状态${NC}"
echo -e "${CYAN}══════════════════════════════════════${NC}"
echo ""

# ── Backend ────────────────────────────────────
echo -e "  ${CYAN}■ 后端服务 (FastAPI :8000)${NC}"
BK_PID=$(lsof -ti:8000 2>/dev/null || true)
if [ -n "$BK_PID" ]; then
    BK_CMD=$(ps -p "$BK_PID" -o command= 2>/dev/null | head -c 80)
    log_ok "运行中 (PID: $BK_PID) — ${BK_CMD}"
    # Health check
    HEALTH=$(curl -s http://127.0.0.1:8000/api/health 2>/dev/null || echo '{"status":"unreachable"}')
    HEALTH_STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown")
    if [ "$HEALTH_STATUS" = "ok" ]; then
        echo -e "           ${GREEN}健康检查: ✓${NC}"
    else
        echo -e "           ${RED}健康检查: ✗ ($HEALTH_STATUS)${NC}"
    fi
else
    log_dead "未运行"
fi
echo ""

# ── Frontend ───────────────────────────────────
echo -e "  ${CYAN}■ 前端服务 (Vite :8888)${NC}"
FE_PID=$(lsof -ti:8888 2>/dev/null || true)
if [ -n "$FE_PID" ]; then
    FE_CMD=$(ps -p "$FE_PID" -o command= 2>/dev/null | head -c 80)
    log_ok "运行中 (PID: $FE_PID) — ${FE_CMD}"
    if curl -s http://127.0.0.1:8888 >/dev/null 2>&1; then
        echo -e "           ${GREEN}HTTP 响应: ✓${NC}"
    else
        echo -e "           ${YELLOW}HTTP 响应: ✗${NC}"
    fi
else
    log_dead "未运行"
fi
echo ""

# ── Docker ─────────────────────────────────────
echo -e "  ${CYAN}■ Docker 容器${NC}"
if command -v docker &>/dev/null && docker ps 2>/dev/null | grep -q "quant-trading"; then
    docker ps --filter "name=quant" --format "  ${GREEN}●${NC} {{.Names}} ({{.Status}})" 2>/dev/null
else
    log_na "未使用 Docker"
fi
echo ""

# ── Summary ────────────────────────────────────
echo -e "${CYAN}──────────────────────────────────────${NC}"
if [ -n "$BK_PID" ] && [ -n "$FE_PID" ]; then
    echo -e "  ${GREEN}所有服务运行正常${NC}"
elif [ -n "$BK_PID" ] || [ -n "$FE_PID" ]; then
    echo -e "  ${YELLOW}部分服务未运行，请检查${NC}"
else
    echo -e "  ${YELLOW}服务未启动，运行 ./scripts/start.sh${NC}"
fi
echo -e "${CYAN}──────────────────────────────────────${NC}"
echo ""
