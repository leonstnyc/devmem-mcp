# DevMem

DevMem is a local-first MCP memory server for coding agents. It records small,
explicit developer memories such as gotchas, error fixes, and architecture
decisions, then retrieves them in later sessions.

The base install stores data in local SQLite and uses deterministic local hash
embeddings. It does not need API keys or remote services.

## Install

```bash
pipx install devmem-mcp
devmem status
devmem mcp
```

For local development from this repository:

```bash
pip install -e ".[dev]"
devmem status
```

## MCP Config

Codex and Claude Code can start DevMem with the same command:

```json
{
  "mcpServers": {
    "devmem": {
      "command": "devmem",
      "args": ["mcp"],
      "env": {
        "DEVMEM_REPO_SLUG": "owner/project"
      }
    }
  }
}
```

## Common Commands

```bash
devmem status
devmem report --kind codebase_gotcha --summary-text "Short summary" --text "Full note"
devmem search "sqlite setup"
devmem diagnose "OperationalError: no such table"
devmem feedback devmem:abc123 helpful
devmem preflight-mcp --quiet
devmem embed-pending
```

## Privacy

DevMem writes notes, metadata, feedback, and embeddings to
`~/.devmem/devmem.db` by default. It has no telemetry. OpenAI embeddings are an
optional upgrade path and are used only when the OpenAI extra is installed and
configured.

See `docs/configuration.md`, `docs/mcp-clients.md`, and `docs/privacy.md` for
the full setup details.
