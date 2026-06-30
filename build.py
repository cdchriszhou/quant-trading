"""
Quant Trading System - Build for Deployment

Produces deploy.zip containing:
  backend/app/     - Python application code
  frontend/        - Compiled static files (vite build)
  start.sh         - Production start (background, PID tracking)
  stop.sh          - Production stop (graceful shutdown)
  quant-update.sh  - Update from zip (backup -> unzip -> restore data)
  rollback.sh      - Rollback to any previous backup
  .env.example     - Configuration template
"""

import os
import sys
import shutil
import subprocess
import zipfile
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DEPLOY = os.path.join(ROOT, "deploy")

# Zip filename with timestamp, e.g. quant-trading-prod-20260621-233457.zip
TIMESTAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
ZIP_NAME = f"quant-trading-prod-{TIMESTAMP}.zip"
ZIP_FILE = os.path.join(ROOT, ZIP_NAME)


def shell_scripts():
    """Return dict of {filename: content} for Linux deployment scripts."""

    return {
        # ============================================================
        "start.sh": """#!/bin/bash
# Quant Trading System - Production Start
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/backend/quant.pid"
LOG_FILE="$SCRIPT_DIR/backend/quant.log"
VENV_DIR="$SCRIPT_DIR/.venv"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "[ERROR] Already running (PID: $PID). Use stop.sh first."
        exit 1
    fi
    rm -f "$PID_FILE"
fi

# Ensure .env exists
if [ ! -f "backend/.env" ]; then
    cp -n .env.example backend/.env 2>/dev/null || true
    echo "[WARN] No backend/.env found. Created from .env.example - please edit it."
fi

# Setup virtual environment
if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Install dependencies
echo "Installing Python dependencies..."
cd "$SCRIPT_DIR/backend"
"$VENV_DIR/bin/pip" install -r requirements.txt -q

# Start server in background
echo "Starting Quant Trading System..."
export STATIC_DIR="$SCRIPT_DIR/frontend"
nohup "$VENV_DIR/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

echo "Started (PID: $!)"
echo "  API:      http://localhost:8000/api/docs"
echo "  Frontend: http://localhost:8000"
echo "  Logs:     $LOG_FILE"
""",
        # ============================================================
        "stop.sh": """#!/bin/bash
# Quant Trading System - Production Stop

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/backend/quant.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "No PID file found. Trying to find process by port..."
    PID=$(lsof -ti :8000 2>/dev/null || true)
    if [ -n "$PID" ]; then
        kill "$PID" 2>/dev/null && echo "Stopped PID: $PID" || echo "Failed to stop PID: $PID"
    else
        echo "No process found on port 8000."
    fi
    exit 0
fi

PID=$(cat "$PID_FILE")
echo "Stopping Quant Trading System (PID: $PID)..."

if kill "$PID" 2>/dev/null; then
    for i in $(seq 1 10); do
        if ! kill -0 "$PID" 2>/dev/null; then
            echo "Stopped gracefully."
            rm -f "$PID_FILE"
            exit 0
        fi
        sleep 1
    done
    echo "Force stopping..."
    kill -9 "$PID" 2>/dev/null || true
else
    echo "Process not running."
fi

rm -f "$PID_FILE"
echo "Stopped."
""",
        # ============================================================
        # quant-update.sh is NOT in the zip — it lives parallel to quant-trading/
        # so it can stop the old app, unzip the new one, and restore data safely.
        "quant-update.sh": """#!/bin/bash
# Quant Trading System - Update / First Deploy from zip
# Place this script in the SAME directory as:
#   - quant-trading-prod-*.zip   (the package)
#   - quant-trading/             (will be created/updated)
#
# Usage:
#   ./quant-update.sh                           # auto-find latest zip
#   ./quant-update.sh quant-trading-prod-xxx.zip  # specify zip
#
# Flow: unzip -> stop old -> backup data -> deploy -> restore data -> start
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR/quant-trading"

# Auto-detect zip if not specified
ZIP_FILE="$1"
if [ -z "$ZIP_FILE" ]; then
    ZIP_FILE=$(ls -1t "$SCRIPT_DIR"/quant-trading-prod-*.zip 2>/dev/null | head -1)
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

# 1. Stop old service (skip on first deploy)
if $IS_FIRST_DEPLOY; then
    echo "[1/6] First deploy, no old service to stop."
else
    echo "[1/6] Stopping old service..."
    if [ -f "$APP_DIR/stop.sh" ]; then
        bash "$APP_DIR/stop.sh"
    else
        PID=$(lsof -ti :8000 2>/dev/null || true)
        [ -n "$PID" ] && kill "$PID" && sleep 2
        echo "  Stopped."
    fi
fi

# 2. Backup old data (skip on first deploy)
if $IS_FIRST_DEPLOY; then
    echo
    echo "[2/6] First deploy, nothing to backup."
else
    echo
    echo "[2/6] Backing up old data..."
    mkdir -p "$BACKUP_DIR"
    tar -czf "$BACKUP_FILE" \
        -C "$APP_DIR" \
        backend/.env \
        backend/*.db \
        backend/*.db-shm \
        backend/*.db-wal \
        backend/app \
        2>/dev/null || true

    if [ -s "$BACKUP_FILE" ]; then
        echo "  Backup: $BACKUP_FILE"
        COUNT=$(tar -tzf "$BACKUP_FILE" 2>/dev/null | wc -l)
        echo "  $COUNT files archived"
    else
        rm -f "$BACKUP_FILE"
        echo "  (no old data to backup)"
    fi

    # Keep last 30 backups
    ls -t "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | tail -n +31 | xargs rm -f 2>/dev/null || true
fi

# 3. Unzip new package
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

# 4. Deploy new code
echo
echo "[4/6] Deploying new code..."
# If first deploy, just move the whole directory
if $IS_FIRST_DEPLOY; then
    mv "$SRC" "$APP_DIR"
    echo "  quant-trading/ created from zip"
else
    if [ -d "$SRC/backend/app" ]; then
        rm -rf "$APP_DIR/backend/app"
        cp -r "$SRC/backend/app" "$APP_DIR/backend/app"
        echo "  backend/app/ updated"
    fi
    if [ -d "$SRC/frontend" ]; then
        rm -rf "$APP_DIR/frontend"
        cp -r "$SRC/frontend" "$APP_DIR/frontend"
        echo "  frontend/ updated"
    fi
    if [ -f "$SRC/.env.example" ]; then
        cp "$SRC/.env.example" "$APP_DIR/.env.example"
        echo "  .env.example updated"
    fi
    for script in start.sh stop.sh rollback.sh; do
        if [ -f "$SRC/$script" ]; then
            cp "$SRC/$script" "$APP_DIR/$script"
            chmod +x "$APP_DIR/$script"
            echo "  $script updated"
        fi
    done
fi

# 5. Restore data from backup (skip on first deploy)
if $IS_FIRST_DEPLOY; then
    echo
    echo "[5/6] First deploy, creating default config..."
    if [ ! -f "$APP_DIR/backend/.env" ] && [ -f "$APP_DIR/.env.example" ]; then
        cp "$APP_DIR/.env.example" "$APP_DIR/backend/.env"
        echo "  Created backend/.env from .env.example"
    fi
else
    echo
    echo "[5/6] Restoring data..."
    if [ -f "$BACKUP_FILE" ]; then
        tar -xzf "$BACKUP_FILE" -C "$APP_DIR" backend/.env 2>/dev/null && \
            echo "  .env restored" || echo "  No .env in backup"
        tar -xzf "$BACKUP_FILE" -C "$APP_DIR" --wildcards 'backend/*.db' --wildcards 'backend/*.db-shm' --wildcards 'backend/*.db-wal' 2>/dev/null && \
            echo "  Database restored" || echo "  No database in backup"
    fi
fi

# Cleanup temp
rm -rf "$TMP_DIR"

# 6. Install dependencies and start
echo
echo "[6/6] Installing dependencies and starting..."
cd "$APP_DIR/backend"
VENV_DIR="$APP_DIR/.venv"
if [ ! -f "$VENV_DIR/bin/python" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install -r requirements.txt -q
echo "  Done."

echo
echo "Starting service..."
cd "$APP_DIR"
bash start.sh

echo
echo "============================================"
echo "  Update complete!"
if [ -f "$BACKUP_FILE" ]; then
    echo "  Backup: $BACKUP_FILE"
fi
echo "============================================"
""",
        # ============================================================
        "rollback.sh": """#!/bin/bash
# Quant Trading System - Rollback to a previous backup

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
BACKUP_DIR="$SCRIPT_DIR/backups"

if [ -z "$1" ]; then
    echo "Usage: ./rollback.sh <backup-file>"
    echo "Available backups:"
    if [ -d "$BACKUP_DIR" ]; then
        ls -1t "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | head -20 | while read f; do
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
    bash "$SCRIPT_DIR/stop.sh"
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


def main():
    print("=" * 44)
    print("  Quant Trading System - Build for Deploy")
    print("=" * 44)
    print()

    # ---- Clean --------------------------------------------------
    print("[1/3] Cleaning previous build...")
    if os.path.exists(DEPLOY):
        shutil.rmtree(DEPLOY)
    os.makedirs(DEPLOY)
    # Clean old zip files
    for old_zip in os.listdir(ROOT):
        if old_zip.startswith("quant-trading-prod-") and old_zip.endswith(".zip"):
            os.remove(os.path.join(ROOT, old_zip))
            print(f"  Removed old: {old_zip}")
    print("  Done.")

    # ---- Build frontend -----------------------------------------
    print()
    print("[2/3] Building frontend...")
    frontend_dir = os.path.join(ROOT, "frontend")
    if not os.path.isdir(os.path.join(frontend_dir, "node_modules")):
        subprocess.run("npm install", cwd=frontend_dir, shell=True, check=True)
    subprocess.run("npm run build", cwd=frontend_dir, shell=True, check=True)
    print("  Frontend built.")

    # ---- Package into deploy/ -----------------------------------
    print()
    print("[3/3] Packaging deploy.zip...")

    APP_DIR = os.path.join(DEPLOY, "quant-trading")

    # Backend code -> deploy/quant-trading/backend/app/
    shutil.copytree(
        os.path.join(ROOT, "backend", "app"),
        os.path.join(APP_DIR, "backend", "app"),
    )
    shutil.copy2(
        os.path.join(ROOT, "backend", "requirements.txt"),
        os.path.join(APP_DIR, "backend", "requirements.txt"),
    )

    # Frontend static -> deploy/quant-trading/frontend/
    frontend_dist = os.path.join(ROOT, "frontend", "dist")
    if os.path.isdir(frontend_dist):
        shutil.copytree(frontend_dist, os.path.join(APP_DIR, "frontend"))

    # Shell scripts inside quant-trading/
    for name, content in shell_scripts().items():
        if name == "quant-update.sh":
            # Write OUTSIDE quant-trading/, parallel to it
            path = os.path.join(DEPLOY, name)
        else:
            # Write INSIDE quant-trading/
            path = os.path.join(APP_DIR, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content.lstrip("\n"))

    # .env.example -> deploy/quant-trading/.env.example
    env_example = """\
# Quant Trading System - Production Configuration
# Copy to backend/.env and edit before starting.

APP_NAME="Quant Trading System"
DEBUG=false

# Database: sqlite (default) or mysql
DB_DRIVER=sqlite
# DB_HOST=127.0.0.1
# DB_PORT=3306
# DB_USER=root
# DB_PASSWORD=quant123
# DB_NAME=quant_trading

# Security - CHANGE this to a random string!
SECRET_KEY=change-this-to-a-random-secret

CORS_ORIGINS=["*"]

MARKET_DATA_SOURCE=realtime

TRADING_MODE=paper
DEFAULT_CASH=1000000.0
COMMISSION_RATE=0.00025
MIN_COMMISSION=5.0
"""
    with open(os.path.join(APP_DIR, ".env.example"), "w", encoding="utf-8", newline="\n") as f:
        f.write(env_example)

    # ---- Zip: zip the quant-trading/ directory as-is ------------
    with zipfile.ZipFile(ZIP_FILE, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(APP_DIR):
            for fname in files:
                full = os.path.join(root, fname)
                arcname = os.path.relpath(full, DEPLOY)  # quant-trading/backend/...
                zf.write(full, arcname)

    zip_size = os.path.getsize(ZIP_FILE)
    print(f"  {ZIP_NAME} created ({zip_size / 1024:.0f} KB)")
    up_size = os.path.getsize(os.path.join(DEPLOY, "quant-update.sh"))
    print(f"  quant-update.sh created ({up_size} B)")

    # Copy quant-update.sh to project root, then clean up deploy/
    shutil.copy2(
        os.path.join(DEPLOY, "quant-update.sh"),
        os.path.join(ROOT, "quant-update.sh"),
    )
    shutil.rmtree(DEPLOY)

    # ---- Done ---------------------------------------------------
    print()
    print("=" * 44)
    print(f"  Build complete!")
    print(f"    {ZIP_NAME}")
    print(f"    quant-update.sh")
    print("=" * 44)
    print()
    print("  --- First deploy to Linux ---")
    print()
    print(f"    scp {ZIP_NAME} quant-update.sh user@host:/opt/")
    print()
    print("    ssh user@host")
    print("    cd /opt")
    print(f"    unzip {ZIP_NAME}            # creates quant-trading/")
    print("    cd quant-trading")
    print("    cp .env.example backend/.env")
    print("    vim backend/.env            # change SECRET_KEY")
    print("    chmod +x *.sh && ./start.sh")
    print()
    print("  --- Update (preserves DB and config) ---")
    print()
    print("    python build.py")
    print(f"    scp {ZIP_NAME} quant-update.sh user@host:/opt/")
    print("    ssh user@host")
    print("    cd /opt")
    print(f"    ./quant-update.sh              # auto-detects {ZIP_NAME}")
    print()
    print("  --- Rollback ---")
    print()
    print("    ssh user@host")
    print("    cd /opt/quant-trading")
    print("    ./rollback.sh               # list backups")
    print("    ./rollback.sh backups/backup_20220622_140000.tar.gz")
    print("=" * 44)


if __name__ == "__main__":
    main()
