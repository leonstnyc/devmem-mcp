from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from devmem.app.services import DevMemFeedbackRecorder, DevMemReporter, DevMemRetriever
from devmem.domain.config import DevMemConfig
from devmem.domain.models import DevMemNoteKind, FeedbackRating, normalize_tenant_id
from devmem.domain.ports import DevMemStorePort, TextEmbedderPort

logger = logging.getLogger(__name__)

BASE_TOOL_NAMES = (
    "devmem_report",
    "devmem_lookup",
    "devmem_diagnose",
    "devmem_feedback",
    "devmem_search",
    "devmem_status",
)


@dataclass(frozen=True)
class TextContent:
    type: str
    text: str

    def to_json(self) -> dict[str, str]:
        return {"type": self.type, "text": self.text}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    inputSchema: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
        }


@dataclass
class DevMemMCPContext:
    reporter: DevMemReporter
    retriever: DevMemRetriever
    feedback_recorder: DevMemFeedbackRecorder
    store: DevMemStorePort
    embedder: TextEmbedderPort
    config: DevMemConfig
    store_type: str
    embedder_type: str


class LazyDevMemMCPContext:
    def __init__(self, config: DevMemConfig) -> None:
        self._config = config
        self._inner: DevMemMCPContext | None = None
        self._init_error: str | None = None
        self._lock = threading.Lock()

    def get(self) -> DevMemMCPContext:
        if self._inner is not None:
            return self._inner
        with self._lock:
            if self._inner is not None:
                return self._inner
            try:
                from devmem.infra.runtime import build_runtime

                runtime = build_runtime(self._config)
                reporter = DevMemReporter(
                    store=runtime.store,
                    embedder=runtime.embedder,
                    repo_slug=runtime.config.repo_slug,
                )
                retriever = DevMemRetriever(store=runtime.store, embedder=runtime.embedder)
                feedback = DevMemFeedbackRecorder(store=runtime.store)
                self._inner = DevMemMCPContext(
                    reporter=reporter,
                    retriever=retriever,
                    feedback_recorder=feedback,
                    store=runtime.store,
                    embedder=runtime.embedder,
                    config=runtime.config,
                    store_type=runtime.store_type,
                    embedder_type=runtime.embedder_type,
                )
                self._init_error = None
                return self._inner
            except Exception as exc:
                self._init_error = f"{type(exc).__name__}: {str(exc)[:200]}"
                logger.error("DevMem runtime init failed: %s", self._init_error)
                raise RuntimeError(self._init_error) from exc

    @property
    def last_error(self) -> str | None:
        return self._init_error


def _tenant(arguments: dict[str, Any], config: DevMemConfig) -> str:
    raw = arguments.get("tenant_id")
    if isinstance(raw, str):
        return normalize_tenant_id(raw)
    return normalize_tenant_id(os.environ.get("DEVMEM_TENANT_ID") or config.tenant_id)


def _tool(
    *,
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> Tool:
    return Tool(
        name=name,
        description=description,
        inputSchema={
            "type": "object",
            "properties": properties,
            "required": required or [],
        },
    )


_BASE_TOOLS = (
    _tool(
        name="devmem_report",
        description="Record a developer-memory note.",
        properties={
            "kind": {
                "type": "string",
                "enum": [kind.value for kind in DevMemNoteKind],
            },
            "text": {"type": "string"},
            "summary_text": {"type": "string"},
            "file_paths": {"type": "array", "items": {"type": "string"}},
            "module": {"type": "string"},
            "error_pattern": {"type": "string"},
            "error_type": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "tenant_id": {"type": "string"},
        },
        required=["kind", "text", "summary_text"],
    ),
    _tool(
        name="devmem_lookup",
        description="Look up developer memories related to specific files.",
        properties={
            "file_paths": {"type": "array", "items": {"type": "string"}},
            "include_kinds": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer", "minimum": 1},
            "tenant_id": {"type": "string"},
        },
        required=["file_paths"],
    ),
    _tool(
        name="devmem_diagnose",
        description="Search error-solution memories for a failure.",
        properties={
            "error_message": {"type": "string"},
            "error_type": {"type": "string"},
            "file_path": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1},
            "tenant_id": {"type": "string"},
        },
        required=["error_message"],
    ),
    _tool(
        name="devmem_feedback",
        description="Rate a memory as helpful, outdated, or wrong.",
        properties={
            "memory_id": {"type": "string"},
            "rating": {"type": "string", "enum": [rating.value for rating in FeedbackRating]},
            "tenant_id": {"type": "string"},
        },
        required=["memory_id", "rating"],
    ),
    _tool(
        name="devmem_search",
        description="Semantic search across developer memories.",
        properties={
            "query": {"type": "string"},
            "kinds": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer", "minimum": 1},
            "tenant_id": {"type": "string"},
        },
        required=["query"],
    ),
    _tool(
        name="devmem_status",
        description="Report store, embedder, database path, and note count.",
        properties={},
    ),
)


async def _resolve(
    ctx: LazyDevMemMCPContext | DevMemMCPContext,
) -> tuple[DevMemMCPContext | None, Sequence[TextContent] | None]:
    if isinstance(ctx, DevMemMCPContext):
        return ctx, None
    try:
        return await asyncio.to_thread(ctx.get), None
    except Exception as exc:
        return None, [
            TextContent(
                type="text",
                text=f"DevMem unavailable: {type(exc).__name__}: {str(exc)[:200]}",
            )
        ]


async def _handle_report(
    ctx: LazyDevMemMCPContext | DevMemMCPContext,
    arguments: dict[str, Any],
) -> Sequence[TextContent]:
    resolved, error = await _resolve(ctx)
    if resolved is None:
        return error or []
    try:
        result = await asyncio.to_thread(
            resolved.reporter.report,
            kind=DevMemNoteKind(str(arguments["kind"])),
            text=str(arguments["text"]),
            summary_text=str(arguments["summary_text"]),
            tenant_id=_tenant(arguments, resolved.config),
            file_paths=tuple(str(path) for path in arguments.get("file_paths", []) or []),
            module=arguments.get("module"),
            error_pattern=arguments.get("error_pattern"),
            error_type=arguments.get("error_type"),
            tags=tuple(str(tag) for tag in arguments.get("tags", []) or []),
        )
        suffix = f" ({result.warning})" if result.warning else ""
        return [TextContent(type="text", text=f"Recorded {result.memory_id}{suffix}")]
    except Exception as exc:
        return [
            TextContent(
                type="text",
                text=f"Error recording memory: {type(exc).__name__}: {str(exc)[:200]}",
            )
        ]


async def _handle_lookup(
    ctx: LazyDevMemMCPContext | DevMemMCPContext,
    arguments: dict[str, Any],
) -> Sequence[TextContent]:
    resolved, error = await _resolve(ctx)
    if resolved is None:
        return error or []
    result = await asyncio.to_thread(
        resolved.retriever.lookup,
        tenant_id=_tenant(arguments, resolved.config),
        file_paths=tuple(str(path) for path in arguments.get("file_paths", []) or []),
        include_kinds=arguments.get("include_kinds"),
        limit=int(arguments.get("limit", 5)),
    )
    return [TextContent(type="text", text=result.text)]


async def _handle_diagnose(
    ctx: LazyDevMemMCPContext | DevMemMCPContext,
    arguments: dict[str, Any],
) -> Sequence[TextContent]:
    resolved, error = await _resolve(ctx)
    if resolved is None:
        return error or []
    result = await asyncio.to_thread(
        resolved.retriever.diagnose,
        tenant_id=_tenant(arguments, resolved.config),
        error_message=str(arguments["error_message"]),
        error_type=arguments.get("error_type"),
        file_path=arguments.get("file_path"),
        limit=int(arguments.get("limit", 5)),
    )
    return [TextContent(type="text", text=result.text)]


async def _handle_feedback(
    ctx: LazyDevMemMCPContext | DevMemMCPContext,
    arguments: dict[str, Any],
) -> Sequence[TextContent]:
    resolved, error = await _resolve(ctx)
    if resolved is None:
        return error or []
    score = await asyncio.to_thread(
        resolved.feedback_recorder.record,
        tenant_id=_tenant(arguments, resolved.config),
        note_id=str(arguments["memory_id"]),
        rating=FeedbackRating(str(arguments["rating"])),
    )
    return [TextContent(type="text", text=f"Recorded feedback score {score:.1f}")]


async def _handle_search(
    ctx: LazyDevMemMCPContext | DevMemMCPContext,
    arguments: dict[str, Any],
) -> Sequence[TextContent]:
    resolved, error = await _resolve(ctx)
    if resolved is None:
        return error or []
    result = await asyncio.to_thread(
        resolved.retriever.search,
        tenant_id=_tenant(arguments, resolved.config),
        query=str(arguments["query"]),
        kinds=arguments.get("kinds"),
        limit=int(arguments.get("limit", 5)),
    )
    return [TextContent(type="text", text=result.text)]


async def _handle_status(
    ctx: LazyDevMemMCPContext | DevMemMCPContext,
    arguments: dict[str, Any],
) -> Sequence[TextContent]:
    del arguments
    resolved, error = await _resolve(ctx)
    if resolved is None:
        return error or []
    note_count = await asyncio.to_thread(resolved.store.count_notes)
    text = "\n".join(
        (
            f"store: {resolved.store_type}",
            f"embedder: {resolved.embedder_type}",
            f"path: {resolved.store.path}",
            f"notes: {note_count}",
            f"repo_slug: {resolved.config.repo_slug}",
        )
    )
    return [TextContent(type="text", text=text)]


_HANDLERS = {
    "devmem_report": _handle_report,
    "devmem_lookup": _handle_lookup,
    "devmem_diagnose": _handle_diagnose,
    "devmem_feedback": _handle_feedback,
    "devmem_search": _handle_search,
    "devmem_status": _handle_status,
}


@dataclass
class DevMemJSONRPCServer:
    ctx: LazyDevMemMCPContext | DevMemMCPContext

    async def handle_request(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        method = payload.get("method")
        request_id = payload.get("id")
        if method == "notifications/initialized":
            return None
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "devmem", "version": "0.1.0"},
                },
            }
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": [tool.to_json() for tool in _BASE_TOOLS]},
            }
        if method == "tools/call":
            return await self._handle_tool_call(payload)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        }

    async def _handle_tool_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = payload.get("id")
        params = payload.get("params")
        if not isinstance(params, dict):
            return self._error(request_id, -32602, "tools/call params must be an object")
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return self._error(request_id, -32602, "tools/call requires name and arguments")
        handler = _HANDLERS.get(name)
        if handler is None:
            return self._error(request_id, -32601, f"Unknown tool: {name}")
        is_error = False
        try:
            content = await handler(self.ctx, arguments)
        except Exception as exc:
            is_error = True
            content = [
                TextContent(
                    type="text",
                    text=f"Error calling {name}: {type(exc).__name__}: {str(exc)[:200]}",
                )
            ]
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [item.to_json() for item in content],
                "isError": is_error,
            },
        }

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def create_mcp_server(
    ctx: LazyDevMemMCPContext | DevMemMCPContext,
) -> DevMemJSONRPCServer:
    return DevMemJSONRPCServer(ctx=ctx)


def _write_response(response: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _serve_stdio(server: DevMemJSONRPCServer) -> None:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                _write_response(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": f"Invalid JSON: {exc.msg}"},
                    }
                )
                continue
            if not isinstance(payload, dict):
                _write_response(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32600, "message": "JSON-RPC payload must be an object"},
                    }
                )
                continue
            response = loop.run_until_complete(server.handle_request(payload))
            if response is not None:
                _write_response(response)
    finally:
        loop.close()


async def main() -> None:
    server = create_mcp_server(LazyDevMemMCPContext(DevMemConfig()))
    await asyncio.to_thread(_serve_stdio, server)
