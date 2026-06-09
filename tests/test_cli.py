from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from devmem.__main__ import build_parser, main
from devmem.domain.errors import OptionalFeatureError


def test_help_lists_required_commands_only() -> None:
    parser = build_parser()
    choices: dict[str, Any] = {}
    for action in parser._actions:
        action_choices = getattr(action, "choices", None)
        if isinstance(action_choices, dict) and "mcp" in action_choices:
            choices = action_choices
            break
    commands = set(choices)

    assert commands == {
        "mcp",
        "status",
        "report",
        "search",
        "diagnose",
        "feedback",
        "preflight-mcp",
        "cleanup-mcp",
        "embed-pending",
        "api",
    }


def test_cli_report_search_diagnose_feedback_status(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(tmp_path / "devmem.db"))
    monkeypatch.setenv("DEVMEM_REPO_SLUG", "owner/project")

    assert main(
        [
            "report",
            "--kind",
            "error_solution",
            "--summary-text",
            "Migration fix",
            "--text",
            "Run the migration before querying.",
            "--error-pattern",
            "missing table",
            "--file-path",
            "src/db.py",
        ]
    ) == 0
    report_payload = json.loads(capsys.readouterr().out)
    assert report_payload["memory_id"].startswith("devmem:")

    assert main(["search", "migration", "--limit", "3"]) == 0
    assert "Migration fix" in capsys.readouterr().out

    assert main(["diagnose", "missing table"]) == 0
    assert "Migration fix" in capsys.readouterr().out

    assert main(["feedback", report_payload["memory_id"], "helpful"]) == 0
    feedback_payload = json.loads(capsys.readouterr().out)
    assert feedback_payload["score"] == 1.0

    assert main(["status"]) == 0
    status = capsys.readouterr().out
    assert "store: sqlite" in status
    assert "embedder: local-hash" in status
    assert "repo_slug: owner/project" in status


def test_preflight_mcp_runs_against_source_tree(monkeypatch, tmp_path: Path) -> None:
    src_path = Path(__file__).resolve().parents[1] / "src"
    env_pythonpath = os.pathsep.join(
        part for part in (str(src_path), os.environ.get("PYTHONPATH", "")) if part
    )
    monkeypatch.setenv("PYTHONPATH", env_pythonpath)
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(tmp_path / "devmem.db"))
    monkeypatch.setenv("DEVMEM_REPO_SLUG", "owner/project")

    assert main(["preflight-mcp", "--quiet", "--no-cleanup", "--timeout", "8"]) == 0


def test_module_entrypoint_help_works() -> None:
    src_path = Path(__file__).resolve().parents[1] / "src"
    result = subprocess.run(
        [sys.executable, "-m", "devmem", "--help"],
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(src_path)},
        text=True,
    )

    assert result.returncode == 0
    assert "preflight-mcp" in result.stdout


def test_invalid_store_mode_has_specific_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(tmp_path / "devmem.db"))
    monkeypatch.setenv("DEVMEM_PRIMARY_STORE", "postgres")

    with pytest.raises(Exception, match="preview base package"):
        main(["status"])


def test_cleanup_mcp_honors_age_gate(monkeypatch, capsys) -> None:
    import devmem.__main__ as main_module

    ps_output = (
        "  PID STARTED COMMAND\n"
        "12345 Mon Jan  1 00:00:00 2001 /usr/bin/python -m devmem mcp\n"
    )

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        return subprocess.CompletedProcess(
            args=["ps"],
            returncode=0,
            stdout=ps_output,
            stderr="",
        )

    monkeypatch.setattr(main_module.subprocess, "run", fake_run)

    assert main(["cleanup-mcp", "--max-age", "999999999", "--dry-run"]) == 0
    assert "would kill 0/1" in capsys.readouterr().out

    assert main(["cleanup-mcp", "--all", "--dry-run"]) == 0
    assert "would kill PID 12345" in capsys.readouterr().out


def test_cleanup_mcp_ignores_incidental_text_matches(monkeypatch, capsys) -> None:
    import devmem.__main__ as main_module

    ps_output = (
        "  PID STARTED COMMAND\n"
        "12345 Mon Jan  1 00:00:00 2001 /usr/bin/python -m devmem mcp\n"
        "23456 Mon Jan  1 00:00:00 2001 /usr/bin/python note.py --text 'devmem mcp'\n"
        "34567 Mon Jan  1 00:00:00 2001 /tmp/devmem mcp\n"
        "45678 Mon Jan  1 00:00:00 2001 /usr/bin/devmemory mcp\n"
    )

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        return subprocess.CompletedProcess(
            args=["ps"],
            returncode=0,
            stdout=ps_output,
            stderr="",
        )

    monkeypatch.setattr(main_module.subprocess, "run", fake_run)

    assert main(["cleanup-mcp", "--all", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "would kill PID 12345" in output
    assert "would kill PID 34567" in output
    assert "23456" not in output
    assert "45678" not in output


def test_api_command_uses_optional_uvicorn_launcher(monkeypatch) -> None:
    import devmem.__main__ as main_module

    calls: list[tuple[str, dict[str, Any]]] = []

    class FakeUvicorn:
        @staticmethod
        def run(app: str, **kwargs: Any) -> None:
            calls.append((app, kwargs))

    def fake_import_module(name: str) -> object:
        if name == "uvicorn":
            return FakeUvicorn
        raise AssertionError(f"unexpected import {name}")

    monkeypatch.setattr(main_module.importlib, "import_module", fake_import_module)

    assert main(["api", "--host", "0.0.0.0", "--port", "9999"]) == 0
    assert calls == [
        (
            "devmem.api_server:create_app",
            {"factory": True, "host": "0.0.0.0", "port": 9999},
        )
    ]


def test_api_command_missing_extra_has_distribution_install_hint(monkeypatch) -> None:
    import devmem.__main__ as main_module

    def fake_import_module(name: str) -> object:
        if name == "uvicorn":
            raise ImportError("missing uvicorn")
        raise AssertionError(f"unexpected import {name}")

    monkeypatch.setattr(main_module.importlib, "import_module", fake_import_module)

    with pytest.raises(OptionalFeatureError, match=r"devmem-mcp\[api\]"):
        main(["api"])


def test_embed_pending_uses_summary_and_text(monkeypatch, capsys) -> None:
    import devmem.__main__ as main_module

    embedded_texts: list[str] = []
    completed: list[tuple[str, list[float]]] = []

    class FakeEmbedder:
        @staticmethod
        def embed(text: str) -> list[float]:
            embedded_texts.append(text)
            return [1.0, 0.0]

    class FakeStore:
        path = "unused"

        @staticmethod
        def get_pending_notes(*, limit: int = 100) -> list[dict[str, str]]:
            assert limit == 100
            return [
                {
                    "note_id": "devmem:pending",
                    "summary_text": "Summary matters",
                    "text": "Body matters too",
                }
            ]

        @staticmethod
        def complete_pending_note(*, note_id: str, embedding: list[float]) -> None:
            completed.append((note_id, embedding))

    class FakeRuntime:
        store = FakeStore()
        embedder = FakeEmbedder()

    def fake_build_runtime(config: object) -> FakeRuntime:
        del config
        return FakeRuntime()

    monkeypatch.setattr(main_module, "build_runtime", fake_build_runtime)

    assert main(["embed-pending"]) == 0

    assert embedded_texts == ["Summary matters\n\nBody matters too"]
    assert completed == [("devmem:pending", [1.0, 0.0])]
    assert "Embedded 1/1 pending notes." in capsys.readouterr().out
