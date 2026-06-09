from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path

_GIT_REMOTE_TIMEOUT_SECONDS = 1.5
_DEFAULT_SQLITE_PATH = "~/.devmem/devmem.db"
_DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
_DEFAULT_OPENAI_TIMEOUT_SECONDS = 10.0


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip()


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


def _env_float(name: str, default: float, *, minimum: float = 0.1) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if isfinite(value) and value >= minimum else default


def _normalize_store(value: str) -> str:
    normalized = value.strip().lower()
    return normalized or "sqlite"


def _parse_remote_slug(remote_url: str) -> str | None:
    value = remote_url.strip()
    if not value:
        return None
    value = value.removesuffix(".git")
    ssh_match = re.match(r"^[^@]+@[^:]+:(?P<owner>[^/]+)/(?P<repo>[^/]+)$", value)
    if ssh_match:
        return f"{ssh_match.group('owner')}/{ssh_match.group('repo')}"
    https_match = re.match(r"^https?://[^/]+/(?P<owner>[^/]+)/(?P<repo>[^/]+)$", value)
    if https_match:
        return f"{https_match.group('owner')}/{https_match.group('repo')}"
    if "/" in value and "://" not in value:
        parts = [part for part in value.split("/") if part]
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
    return None


def derive_repo_slug(repo_root: str | None = None) -> str:
    explicit = os.environ.get("DEVMEM_REPO_SLUG")
    if explicit and explicit.strip():
        return explicit.strip()

    root = Path(repo_root or _env("DEVMEM_REPO_ROOT", os.getcwd())).expanduser()
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "config", "--get", "remote.origin.url"],
            capture_output=True,
            check=False,
            text=True,
            timeout=_GIT_REMOTE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None
    if result is not None and result.returncode == 0:
        slug = _parse_remote_slug(result.stdout)
        if slug:
            return slug

    folder_name = root.resolve().name if root.exists() else root.name
    return folder_name or "devmem"


def _default_sqlite_path() -> str:
    return str(Path(_env("DEVMEM_SQLITE_PATH", _DEFAULT_SQLITE_PATH)).expanduser())


@dataclass(frozen=True)
class DevMemConfig:
    sqlite_path: str = field(default_factory=_default_sqlite_path)
    repo_root: str = field(default_factory=lambda: str(Path(_env("DEVMEM_REPO_ROOT", os.getcwd()))))
    repo_slug: str = field(default_factory=derive_repo_slug)
    tenant_id: str = field(default_factory=lambda: _env("DEVMEM_TENANT_ID", "default") or "default")
    primary_store: str = field(
        default_factory=lambda: _normalize_store(_env("DEVMEM_PRIMARY_STORE", "sqlite"))
    )
    code_index_enabled: bool = field(
        default_factory=lambda: _env_bool("DEVMEM_CODE_INDEX_ENABLED", False)
    )
    code_max_symbol_bytes: int = field(
        default_factory=lambda: _env_int("DEVMEM_CODE_MAX_SYMBOL_BYTES", 8192)
    )
    embedding_model: str = field(
        default_factory=lambda: _env(
            "DEVMEM_EMBEDDING_MODEL",
            _DEFAULT_OPENAI_EMBEDDING_MODEL,
        )
    )
    embedding_dim: int = field(default_factory=lambda: _env_int("DEVMEM_EMBEDDING_DIM", 256))
    database_url: str = field(default_factory=lambda: _env("DEVMEM_DATABASE_URL", ""), repr=False)
    api_key: str = field(default_factory=lambda: _env("DEVMEM_API_KEY", ""), repr=False)
    host: str = field(default_factory=lambda: _env("DEVMEM_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("DEVMEM_PORT", 8765))
    force_local_embedder: bool = field(
        default_factory=lambda: _env_bool("DEVMEM_FORCE_LOCAL_EMBEDDER", False)
    )
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY", ""), repr=False)
    openai_timeout_seconds: float = field(
        default_factory=lambda: _env_float(
            "DEVMEM_OPENAI_TIMEOUT_SECONDS",
            _DEFAULT_OPENAI_TIMEOUT_SECONDS,
        )
    )
    postgres_connect_timeout_seconds: int = field(
        default_factory=lambda: _env_int("DEVMEM_POSTGRES_CONNECT_TIMEOUT_SECONDS", 5)
    )
    symbol_indexer_bin: str = field(default_factory=lambda: _env("DEVMEM_SYMBOL_INDEXER_BIN", ""))
    symbol_indexer_timeout_seconds: int = field(
        default_factory=lambda: _env_int("DEVMEM_SYMBOL_INDEXER_TIMEOUT_SECONDS", 5)
    )

    def normalized_tenant_id(self, override: str | None = None) -> str:
        value = override if override is not None else self.tenant_id
        normalized = value.strip()
        return normalized or "default"
