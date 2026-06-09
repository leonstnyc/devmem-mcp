# Contributing

## Local Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Quality Gates

Run these before opening a pull request:

```bash
pytest
ruff check .
ruff format --check .
basedpyright
python -m build --sdist --wheel --outdir .tmp/release-dist
python scripts/audit_release.py --dist .tmp/release-dist
```

Use a fresh output directory, or clear the old one, before rebuilding release
artifacts. The release audit fails on stale artifacts from other distribution
names.

Use `DEVMEM_SQLITE_PATH=.tmp/devmem.db` for local tests or manual smoke checks
when you do not want to write to `~/.devmem/devmem.db`.

## Scope

The base package must stay local-first and independent from any private
monorepo. Optional integrations belong behind extras and must have independent
install/import smoke tests.
