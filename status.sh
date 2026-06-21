#!/bin/bash
# Convenience wrapper — checks quant trading system status
cd "$(dirname "$0")"
exec bash scripts/status.sh "$@"
