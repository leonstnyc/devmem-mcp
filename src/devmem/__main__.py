from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import select
import shlex
import signal
import subprocess
import sys
import time
import weakref
from collections.abc import Callable
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import IO, Any

from devmem.app.services import DevMemFeedbackRecorder, DevMemReporter, DevMemRetriever
from devmem.domain.config import DevMemConfig
from devmem.domain.errors import OptionalFeatureError
from devmem.domain.models import DevMemNoteKind, FeedbackRating
from devmem.infra.runtime import build_runtime

_STREAM_READ_BUFFERS: weakref.WeakKeyDictionary[object, bytes] = weakref.WeakKeyDictionary()
_CLEANUP_PS_TIMEOUT_SECONDS = 5.0


def _positive_float(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"must be a finite number > 0, got {raw!r}") from exc
    if not isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError(f"must be a finite number > 0, got {raw!r}")
    return value


def _positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"must be an integer > 0, got {raw!r}") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be an integer > 0, got {raw!r}")
    return value


def _runtime_services() -> tuple[
    DevMemConfig,
    Any,
    DevMemReporter,
    DevMemRetriever,
    DevMemFeedbackRecorder,
]:
    config = DevMemConfig()
    runtime = build_runtime(config)
    return (
        config,
        runtime,
        DevMemReporter(
            store=runtime.store,
            embedder=runtime.embedder,
            repo_slug=runtime.config.repo_slug,
        ),
        DevMemRetriever(store=runtime.store, embedder=runtime.embedder),
        DevMemFeedbackRecorder(store=runtime.store),
    )


def _run_mcp(_: argparse.Namespace) -> int:
    from devmem.mcp_server import main as mcp_main

    asyncio.run(mcp_main())
    return 0


def _run_status(_: argparse.Namespace) -> int:
    config = DevMemConfig()
    runtime = build_runtime(config)
    lines = (
        f"store: {runtime.store_type}",
        f"embedder: {runtime.embedder_type}",
        f"path: {runtime.store.path}",
        f"notes: {runtime.store.count_notes()}",
        f"repo_slug: {runtime.config.repo_slug}",
    )
    print("\n".join(lines))
    return 0


def _run_report(args: argparse.Namespace) -> int:
    config, _runtime, reporter, _retriever, _feedback = _runtime_services()
    result = reporter.report(
        kind=DevMemNoteKind(args.kind),
        text=args.text,
        summary_text=args.summary_text,
        tenant_id=args.tenant_id or config.tenant_id,
        file_paths=tuple(args.file_path or ()),
        module=args.module,
        error_pattern=args.error_pattern,
        error_type=args.error_type,
        tags=tuple(args.tag or ()),
    )
    payload = {"memory_id": result.memory_id, "note_kind": result.note_kind.value}
    if result.warning:
        payload["warning"] = result.warning
    print(json.dumps(payload, sort_keys=True))
    return 0


def _run_search(args: argparse.Namespace) -> int:
    config, _runtime, _reporter, retriever, _feedback = _runtime_services()
    result = retriever.search(
        tenant_id=args.tenant_id or config.tenant_id,
        query=args.query,
        kinds=tuple(args.kind or ()),
        limit=args.limit,
    )
    print(result.text)
    return 0


def _run_diagnose(args: argparse.Namespace) -> int:
    config, _runtime, _reporter, retriever, _feedback = _runtime_services()
    result = retriever.diagnose(
        tenant_id=args.tenant_id or config.tenant_id,
        error_message=args.error_message,
        error_type=args.error_type,
        file_path=args.file_path,
        limit=args.limit,
    )
    print(result.text)
    return 0


def _run_feedback(args: argparse.Namespace) -> int:
    config, _runtime, _reporter, _retriever, feedback = _runtime_services()
    score = feedback.record(
        tenant_id=args.tenant_id or config.tenant_id,
        note_id=args.memory_id,
        rating=FeedbackRating(args.rating),
    )
    print(json.dumps({"memory_id": args.memory_id, "rating": args.rating, "score": score}))
    return 0


def _read_line_timeout(stream: IO[bytes], timeout: float) -> str | None:
    fd = stream.fileno()
    deadline = time.monotonic() + timeout
    buf = _STREAM_READ_BUFFERS.pop(stream, b"")
    while True:
        if b"\n" in buf:
            line, remainder = buf.split(b"\n", 1)
            if remainder:
                _STREAM_READ_BUFFERS[stream] = remainder
            return line.decode("utf-8", errors="replace").strip()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if buf:
                _STREAM_READ_BUFFERS[stream] = buf
            return None
        ready, _, _ = select.select([fd], [], [], min(remaining, 0.5))
        if not ready:
            continue
        chunk = os.read(fd, 4096)
        if not chunk:
            _STREAM_READ_BUFFERS.pop(stream, None)
            return None
        buf += chunk


def _load_env_file(env_file: Path) -> dict[str, str]:
    child_env = os.environ.copy()
    if not env_file.is_file():
        return child_env
    try:
        from dotenv import dotenv_values
    except ImportError:
        return child_env
    for key, value in dotenv_values(str(env_file)).items():
        if key and value is not None:
            child_env[key] = value
    return child_env


def _parse_json_rpc_response(raw_line: str, response_name: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{response_name} returned invalid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{response_name} returned {type(payload).__name__}, expected object")
    return payload


def _extract_tool_names(tools_response: dict[str, Any]) -> list[str]:
    result = tools_response.get("result")
    if not isinstance(result, dict):
        raise ValueError("tools/list response missing object result")
    tools = result.get("tools", [])
    if not isinstance(tools, list):
        raise ValueError("tools/list response tools was not a list")
    names: list[str] = []
    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            raise ValueError(f"tools/list response tool #{index} was not an object")
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"tools/list response tool #{index} missing string name")
        names.append(name)
    return names


def _release_contract_path() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "release-contract.json"


def _expected_tools() -> set[str]:
    contract_path = _release_contract_path()
    if contract_path.exists():
        payload = json.loads(contract_path.read_text())
        tools = payload.get("required_base_mcp_tools", [])
        if isinstance(tools, list) and all(isinstance(tool, str) for tool in tools):
            return set(tools)
    from devmem.mcp_server import BASE_TOOL_NAMES

    return set(BASE_TOOL_NAMES)


def _run_preflight_mcp(args: argparse.Namespace) -> int:
    timeout: float = args.timeout
    quiet: bool = args.quiet
    no_cleanup: bool = args.no_cleanup
    repo_root = Path(args.repo_root or os.getcwd()).resolve()

    init_msg = (
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "devmem-preflight", "version": "1.0"},
                },
            }
        )
        + "\n"
    )
    initialized = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
    list_tools = (
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n"
    )
    cmd = [sys.executable, "-m", "devmem", "mcp"]
    expected_tools = _expected_tools()

    start = time.monotonic()
    failure_reason: str | None = None
    received_tools: list[str] = []
    proc: subprocess.Popen[bytes] | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_load_env_file(repo_root / ".env"),
            start_new_session=True,
        )
    except (OSError, ValueError) as exc:
        failure_reason = f"Failed to spawn MCP server: {type(exc).__name__}: {str(exc)[:200]}"

    if proc is not None:
        try:
            if proc.stdin is None or proc.stdout is None:
                failure_reason = "Failed to open subprocess stdio pipes"
            else:
                proc.stdin.write(init_msg.encode())
                proc.stdin.flush()
                init_line = _read_line_timeout(proc.stdout, timeout=min(timeout * 0.7, 3.5))
                if init_line is None:
                    failure_reason = "Timeout waiting for initialize response"
                else:
                    init_response = _parse_json_rpc_response(init_line, "initialize")
                    if "error" in init_response:
                        failure_reason = f"Initialize error: {init_response['error']}"
                    elif init_response.get("id") != 1:
                        failure_reason = f"Unexpected response id: {init_response.get('id')}"
                    else:
                        proc.stdin.write(initialized.encode())
                        proc.stdin.write(list_tools.encode())
                        proc.stdin.flush()
                        proc.stdin.close()
                        tools_line = _read_line_timeout(
                            proc.stdout,
                            timeout=min(timeout * 0.3, 2.0),
                        )
                        if tools_line is None:
                            failure_reason = "Timeout waiting for tools/list response"
                        else:
                            tools_response = _parse_json_rpc_response(tools_line, "tools/list")
                            if "error" in tools_response:
                                failure_reason = f"tools/list error: {tools_response['error']}"
                            else:
                                received_tools = _extract_tool_names(tools_response)
                                if set(received_tools) != expected_tools:
                                    failure_reason = (
                                        "Tool surface mismatch: "
                                        f"expected {sorted(expected_tools)}, "
                                        f"got {sorted(received_tools)}"
                                    )
        except (BrokenPipeError, OSError, ValueError) as exc:
            failure_reason = f"{type(exc).__name__}: {str(exc)[:200]}"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    if failure_reason is None:
        if not quiet:
            print(f"DevMem preflight: PASS ({len(received_tools)} tools in {elapsed_ms}ms)")
        return 0

    stderr_text = ""
    if proc is not None and proc.stderr is not None:
        try:
            stderr_text = proc.stderr.read(500).decode("utf-8", errors="replace")
        except OSError:
            stderr_text = ""
    print(f"DevMem preflight: FAIL - {failure_reason}", file=sys.stderr)
    print(f"  elapsed: {elapsed_ms}ms", file=sys.stderr)
    if stderr_text.strip():
        print(f"  server stderr: {stderr_text.strip()[:300]}", file=sys.stderr)
    if not no_cleanup:
        cleanup_args = argparse.Namespace(max_age=4.0, all=True, dry_run=False)
        _run_cleanup_mcp(cleanup_args)
    return 1


def _run_cleanup_mcp(args: argparse.Namespace) -> int:
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid,lstart,command"],
            capture_output=True,
            check=False,
            text=True,
            timeout=_CLEANUP_PS_TIMEOUT_SECONDS,
        )
        result.check_returncode()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"DevMem cleanup: FAIL - {type(exc).__name__}: {str(exc)[:200]}", file=sys.stderr)
        return 1

    candidates: list[tuple[int, float]] = []
    our_pid = os.getpid()
    our_ppid = os.getppid()
    now = time.time()
    for line in result.stdout.splitlines()[1:]:
        parts = line.split(maxsplit=6)
        if len(parts) < 7:
            continue
        if not _is_devmem_mcp_command(parts[6]):
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        if pid in {our_pid, our_ppid}:
            continue
        lstart = " ".join(parts[1:6])
        try:
            started_at = datetime.strptime(lstart, "%a %b %d %H:%M:%S %Y")
            elapsed = now - started_at.timestamp()
        except ValueError:
            elapsed = 0.0
        candidates.append((pid, elapsed))

    if not candidates:
        print("No MCP server processes found.")
        return 0

    killed = 0
    eligible = {
        pid
        for pid, elapsed in candidates
        if args.all or elapsed > args.max_age * 3600
    }
    for pid in sorted(eligible):
        if args.dry_run:
            print(f"would kill PID {pid}")
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            killed += 1
        except ProcessLookupError:
            pass
    action = "would kill" if args.dry_run else "killed"
    total = len(eligible) if args.dry_run else killed
    print(f"MCP cleanup: {action} {total}/{len(set(candidates))}")
    return 0


def _is_devmem_mcp_command(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    for index, part in enumerate(parts):
        name = Path(part).name
        if name == "devmem" and index + 1 < len(parts) and parts[index + 1] == "mcp":
            return True
        if (
            name.startswith("python")
            and index + 3 < len(parts)
            and parts[index + 1] == "-m"
            and parts[index + 2] == "devmem"
            and parts[index + 3] == "mcp"
        ):
            return True
    return False


def _run_embed_pending(_: argparse.Namespace) -> int:
    runtime = build_runtime(DevMemConfig())
    pending = runtime.store.get_pending_notes(limit=100)
    embedded = 0
    for note in pending:
        note_id = note.get("note_id")
        summary_text = note.get("summary_text")
        text = note.get("text")
        if (
            not isinstance(note_id, str)
            or not isinstance(summary_text, str)
            or not isinstance(text, str)
        ):
            continue
        embedding_text = f"{summary_text}\n\n{text}".strip()
        runtime.store.complete_pending_note(
            note_id=note_id,
            embedding=runtime.embedder.embed(embedding_text),
        )
        embedded += 1
    print(f"Embedded {embedded}/{len(pending)} pending notes.")
    return 0


def _run_api(args: argparse.Namespace) -> int:
    config = DevMemConfig()
    host = args.host or config.host
    port = args.port if args.port is not None else config.port
    try:
        uvicorn = importlib.import_module("uvicorn")
    except ImportError as exc:
        raise OptionalFeatureError(
            "The API server requires the 'api' extra. Install with: "
            'pip install "devmem-mcp[api] @ git+https://github.com/leonstnyc/devmem-mcp.git"'
        ) from exc
    uvicorn.run(
        "devmem.api_server:create_app",
        factory=True,
        host=host,
        port=port,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devmem")
    subparsers = parser.add_subparsers(dest="command", required=True)

    mcp = subparsers.add_parser("mcp", help="run the stdio MCP server")
    mcp.set_defaults(func=_run_mcp)

    status = subparsers.add_parser("status", help="show store, embedder, path, and note count")
    status.set_defaults(func=_run_status)

    report = subparsers.add_parser("report", help="record a developer-memory note")
    report.add_argument("--kind", choices=[kind.value for kind in DevMemNoteKind], required=True)
    report.add_argument("--text", required=True)
    report.add_argument("--summary-text", required=True)
    report.add_argument("--file-path", action="append")
    report.add_argument("--module")
    report.add_argument("--error-pattern")
    report.add_argument("--error-type")
    report.add_argument("--tag", action="append")
    report.add_argument("--tenant-id")
    report.set_defaults(func=_run_report)

    search = subparsers.add_parser("search", help="search stored developer memories")
    search.add_argument("query")
    search.add_argument("--kind", action="append", choices=[kind.value for kind in DevMemNoteKind])
    search.add_argument("--limit", type=_positive_int, default=5)
    search.add_argument("--tenant-id")
    search.set_defaults(func=_run_search)

    diagnose = subparsers.add_parser("diagnose", help="find error-solution memories")
    diagnose.add_argument("error_message")
    diagnose.add_argument("--error-type")
    diagnose.add_argument("--file-path")
    diagnose.add_argument("--limit", type=_positive_int, default=5)
    diagnose.add_argument("--tenant-id")
    diagnose.set_defaults(func=_run_diagnose)

    feedback = subparsers.add_parser("feedback", help="rate a memory")
    feedback.add_argument("memory_id")
    feedback.add_argument("rating", choices=[rating.value for rating in FeedbackRating])
    feedback.add_argument("--tenant-id")
    feedback.set_defaults(func=_run_feedback)

    preflight = subparsers.add_parser("preflight-mcp", help="validate MCP startup and tools")
    preflight.add_argument("--timeout", type=_positive_float, default=5.0)
    preflight.add_argument("--quiet", action="store_true")
    preflight.add_argument("--no-cleanup", action="store_true")
    preflight.add_argument("--repo-root")
    preflight.set_defaults(func=_run_preflight_mcp)

    cleanup = subparsers.add_parser("cleanup-mcp", help="terminate stale MCP server processes")
    cleanup.add_argument("--max-age", type=_positive_float, default=4.0)
    cleanup.add_argument("--all", action="store_true")
    cleanup.add_argument("--dry-run", action="store_true")
    cleanup.set_defaults(func=_run_cleanup_mcp)

    embed_pending = subparsers.add_parser("embed-pending", help="retry pending note embeddings")
    embed_pending.set_defaults(func=_run_embed_pending)

    api = subparsers.add_parser("api", help="run the optional HTTP API server")
    api.add_argument("--host")
    api.add_argument("--port", type=_positive_int)
    api.set_defaults(func=_run_api)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func: Callable[[argparse.Namespace], int] = args.func
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
