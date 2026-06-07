# Development

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Run Checks

```bash
pytest
ruff check .
basedpyright
python -m build --sdist --wheel
python scripts/audit_release.py --dist dist
```

## Fresh Install Smoke

```bash
python -m venv /tmp/devmem-smoke
/tmp/devmem-smoke/bin/python -m pip install dist/*.whl
DEVMEM_SQLITE_PATH=/tmp/devmem-smoke.db /tmp/devmem-smoke/bin/devmem status
DEVMEM_SQLITE_PATH=/tmp/devmem-smoke.db /tmp/devmem-smoke/bin/devmem preflight-mcp --quiet
```

Keep generated files such as `dist/`, `.tmp/`, virtual environments, caches, and
SQLite databases out of commits.
