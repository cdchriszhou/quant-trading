"""
Quant Trading System - Build for Deployment

Produces:
  quant-trading-prod-<timestamp>.zip  - deploy package (quant-trading/ ...)
  quant-update.sh                     - sibling updater (not inside the zip)

Package layout:
  quant-trading/
    backend/app/           Python application
    backend/requirements.txt
    frontend/              Vite production build (static)
    start.sh / stop.sh / rollback.sh
    .env.example
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DEPLOY = os.path.join(ROOT, "deploy")

TIMESTAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
ZIP_NAME = f"quant-trading-prod-{TIMESTAMP}.zip"
ZIP_FILE = os.path.join(ROOT, ZIP_NAME)

IGNORE_PY = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache")


def shell_scripts() -> dict[str, str]:
    """Return {filename: content} for Linux deployment scripts."""

    return {
        "start.sh": """\
#!/bin/bash
# Quant Trading System - Production Start
<<<<<<< HEAD
# Usage: ./start.sh [--foreground]
#   --foreground   Run in foreground (useful for local testing)
set -e
=======
set -euo pipefail
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/backend/quant.pid"
LOG_FILE="$SCRIPT_DIR/backend/quant.log"
VENV_DIR="$SCRIPT_DIR/.venv"
FOREGROUND=false

if [ "$1" = "--foreground" ] || [ "$1" = "-f" ]; then
    FOREGROUND=true
fi

# Colors
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
CYAN='\\033[0;36m'
NC='\\033[0m'

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "[ERROR] Already running (PID: $PID). Use stop.sh first."
        exit 1
    fi
    rm -f "$PID_FILE"
fi

if [ ! -f "backend/.env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example backend/.env
        echo "[WARN] Created backend/.env from .env.example"
        echo "[WARN] Edit SECRET_KEY / CORS / trading flags before going live."
    else
        echo "[ERROR] Missing backend/.env and .env.example"
        exit 1
    fi
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

<<<<<<< HEAD
# Install dependencies (bypass system proxy that may be down)
echo "Installing Python dependencies..."
cd "$SCRIPT_DIR/backend"
NO_PROXY="*" no_proxy="*" HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \\
    http_proxy="" https_proxy="" all_proxy="" \\
    "$VENV_DIR/bin/pip" install -r requirements.txt -q

# Start server
echo "Starting Quant Trading System..."
export STATIC_DIR="$SCRIPT_DIR/frontend"

if $FOREGROUND; then
    echo ""
    echo -e "  ${GREEN}■${NC} Frontend:    http://localhost:8000"
    echo -e "  ${GREEN}■${NC} API Docs:    http://localhost:8000/api/docs"
    echo -e "  ${YELLOW}Press Ctrl+C to stop${NC}"
    echo ""
    exec "$VENV_DIR/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
else
    nohup "$VENV_DIR/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    # Wait for health check
    echo -n "  Waiting for server..."
    for i in $(seq 1 30); do
        if curl -s http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
            echo -e " ${GREEN}✓${NC}"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo -e " ${YELLOW}⚠${NC}"
            echo "[WARN] Server may still be starting. Check logs: $LOG_FILE"
        fi
        echo -n "."
        sleep 1
    done

    echo ""
    echo -e "  ${GREEN}■${NC} Frontend:    http://localhost:8000"
    echo -e "  ${GREEN}■${NC} API Docs:    http://localhost:8000/api/docs"
    echo -e "  ${GREEN}■${NC} PID:         $(cat "$PID_FILE")"
    echo -e "  ${GREEN}■${NC} Logs:        $LOG_FILE"
    echo ""
    echo "  Use ./stop.sh to stop the service."
fi
=======
echo "Installing Python dependencies..."
cd "$SCRIPT_DIR/backend"
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r requirements.txt -q

echo "Starting Quant Trading System..."
export STATIC_DIR="$SCRIPT_DIR/frontend"
nohup "$VENV_DIR/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> "$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"

sleep 1
if ! kill -0 "$PID" 2>/dev/null; then
    echo "[ERROR] Process exited immediately. Check logs: $LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi

echo "Started (PID: $PID)"
echo "  App:  http://localhost:8000"
echo "  Logs: $LOG_FILE"
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
""",
        "stop.sh": """\
#!/bin/bash
# Quant Trading System - Production Stop
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/backend/quant.pid"

stop_pid() {
    local PID="$1"
    echo "Stopping Quant Trading System (PID: $PID)..."
    if kill "$PID" 2>/dev/null; then
        for _ in $(seq 1 10); do
            if ! kill -0 "$PID" 2>/dev/null; then
                echo "Stopped gracefully."
                return 0
            fi
            sleep 1
        done
        echo "Force stopping..."
        kill -9 "$PID" 2>/dev/null || true
    else
        echo "Process not running."
    fi
}

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    stop_pid "$PID"
    rm -f "$PID_FILE"
    echo "Stopped."
    exit 0
fi

echo "No PID file found. Trying port 8000..."
PIDS=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "$PIDS" ]; then
    for PID in $PIDS; do
        stop_pid "$PID"
    done
else
    echo "No process found on port 8000."
fi
""",
        # Lives next to the zip (not inside quant-trading/)
        "quant-update.sh": """\
#!/bin/bash
# Quant Trading System - Update / First Deploy from zip
# Place beside:
#   - quant-trading-prod-*.zip
#   - quant-trading/   (created/updated)
#
# Usage:
#   ./quant-update.sh
#   ./quant-update.sh quant-trading-prod-xxx.zip
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR/quant-trading"

ZIP_FILE="${1:-}"
if [ -z "$ZIP_FILE" ]; then
    ZIP_FILE=$(ls -1t "$SCRIPT_DIR"/quant-trading-prod-*.zip 2>/dev/null | head -1 || true)
    if [ -z "$ZIP_FILE" ]; then
        echo "Usage: ./quant-update.sh [deploy.zip]"
        echo "  No zip specified and no quant-trading-prod-*.zip found in $SCRIPT_DIR"
        exit 1
    fi
    echo "Auto-detected: $(basename "$ZIP_FILE")"
fi

if [ ! -f "$ZIP_FILE" ]; then
    echo "[ERROR] File not found: $ZIP_FILE"
    exit 1
fi

IS_FIRST_DEPLOY=false
if [ ! -d "$APP_DIR" ]; then
    IS_FIRST_DEPLOY=true
fi

BACKUP_DIR="$APP_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
TMP_DIR="$SCRIPT_DIR/.update_tmp"

echo "============================================"
echo "  Quant Trading System - Update"
echo "  Package: $(basename "$ZIP_FILE")"
if $IS_FIRST_DEPLOY; then
    echo "  Mode:    First deploy"
fi
echo "============================================"
echo

# 1. Stop
if $IS_FIRST_DEPLOY; then
    echo "[1/6] First deploy, no old service to stop."
else
    echo "[1/6] Stopping old service..."
    if [ -f "$APP_DIR/stop.sh" ]; then
        bash "$APP_DIR/stop.sh" || true
    else
        PID=$(lsof -ti :8000 2>/dev/null || true)
        [ -n "$PID" ] && kill $PID && sleep 2 || true
        echo "  Stopped."
    fi
fi

# 2. Backup
if $IS_FIRST_DEPLOY; then
    echo
    echo "[2/6] First deploy, nothing to backup."
else
    echo
    echo "[2/6] Backing up old data..."
    mkdir -p "$BACKUP_DIR"
    tar -czf "$BACKUP_FILE" \
        -C "$APP_DIR" \
        --ignore-failed-read \
        backend/.env \
        backend/*.db \
        backend/*.db-shm \
        backend/*.db-wal \
        backend/app \
        backend/requirements.txt \
        2>/dev/null || true

    if [ -s "$BACKUP_FILE" ]; then
        echo "  Backup: $BACKUP_FILE"
        COUNT=$(tar -tzf "$BACKUP_FILE" 2>/dev/null | wc -l | tr -d ' ')
        echo "  $COUNT files archived"
    else
        rm -f "$BACKUP_FILE"
        echo "  (no old data to backup)"
        BACKUP_FILE=""
    fi

    ls -t "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | tail -n +31 | xargs rm -f 2>/dev/null || true
fi

# 3. Unzip
echo
echo "[3/6] Extracting new package..."
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
unzip -o -q "$ZIP_FILE" -d "$TMP_DIR"

SRC="$TMP_DIR"
if [ -d "$TMP_DIR/quant-trading" ]; then
    SRC="$TMP_DIR/quant-trading"
fi

echo "  Contents:"
ls -la "$SRC" | sed 's/^/    /'

# 4. Deploy
echo
echo "[4/6] Deploying new code..."
if $IS_FIRST_DEPLOY; then
    mv "$SRC" "$APP_DIR"
    echo "  quant-trading/ created from zip"
else
    if [ -d "$SRC/backend/app" ]; then
        rm -rf "$APP_DIR/backend/app"
        cp -r "$SRC/backend/app" "$APP_DIR/backend/app"
        echo "  backend/app/ updated"
    fi
    if [ -f "$SRC/backend/requirements.txt" ]; then
        mkdir -p "$APP_DIR/backend"
        cp "$SRC/backend/requirements.txt" "$APP_DIR/backend/requirements.txt"
        echo "  backend/requirements.txt updated"
    fi
    if [ -d "$SRC/frontend" ]; then
        rm -rf "$APP_DIR/frontend"
        cp -r "$SRC/frontend" "$APP_DIR/frontend"
        echo "  frontend/ updated"
    fi
    if [ -f "$SRC/.env.example" ]; then
        cp "$SRC/.env.example" "$APP_DIR/.env.example"
        echo "  .env.example updated (existing backend/.env kept)"
    fi
    for script in start.sh stop.sh rollback.sh; do
        if [ -f "$SRC/$script" ]; then
            cp "$SRC/$script" "$APP_DIR/$script"
            chmod +x "$APP_DIR/$script"
            echo "  $script updated"
        fi
    done
fi

# 5. Config / restore
if $IS_FIRST_DEPLOY; then
    echo
    echo "[5/6] First deploy, creating default config..."
    if [ ! -f "$APP_DIR/backend/.env" ] && [ -f "$APP_DIR/.env.example" ]; then
        cp "$APP_DIR/.env.example" "$APP_DIR/backend/.env"
        echo "  Created backend/.env from .env.example"
        echo "  >>> Edit SECRET_KEY and production flags before start.sh <<<"
    fi
else
    echo
    echo "[5/6] Restoring data..."
    if [ -n "${BACKUP_FILE:-}" ] && [ -f "$BACKUP_FILE" ]; then
        tar -xzf "$BACKUP_FILE" -C "$APP_DIR" backend/.env 2>/dev/null && \
            echo "  .env restored" || echo "  No .env in backup"
        tar -xzf "$BACKUP_FILE" -C "$APP_DIR" \
            --wildcards 'backend/*.db' \
            --wildcards 'backend/*.db-shm' \
            --wildcards 'backend/*.db-wal' \
            2>/dev/null && echo "  Database restored" || echo "  No database in backup"
    fi
fi

rm -rf "$TMP_DIR"

# 6. Deps + start
echo
echo "[6/6] Installing dependencies and starting..."
<<<<<<< HEAD
cd "$APP_DIR/backend"
VENV_DIR="$APP_DIR/.venv"
if [ ! -f "$VENV_DIR/bin/python" ]; then
    python3 -m venv "$VENV_DIR"
fi
NO_PROXY="*" no_proxy="*" HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \\
    http_proxy="" https_proxy="" all_proxy="" \\
    "$VENV_DIR/bin/pip" install -r requirements.txt -q
echo "  Done."

echo
echo "Starting service..."
=======
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
cd "$APP_DIR"
chmod +x start.sh stop.sh rollback.sh 2>/dev/null || true
bash start.sh

echo
echo "============================================"
echo "  Update complete!"
if [ -n "${BACKUP_FILE:-}" ] && [ -f "$BACKUP_FILE" ]; then
    echo "  Backup: $BACKUP_FILE"
fi
echo "============================================"
""",
        "rollback.sh": """\
#!/bin/bash
# Quant Trading System - Rollback to a previous backup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
BACKUP_DIR="$SCRIPT_DIR/backups"

if [ -z "${1:-}" ]; then
    echo "Usage: ./rollback.sh <backup-file>"
    echo "Available backups:"
    if [ -d "$BACKUP_DIR" ]; then
        ls -1t "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | head -20 | while read -r f; do
            SIZE=$(du -h "$f" 2>/dev/null | cut -f1)
            echo "  $(basename "$f")  ($SIZE)"
        done
    else
        echo "  (no backups found)"
    fi
    exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
    BACKUP_FILE="$BACKUP_DIR/$1"
fi
if [ ! -f "$BACKUP_FILE" ]; then
    echo "[ERROR] Backup not found: $1"
    exit 1
fi

echo "============================================"
echo "  Rollback to: $(basename "$BACKUP_FILE")"
echo "============================================"
echo

echo "[1/3] Stopping service..."
if [ -f "$SCRIPT_DIR/stop.sh" ]; then
    bash "$SCRIPT_DIR/stop.sh" || true
fi

echo
echo "[2/3] Restoring from backup..."
tar -xzf "$BACKUP_FILE" -C "$SCRIPT_DIR"
echo "  Restored."

echo
echo "[3/3] Restarting service..."
cd "$SCRIPT_DIR"
bash start.sh

echo
echo "============================================"
echo "  Rollback complete."
echo "============================================"
""",
    }


def _require_tools() -> None:
    for cmd, hint in (
        ("npm", "Install Node.js 18+"),
        ("node", "Install Node.js 18+"),
    ):
        if shutil.which(cmd) is None:
            raise SystemExit(f"[ERROR] `{cmd}` not found. {hint}")


def main() -> None:
    print("=" * 44)
    print("  Quant Trading System - Build for Deploy")
    print("=" * 44)
    print()

    _require_tools()

    # ---- Clean --------------------------------------------------
    print("[1/4] Cleaning previous build...")
    if os.path.exists(DEPLOY):
        shutil.rmtree(DEPLOY)
    os.makedirs(DEPLOY)
    for old_zip in os.listdir(ROOT):
        if old_zip.startswith("quant-trading-prod-") and old_zip.endswith(".zip"):
            os.remove(os.path.join(ROOT, old_zip))
            print(f"  Removed old: {old_zip}")
    print("  Done.")

    # ---- Build frontend -----------------------------------------
    print()
    print("[2/4] Building frontend...")
    frontend_dir = os.path.join(ROOT, "frontend")
<<<<<<< HEAD
    # Build with proxy bypass (macOS system proxy may be set but app not running)
    build_env = os.environ.copy()
    for k in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
        build_env.pop(k, None)
    build_env["NO_PROXY"] = "*"
    build_env["no_proxy"] = "*"
    if not os.path.isdir(os.path.join(frontend_dir, "node_modules")):
        subprocess.run("npm install", cwd=frontend_dir, shell=True, check=True, env=build_env)
    subprocess.run("npm run build", cwd=frontend_dir, shell=True, check=True, env=build_env)
=======
    node_modules = os.path.join(frontend_dir, "node_modules")
    if not os.path.isdir(node_modules):
        print("  npm install...")
        subprocess.run("npm install", cwd=frontend_dir, shell=True, check=True)
    subprocess.run("npm run build", cwd=frontend_dir, shell=True, check=True)
    frontend_dist = os.path.join(frontend_dir, "dist")
    if not os.path.isdir(frontend_dist) or not os.path.isfile(
        os.path.join(frontend_dist, "index.html")
    ):
        raise SystemExit("[ERROR] frontend/dist/index.html missing after build")
>>>>>>> 4b5774d (feat: add stock recommend, insight popup, and trading UX upgrades)
    print("  Frontend built.")

    # ---- Package ------------------------------------------------
    print()
    print("[3/4] Packaging...")

    app_dir = os.path.join(DEPLOY, "quant-trading")
    backend_src = os.path.join(ROOT, "backend")
    req_src = os.path.join(backend_src, "requirements.txt")
    env_src = os.path.join(backend_src, ".env.example")

    if not os.path.isfile(req_src):
        raise SystemExit("[ERROR] backend/requirements.txt missing")
    if not os.path.isfile(env_src):
        raise SystemExit("[ERROR] backend/.env.example missing")

    shutil.copytree(
        os.path.join(backend_src, "app"),
        os.path.join(app_dir, "backend", "app"),
        ignore=IGNORE_PY,
    )
    shutil.copy2(req_src, os.path.join(app_dir, "backend", "requirements.txt"))
    shutil.copytree(frontend_dist, os.path.join(app_dir, "frontend"))
    shutil.copy2(env_src, os.path.join(app_dir, ".env.example"))

    for name, content in shell_scripts().items():
        if name == "quant-update.sh":
            path = os.path.join(DEPLOY, name)
        else:
            path = os.path.join(app_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        # Mark executable bit in zip via external attr on Unix; on Windows
        # chmod is applied by quant-update.sh / first deploy instructions.

    # ---- Zip ----------------------------------------------------
    print()
    print("[4/4] Creating zip...")
    with zipfile.ZipFile(ZIP_FILE, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(app_dir):
            for fname in files:
                full = os.path.join(root, fname)
                arcname = os.path.relpath(full, DEPLOY)  # quant-trading/...
                # Ensure shell scripts are executable when unzipped on Unix
                if fname.endswith(".sh"):
                    info = zipfile.ZipInfo(arcname.replace("\\", "/"))
                    info.date_time = datetime.now().timetuple()[:6]
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o755 << 16
                    with open(full, "rb") as sf:
                        zf.writestr(info, sf.read())
                else:
                    zf.write(full, arcname.replace("\\", "/"))

    zip_size = os.path.getsize(ZIP_FILE)
    print(f"  {ZIP_NAME} ({zip_size / 1024:.0f} KB)")

    shutil.copy2(
        os.path.join(DEPLOY, "quant-update.sh"),
        os.path.join(ROOT, "quant-update.sh"),
    )
    # Preserve executable bit for local WSL/Git Bash users
    try:
        os.chmod(os.path.join(ROOT, "quant-update.sh"), 0o755)
    except OSError:
        pass

    shutil.rmtree(DEPLOY)

    print()
    print("=" * 44)
    print("  Build complete!")
    print(f"    {ZIP_NAME}")
    print("    quant-update.sh")
    print("=" * 44)
    print()
    print("  --- First deploy ---")
    print()
    print(f"    scp {ZIP_NAME} quant-update.sh user@host:/opt/")
    print("    ssh user@host")
    print("    cd /opt && chmod +x quant-update.sh")
    print("    ./quant-update.sh")
    print("    vim quant-trading/backend/.env   # SECRET_KEY / flags")
    print("    cd quant-trading && ./stop.sh && ./start.sh")
    print()
    print("  --- Update (keeps DB + .env) ---")
    print()
    print(f"    scp {ZIP_NAME} quant-update.sh user@host:/opt/")
    print("    ssh user@host 'cd /opt && ./quant-update.sh'")
    print()
    print("  --- Rollback ---")
    print()
    print("    cd /opt/quant-trading")
    print("    ./rollback.sh                   # list")
    print("    ./rollback.sh backups/backup_xxx.tar.gz")
    print("=" * 44)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Command failed with exit code {e.returncode}", file=sys.stderr)
        sys.exit(e.returncode or 1)
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
