# HTTP API

The HTTP API is optional. Install the API extra before starting it:

```bash
pip install "devmem-mcp[api]"
devmem api --host 127.0.0.1 --port 8765
```

The preview API exposes:

- `GET /status`

The API uses the same environment variables as the CLI. For example:

```bash
DEVMEM_SQLITE_PATH=.devmem/devmem.db devmem api
```

The base install does not include FastAPI or Uvicorn. If `devmem api` reports a
missing extra, install `devmem-mcp[api]`.
