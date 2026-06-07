#!/usr/bin/env sh
if ! command -v devmem >/dev/null 2>&1; then
  exit 0
fi

devmem preflight-mcp --quiet >/dev/null 2>&1 || true
devmem search "${DEVMEM_SESSION_QUERY:-recent project context}" --limit 5 2>/dev/null || true
