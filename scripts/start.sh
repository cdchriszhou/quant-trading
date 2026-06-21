#!/bin/bash
#
# start.sh — Start all services for local development
# Usage: ./scripts/start.sh [--docker]
#
# Options:
#   --docker    Start via docker-compose instead of local processes
#

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$PROJECT_ROOT/.run"
mkdir -p "$RUN_DIR"

cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "\n${CYAN}══════════════════════════════════════════════════${NC}"; echo -e "${CYAN}  $1${NC}"; echo -e "${CYAN}══════════════════════════════════════════════════${NC}"; }

cleanup() {
    log_warn "收到中断信号，正在停止服务..."
    bash "$PROJECT_ROOT/scripts/stop.sh" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# ──────────────────────────────────────────────
# Docker mode
# ──────────────────────────────────────────────
if [ "$1" = "--docker" ]; then
    log_step "启动 Docker 容器"
    cd "$PROJECT_ROOT"
    docker-compose up -d
    log_info "Docker 容器已启动"
    echo ""
    echo -e "  Frontend: ${GREEN}http://localhost:80${NC}"
    echo -e "  Backend:  ${GREEN}http://localhost:8000${NC}"
    echo -e "  API Docs: ${GREEN}http://localhost:8000/api/docs${NC}"
    echo ""
    exit 0
fi

# ──────────────────────────────────────────────
# Local mode
# ──────────────────────────────────────────────

# ── Check prerequisites ────────────────────────
log_step "检查环境依赖"

if ! command -v python3 &>/dev/null; then
    log_error "未找到 python3，请先安装 Python 3.9+"
    exit 1
fi
log_info "python3: $(python3 --version)"

if ! command -v node &>/dev/null; then
    log_error "未找到 node，请先安装 Node.js 16+"
    exit 1
fi
log_info "node: $(node --version)"
log_info "npm:  $(npm --version)"

# Check if pip packages are installed
if python3 -c "import fastapi" 2>/dev/null; then
    log_info "Python 依赖已安装"
else
    log_warn "Python 依赖未安装，正在安装..."
    pip3 install -r "$PROJECT_ROOT/backend/requirements.txt" -q
    log_info "Python 依赖安装完成"
fi

# Check if node_modules exist
if [ -d "$PROJECT_ROOT/frontend/node_modules" ]; then
    log_info "Node 依赖已安装"
else
    log_warn "Node 依赖未安装，正在安装..."
    cd "$PROJECT_ROOT/frontend" && npm install --silent
    log_info "Node 依赖安装完成"
fi

# ── Start Backend ──────────────────────────────
log_step "启动后端服务 (FastAPI)"

# Kill any existing backend process
if [ -f "$RUN_DIR/backend.pid" ]; then
    OLD_PID=$(cat "$RUN_DIR/backend.pid")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        log_warn "后端已在运行 (PID: $OLD_PID)，先停止..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
    fi
fi

cd "$PROJECT_ROOT/backend"
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    > "$RUN_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$RUN_DIR/backend.pid"
log_info "后端已启动 (PID: $BACKEND_PID)"
log_info "日志: $RUN_DIR/backend.log"

# Wait for backend to be ready
cd "$PROJECT_ROOT"
echo -n "  等待后端就绪..."
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo -e " ${RED}✗${NC}"
        log_error "后端启动超时，请检查日志: $RUN_DIR/backend.log"
        exit 1
    fi
    echo -n "."
    sleep 1
done

# ── Start Frontend ─────────────────────────────
log_step "启动前端服务 (Vite)"

# Kill any existing frontend process
if [ -f "$RUN_DIR/frontend.pid" ]; then
    OLD_PID=$(cat "$RUN_DIR/frontend.pid")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        log_warn "前端已在运行 (PID: $OLD_PID)，先停止..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
    fi
fi

cd "$PROJECT_ROOT/frontend"
nohup npx vite --host 0.0.0.0 --port 8888 \
    > "$RUN_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$RUN_DIR/frontend.pid"
log_info "前端已启动 (PID: $FRONTEND_PID)"
log_info "日志: $RUN_DIR/frontend.log"

# Wait for frontend
echo -n "  等待前端就绪..."
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8888 >/dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo -e " ${YELLOW}⚠${NC}"
        log_warn "前端启动可能较慢，继续等待..."
        # Don't exit, frontend may take longer
    fi
    echo -n "."
    sleep 1
done

# ── Summary ────────────────────────────────────
log_step "启动完成"

echo ""
echo -e "  ${GREEN}■${NC} Frontend:    http://localhost:8888"
echo -e "  ${GREEN}■${NC} Backend:     http://localhost:8000"
echo -e "  ${GREEN}■${NC} API Docs:    http://localhost:8000/api/docs"
echo -e "  ${GREEN}■${NC} Backend PID: ${BACKEND_PID}"
echo -e "  ${GREEN}■${NC} Frontend PID: ${FRONTEND_PID}"
echo ""
echo -e "  使用 ${CYAN}./scripts/stop.sh${NC} 停止所有服务"
echo ""

# Tail logs if running in foreground
if [ -t 1 ]; then
    echo -e "${YELLOW}提示: 按 Ctrl+C 停止所有服务${NC}"
    echo ""
    # Wait and follow logs
    tail -f "$RUN_DIR/backend.log" "$RUN_DIR/frontend.log" 2>/dev/null &
    TAIL_PID=$!
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    kill $TAIL_PID 2>/dev/null || true
fi
