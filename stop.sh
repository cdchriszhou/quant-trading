#!/bin/bash
# Convenience wrapper — stops quant trading system
cd "$(dirname "$0")"
exec bash scripts/stop.sh "$@"
