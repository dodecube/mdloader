#!/usr/bin/env bash
# Launcher for Linux/macOS.
exec "${MDLOADER_PYTHON:-python3}" "$(cd "$(dirname "$0")/.." && pwd)/host" "$@"
