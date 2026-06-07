# Install

## User Install

```bash
pipx install devmem-mcp
devmem status
```

## Project Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install devmem-mcp
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
pip install "devmem-mcp[openai]"
pip install "devmem-mcp[api]"
```
