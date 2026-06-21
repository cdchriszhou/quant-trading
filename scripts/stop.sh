#!/bin/bash
#
# stop.sh — Stop all services
# Usage: ./scripts/stop.sh [--docker]
#

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$PROJECT_ROOT/.run"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ──────────────────────────────────────────────
# Docker mode
# ──────────────────────────────────────────────
if [ "$1" = "--docker" ]; then
    log_info "停止 Docker 容器..."
    cd "$PROJECT_ROOT"
    docker-compose down
    log_info "Docker 容器已停止"
    exit 0
fi

# ──────────────────────────────────────────────
# Local mode: stop by PID file
# ──────────────────────────────────────────────
stopped_any=false

for svc in backend frontend; do
    PID_FILE="$RUN_DIR/${svc}.pid"
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            log_info "停止 ${svc} (PID: $PID)..."
            kill "$PID" 2>/dev/null || true
            # Wait for graceful shutdown
            for i in $(seq 1 5); do
                if ! kill -0 "$PID" 2>/dev/null; then
                    break
                fi
                sleep 0.5
            done
            # Force kill if still running
            if kill -0 "$PID" 2>/dev/null; then
                log_warn "${svc} 未正常退出，执行强制停止..."
                kill -9 "$PID" 2>/dev/null || true
            fi
            log_info "${svc} 已停止"
            stopped_any=true
        else
            log_warn "${svc} 进程 (PID: $PID) 已不存在"
        fi
        rm -f "$PID_FILE"
    else
        # Fallback: try to find by pattern
        log_warn "未找到 ${svc} 的 PID 文件，尝试通过端口查找..."
    fi
done

# ── Fallback: find by port ─────────────────────
# Backend on :8000
BK_PID=$(lsof -ti:8000 2>/dev/null || true)
if [ -n "$BK_PID" ]; then
    log_info "通过端口 :8000 找到后端进程 (PID: $BK_PID)，正在停止..."
    kill $BK_PID 2>/dev/null || true
    stopped_any=true
fi

# Frontend on :8888
FE_PID=$(lsof -ti:8888 2>/dev/null || true)
if [ -n "$FE_PID" ]; then
    log_info "通过端口 :8888 找到前端进程 (PID: $FE_PID)，正在停止..."
    kill $FE_PID 2>/dev/null || true
    stopped_any=true
fi

# ── Also kill any related Python/Vite processes ──
# Kill any remaining uvicorn instances from this project
for PID in $(ps aux | grep -i "uvicorn app.main" | grep -v grep | awk '{print $2}' 2>/dev/null); do
    log_info "清理残留 uvicorn 进程 (PID: $PID)..."
    kill $PID 2>/dev/null || true
    stopped_any=true
done

for PID in $(ps aux | grep -i "vite.*quant-trading" | grep -v grep | awk '{print $2}' 2>/dev/null); do
    log_info "清理残留 vite 进程 (PID: $PID)..."
    kill $PID 2>/dev/null || true
    stopped_any=true
done

# Clean up log files
rm -f "$RUN_DIR/backend.log" "$RUN_DIR/frontend.log"

if [ "$stopped_any" = true ]; then
    log_info "所有服务已停止"
else
    log_info "没有运行中的服务"
fi
