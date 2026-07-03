#!/bin/bash
#
# build.sh — Build the deployable package locally
# Usage: ./build.sh
#
# Wrapper around build.py that bypasses macOS system proxy
# (which may be configured but not running).
#
set -e

cd "$(dirname "$0")"

# Bypass system proxy (macOS proxy may be set in Network Preferences
# but the proxy app like Clash may not be running)
NO_PROXY="*" no_proxy="*" \
HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
http_proxy="" https_proxy="" all_proxy="" \
python3 build.py
