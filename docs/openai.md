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

To force local embeddings even with an API key:

```bash
export DEVMEM_FORCE_LOCAL_EMBEDDER=true
```

OpenAI embeddings send note text and search text to OpenAI for embedding. The
base package does not send telemetry or sync memory data remotely.
