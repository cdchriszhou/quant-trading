#!/bin/bash
# Convenience wrapper — starts quant trading system
cd "$(dirname "$0")"
exec bash scripts/start.sh "$@"
