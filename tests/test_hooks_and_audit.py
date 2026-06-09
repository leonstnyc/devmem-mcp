from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_release import (
    audit_artifacts,
    audit_metadata,
    audit_public_tree,
    audit_runtime_surface,
)


def test_hook_templates_are_portable() -> None:
    root = Path(__file__).resolve().parents[1]
    templates = [
        root / "src" / "devmem" / "hooks" / "templates" / "session_start.sh",
        root / "src" / "devmem" / "hooks" / "templates" / "session_stop.sh",
        root / "examples" / "session-hooks" / "session_start.sh",
        root / "examples" / "session-hooks" / "session_stop.sh",
    ]

    for template in templates:
        text = template.read_text()
        assert "command -v devmem" in text
        assert "exit 0" in text
        assert "/Users/" not in text


def test_public_tree_forbidden_pattern_audit_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "docs" / "release-contract.json").read_text())

    assert audit_public_tree(root, contract) == []


def test_release_metadata_audit_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "docs" / "release-contract.json").read_text())

    assert audit_metadata(root, contract) == []


def test_release_runtime_surface_audit_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "docs" / "release-contract.json").read_text())

    assert audit_runtime_surface(root, contract) == []


def test_release_artifact_audit_rejects_stale_distribution_names(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "docs" / "release-contract.json").read_text())
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "devmem-0.1.0-py3-none-any.whl").write_bytes(b"stale artifact")

    assert audit_artifacts(root, dist, contract) == [
        "devmem-0.1.0-py3-none-any.whl is not a 'devmem-mcp' artifact; remove stale build outputs"
    ]
