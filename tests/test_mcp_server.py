from __future__ import annotations

import pytest

from devmem import __version__
from devmem.domain.config import DevMemConfig
from devmem.mcp_server import (
    _BASE_TOOLS,
    BASE_TOOL_NAMES,
    DevMemJSONRPCServer,
    LazyDevMemMCPContext,
)


def _server() -> DevMemJSONRPCServer:
    return DevMemJSONRPCServer(ctx=LazyDevMemMCPContext(DevMemConfig()))


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
async def test_initialize_reports_package_version_and_instructions(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(tmp_path / "devmem.db"))
    monkeypatch.setenv("DEVMEM_REPO_SLUG", "owner/project")

    response = await _server().handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )

    assert response is not None
    assert response["result"]["serverInfo"]["version"] == __version__
    assert "devmem_report" in response["result"]["instructions"]


@pytest.mark.asyncio
async def test_ping_returns_empty_result(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(tmp_path / "devmem.db"))

    response = await _server().handle_request({"jsonrpc": "2.0", "id": 7, "method": "ping"})

    assert response == {"jsonrpc": "2.0", "id": 7, "result": {}}


@pytest.mark.asyncio
async def test_notifications_and_id_less_requests_get_no_response(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(tmp_path / "devmem.db"))
    server = _server()

    cancelled = await server.handle_request(
        {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 3}}
    )
    initialized = await server.handle_request(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}
    )
    unknown_without_id = await server.handle_request({"jsonrpc": "2.0", "method": "bogus/method"})
    unknown_with_id = await server.handle_request(
        {"jsonrpc": "2.0", "id": 9, "method": "bogus/method"}
    )

    assert cancelled is None
    assert initialized is None
    assert unknown_without_id is None
    assert unknown_with_id is not None
    assert unknown_with_id["error"]["code"] == -32601


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


@pytest.mark.asyncio
async def test_report_rejects_null_text_as_tool_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(tmp_path / "devmem.db"))
    monkeypatch.setenv("DEVMEM_REPO_SLUG", "owner/project")
    server = DevMemJSONRPCServer(ctx=LazyDevMemMCPContext(DevMemConfig()))

    response = await server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "devmem_report",
                "arguments": {
                    "kind": "codebase_gotcha",
                    "text": None,
                    "summary_text": "Bad payload",
                },
            },
        }
    )

    assert response is not None
    assert response["result"]["isError"] is True
    assert "text must be a non-empty string" in response["result"]["content"][0]["text"]


@pytest.mark.asyncio
async def test_lookup_rejects_string_file_paths(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(tmp_path / "devmem.db"))
    monkeypatch.setenv("DEVMEM_REPO_SLUG", "owner/project")
    server = DevMemJSONRPCServer(ctx=LazyDevMemMCPContext(DevMemConfig()))

    response = await server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "devmem_lookup",
                "arguments": {"file_paths": "src/devmem/mcp_server.py"},
            },
        }
    )

    assert response is not None
    assert response["result"]["isError"] is True
    assert "file_paths must be an array of strings" in response["result"]["content"][0]["text"]


@pytest.mark.asyncio
async def test_runtime_unavailable_returns_tool_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(tmp_path / "devmem.db"))
    monkeypatch.setenv("DEVMEM_PRIMARY_STORE", "postgres")
    server = DevMemJSONRPCServer(ctx=LazyDevMemMCPContext(DevMemConfig()))

    response = await server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "devmem_status",
                "arguments": {},
            },
        }
    )

    assert response is not None
    assert response["result"]["isError"] is True
    assert "DevMem unavailable" in response["result"]["content"][0]["text"]
