from __future__ import annotations

from typing import Any

from devmem.domain.errors import OptionalFeatureError


def create_app() -> Any:
    try:
        from fastapi import FastAPI  # type: ignore[import-not-found]
    except ImportError as exc:
        raise OptionalFeatureError(
            "The API server requires installing the 'devmem-mcp[api]' extra."
        ) from exc

    from devmem.domain.config import DevMemConfig
    from devmem.infra.runtime import build_runtime

    app = FastAPI(title="DevMem")

    @app.get("/status")
    def status() -> dict[str, Any]:
        runtime = build_runtime(DevMemConfig())
        return {
            "store": runtime.store_type,
            "embedder": runtime.embedder_type,
            "path": runtime.store.path,
            "notes": runtime.store.count_notes(),
            "repo_slug": runtime.config.repo_slug,
        }

    return app
