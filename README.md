# DevMem

DevMem is a local-first MCP memory server for coding agents. It records small,
explicit developer memories such as gotchas, error fixes, and architecture
decisions, then retrieves them in later sessions.

The base install stores data in local SQLite and uses deterministic local hash
embeddings. It does not need API keys or remote services.

Source: <https://github.com/leonstnyc/devmem-mcp>

## Install

```bash
pipx install "git+https://github.com/leonstnyc/devmem-mcp.git"
devmem status
devmem preflight-mcp
```

For local development from this repository:

```bash
pip install -e ".[dev]"
devmem status
```

## First Memory

```bash
devmem report \
  --kind codebase_gotcha \
  --summary-text "Tests need a repo slug" \
  --text "Set DEVMEM_REPO_SLUG=owner/project before running MCP preflight."

devmem search "repo slug"
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

## Optional Extras

Use the distribution name when installing extras:

```bash
pip install "devmem-mcp[openai] @ git+https://github.com/leonstnyc/devmem-mcp.git"
pip install "devmem-mcp[api] @ git+https://github.com/leonstnyc/devmem-mcp.git"
```

OpenAI embeddings are enabled only when `OPENAI_API_KEY` is set and
`DEVMEM_FORCE_LOCAL_EMBEDDER` is not enabled. The optional HTTP API starts with:

```bash
devmem api --host 127.0.0.1 --port 8765
```

## Privacy

DevMem writes notes, metadata, feedback, and embeddings to
`~/.devmem/devmem.db` by default. It has no telemetry. OpenAI embeddings are an
optional upgrade path and are used only when the OpenAI extra is installed and
configured.

## Troubleshooting

- Run `devmem preflight-mcp --quiet` before wiring an MCP client.
- Set `DEVMEM_REPO_SLUG=owner/project` when using DevMem outside a Git clone.
- Set `DEVMEM_SQLITE_PATH=.devmem/devmem.db` for a project-local database.
- If an optional command reports a missing extra, reinstall from GitHub with the
  matching `devmem-mcp[...]` extra.

See `docs/install.md`, `docs/configuration.md`, `docs/mcp-clients.md`,
`docs/openai.md`, `docs/api.md`, `docs/privacy.md`, and
`docs/development.md` for the full setup details.
