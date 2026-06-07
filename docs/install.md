# Install

Source repository: <https://github.com/leonstnyc/devmem-mcp>

## User Install

```bash
pipx install "git+https://github.com/leonstnyc/devmem-mcp.git"
devmem status
```

## Project Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install "git+https://github.com/leonstnyc/devmem-mcp.git"
devmem preflight-mcp
```

## Development Install

```bash
pip install -e ".[dev]"
pytest
python -m build --sdist --wheel
```

The base package uses SQLite and local hash embeddings. OpenAI embeddings and
the optional API server require extras.

## Optional Extras

```bash
pip install "devmem-mcp[openai] @ git+https://github.com/leonstnyc/devmem-mcp.git"
pip install "devmem-mcp[api] @ git+https://github.com/leonstnyc/devmem-mcp.git"
```
