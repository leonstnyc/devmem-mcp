from __future__ import annotations

import secrets
from typing import Any

from devmem.domain.errors import OptionalFeatureError


def create_app() -> Any:
    try:
        from fastapi import (  # type: ignore[import-not-found]
            Depends,
            FastAPI,
            Header,
            HTTPException,
        )
    except ImportError as exc:
        raise OptionalFeatureError(
            "The API server requires the 'api' extra. Install with: "
            'pip install "devmem-mcp[api] @ git+https://github.com/leonstnyc/devmem-mcp.git"'
        ) from exc

    from devmem.domain.config import DevMemConfig
    from devmem.infra.runtime import build_runtime

    app = FastAPI(title="DevMem")
    config = DevMemConfig()

    def require_api_key(authorization: str | None = Header(default=None)) -> None:
        if not config.api_key:
            return
        expected = f"Bearer {config.api_key}"
        if authorization and secrets.compare_digest(authorization, expected):
            return
        raise HTTPException(status_code=401, detail="Unauthorized")

    @app.get("/status", dependencies=[Depends(require_api_key)])
    def status() -> dict[str, Any]:
        runtime = build_runtime(config)
        return {
            "store": runtime.store_type,
            "embedder": runtime.embedder_type,
            "path": runtime.store.path,
            "notes": runtime.store.count_notes(),
            "repo_slug": runtime.config.repo_slug,
        }

    return app
