#!/usr/bin/env sh
if ! command -v devmem >/dev/null 2>&1; then
  exit 0
fi

devmem embed-pending >/dev/null 2>&1 || true
devmem cleanup-mcp --max-age 4 >/dev/null 2>&1 || true
