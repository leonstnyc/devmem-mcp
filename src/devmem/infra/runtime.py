from __future__ import annotations

from dataclasses import dataclass

from devmem.domain.config import DevMemConfig
from devmem.domain.errors import OptionalFeatureError
from devmem.domain.ports import DevMemStorePort, TextEmbedderPort
from devmem.infra.local_embedder import LocalHashEmbedder
from devmem.infra.sqlite_store import SqliteDevMemStore


@dataclass(frozen=True)
class DevMemRuntime:
    config: DevMemConfig
    store: DevMemStorePort
    embedder: TextEmbedderPort
    store_type: str
    embedder_type: str


def _build_embedder(config: DevMemConfig) -> tuple[TextEmbedderPort, str]:
    if config.openai_api_key and not config.force_local_embedder:
        from devmem.infra.openai_embedder import OpenAIEmbedder

        return OpenAIEmbedder(api_key=config.openai_api_key, model=config.embedding_model), "openai"
    return LocalHashEmbedder(dimension=max(32, config.embedding_dim)), "local-hash"


def build_runtime(config: DevMemConfig | None = None) -> DevMemRuntime:
    cfg = config or DevMemConfig()
    if cfg.primary_store != "sqlite":
        raise OptionalFeatureError(
            f"Store {cfg.primary_store!r} is not available in the preview base package."
        )
    embedder, embedder_type = _build_embedder(cfg)
    return DevMemRuntime(
        config=cfg,
        store=SqliteDevMemStore(path=cfg.sqlite_path),
        embedder=embedder,
        store_type="sqlite",
        embedder_type=embedder_type,
    )
