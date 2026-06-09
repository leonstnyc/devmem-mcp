# HTTP API

The HTTP API is optional. Install the API extra before starting it:

```bash
pip install "devmem-mcp[api] @ git+https://github.com/leonstnyc/devmem-mcp.git"
devmem api --host 127.0.0.1 --port 8765
```

The preview API exposes:

- `GET /status`

The API uses the same environment variables as the CLI. For example:

```bash
DEVMEM_SQLITE_PATH=.devmem/devmem.db devmem api
```

Set `DEVMEM_API_KEY` to require bearer-token authentication:

```bash
DEVMEM_API_KEY=local-secret devmem api
curl -H "Authorization: Bearer local-secret" http://127.0.0.1:8765/status
```

The base install does not include FastAPI or Uvicorn. If `devmem api` reports a
missing extra, install `devmem-mcp[api]`.
