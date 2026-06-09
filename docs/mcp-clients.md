# MCP Clients

## Codex

Codex reads MCP servers from `~/.codex/config.toml`:

```toml
[mcp_servers.devmem]
command = "devmem"
args = ["mcp"]

[mcp_servers.devmem.env]
DEVMEM_REPO_SLUG = "owner/project"
```

See `examples/codex-config.toml` for a copyable snippet.

## Claude Code

Register the server with the CLI:

```bash
claude mcp add-json devmem '{"command": "devmem", "args": ["mcp"], "env": {"DEVMEM_REPO_SLUG": "owner/project"}}'
```

Or add it to a project `.mcp.json`:

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

## Preflight

Run this before connecting an MCP client:

```bash
devmem preflight-mcp
```

The preflight command starts `python -m devmem mcp`, sends the MCP initialize
and tool-list messages, and verifies the base tools:

- `devmem_report`
- `devmem_lookup`
- `devmem_diagnose`
- `devmem_feedback`
- `devmem_search`
- `devmem_status`

## Hook Templates

Portable templates are packaged under `devmem.hooks.templates`. They use the
installed `devmem` command and exit quietly if it is unavailable. Run
`devmem hooks` to print their installed paths and a ready-to-paste Claude Code
settings block. For full session-hook wiring (Claude Code and Codex), the
`DEVMEM_SESSION_QUERY` control, and an agent policy snippet, see
`docs/agent-workflow.md`.

## Memory Scope

Memories are scoped by `tenant_id` and database path, not by repository — all
repos share one pool by default. See the Memory Scope section of
`docs/configuration.md` to choose per-project isolation.
