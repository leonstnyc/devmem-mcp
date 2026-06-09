# OpenAI Embeddings

DevMem works without API keys by using local hash embeddings. To use OpenAI
embeddings instead:

```bash
pip install "devmem-mcp[openai] @ git+https://github.com/leonstnyc/devmem-mcp.git"
export OPENAI_API_KEY="..."
devmem status
```

`devmem status` should show `embedder: openai` when the key is present and
`DEVMEM_FORCE_LOCAL_EMBEDDER` is not enabled.

OpenAI embedding requests use `text-embedding-3-small` and a 10-second timeout
by default. Override them with:

```bash
export DEVMEM_EMBEDDING_MODEL=text-embedding-3-large
export DEVMEM_OPENAI_TIMEOUT_SECONDS=5
```

To force local embeddings even with an API key:

```bash
export DEVMEM_FORCE_LOCAL_EMBEDDER=true
```

OpenAI embeddings send note text and search text to OpenAI for embedding. The
base package does not send telemetry or sync memory data remotely.

## Switching Embedders

Embeddings from the local hash embedder and OpenAI models have different
dimensions. Notes embedded before a switch score zero in semantic search until
they are re-embedded; keyword fallback search still finds them. To keep one
consistent embedder, set `DEVMEM_FORCE_LOCAL_EMBEDDER=true` or keep
`OPENAI_API_KEY` set in every environment that writes notes.
