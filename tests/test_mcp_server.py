from __future__ import annotations

import pytest

from devmem.domain.config import DevMemConfig
from devmem.mcp_server import (
    _BASE_TOOLS,
    BASE_TOOL_NAMES,
    DevMemJSONRPCServer,
    LazyDevMemMCPContext,
)


@pytest.mark.asyncio
async def test_base_mcp_tool_surface_exact() -> None:
    names = tuple(tool.name for tool in _BASE_TOOLS)

    assert names == BASE_TOOL_NAMES
    assert set(names) == {
        "devmem_report",
        "devmem_lookup",
        "devmem_diagnose",
        "devmem_feedback",
        "devmem_search",
        "devmem_status",
    }
    assert not any(name.startswith("knowledge_") for name in names)


@pytest.mark.asyncio
async def test_tool_call_exception_returns_mcp_error_content(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(tmp_path / "devmem.db"))
    monkeypatch.setenv("DEVMEM_REPO_SLUG", "owner/project")
    server = DevMemJSONRPCServer(ctx=LazyDevMemMCPContext(DevMemConfig()))

    response = await server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "devmem_search",
                "arguments": {"query": "sqlite", "limit": "not-an-int"},
            },
        }
    )

    assert response is not None
    assert response["result"]["isError"] is True
    assert "ValueError" in response["result"]["content"][0]["text"]
