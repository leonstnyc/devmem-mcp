from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from devmem.domain.config import DevMemConfig
from devmem.infra.openai_embedder import OpenAIEmbedder
from devmem.infra.runtime import build_runtime


def test_openai_runtime_passes_configured_timeout(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    fake_openai = ModuleType("openai")

    class FakeOpenAI:
        def __init__(self, *, api_key: str, timeout: float) -> None:
            captured["api_key"] = api_key
            captured["timeout"] = timeout

    fake_openai.__dict__["OpenAI"] = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    runtime = build_runtime(
        DevMemConfig(
            sqlite_path=str(tmp_path / "devmem.db"),
            repo_root=str(tmp_path),
            repo_slug="owner/project",
            openai_api_key="test-key",
            openai_timeout_seconds=3.5,
        )
    )

    assert runtime.embedder_type == "openai"
    assert isinstance(runtime.embedder, OpenAIEmbedder)
    assert runtime.embedder.model == "text-embedding-3-small"
    assert captured == {"api_key": "test-key", "timeout": 3.5}
