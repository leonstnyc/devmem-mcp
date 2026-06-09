# Configuration

All settings are environment variables. Values are read at runtime.

## Base Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEVMEM_SQLITE_PATH` | `~/.devmem/devmem.db` | SQLite database path. |
| `DEVMEM_REPO_SLUG` | Git remote slug or folder name | Repository identity. |
| `DEVMEM_REPO_ROOT` | Current working directory | Repository root used for slug detection. |
| `DEVMEM_TENANT_ID` | `default` | Tenant scope for reads, writes, and feedback. |
| `DEVMEM_CODE_INDEX_ENABLED` | `false` | Reserved for future code indexing. |
| `DEVMEM_CODE_MAX_SYMBOL_BYTES` | `8192` | Reserved code-indexing byte limit. |

## Optional Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | unset | Enables OpenAI embeddings when `devmem-mcp[openai]` is installed. |
| `DEVMEM_OPENAI_TIMEOUT_SECONDS` | `10` | Timeout for OpenAI embedding requests. |
| `DEVMEM_EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model. Ignored by the local hash embedder. |
| `DEVMEM_EMBEDDING_DIM` | `256` | Embedding dimension. |
| `DEVMEM_DATABASE_URL` | unset | Reserved for future external database support. |
| `DEVMEM_PRIMARY_STORE` | `sqlite` | Store selector. Only `sqlite` is available in preview. |
| `DEVMEM_API_KEY` | unset | Requires bearer-token auth when the API server is enabled. |
| `DEVMEM_HOST` | `127.0.0.1` | Optional API host. |
| `DEVMEM_PORT` | `8765` | Optional API port. |
| `DEVMEM_FORCE_LOCAL_EMBEDDER` | `false` | Force local embeddings even with an API key. |
| `DEVMEM_POSTGRES_CONNECT_TIMEOUT_SECONDS` | `5` | Reserved for future external database support. |
| `DEVMEM_SYMBOL_INDEXER_BIN` | unset | Reserved for future code indexing. |
| `DEVMEM_SYMBOL_INDEXER_TIMEOUT_SECONDS` | `5` | Reserved for future code indexing. |

## Hook Variables

These are read by the packaged session-hook templates, not by the Python code.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEVMEM_SESSION_QUERY` | `recent project context` | Search query `session_start.sh` runs to inject context at session start. |

`devmem status` prints the selected store, embedder, database path, note count,
and repository slug. It never prints API keys.

## Memory Scope

Retrieval is filtered by **two** things only: the `tenant_id` and the database
file (`DEVMEM_SQLITE_PATH`). `DEVMEM_REPO_SLUG` is recorded in each note's
metadata and shown by `devmem status`, but it is **not** a query filter. It
labels where a note came from; it does not partition search, lookup, diagnose,
or feedback.

So with the defaults (`tenant_id=default`, one shared `~/.devmem/devmem.db`),
**every repository shares one memory pool.** A gotcha recorded while working in
project A is retrievable while working in project B. That is intentional for
cross-project learning, but choose your isolation deliberately:

| Goal | Configuration |
| --- | --- |
| Shared pool across all repos (default) | Leave `DEVMEM_TENANT_ID` and `DEVMEM_SQLITE_PATH` unset. |
| Logical isolation, one database | Set a distinct `DEVMEM_TENANT_ID` per project (e.g. the repo slug). |
| Physical isolation, separate files | Set `DEVMEM_SQLITE_PATH=.devmem/devmem.db` per project. |

Set the variable in the MCP client `env` block (see `docs/mcp-clients.md`) so the
scope is applied to every tool call in that project.
