from __future__ import annotations

import subprocess
from pathlib import Path

from devmem.domain.config import DevMemConfig, derive_repo_slug


def test_config_explicit_repo_slug(monkeypatch) -> None:
    monkeypatch.setenv("DEVMEM_REPO_SLUG", "owner/project")

    assert DevMemConfig().repo_slug == "owner/project"


def test_config_derives_repo_slug_from_git_remote(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DEVMEM_REPO_SLUG", raising=False)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@example.com:owner/project.git"],
        cwd=tmp_path,
        check=True,
    )

    assert derive_repo_slug(str(tmp_path)) == "owner/project"


def test_config_falls_back_to_folder_name(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DEVMEM_REPO_SLUG", raising=False)

    assert derive_repo_slug(str(tmp_path)) == tmp_path.name


def test_config_normalizes_sqlite_and_tenant(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "devmem.db"
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(db_path))
    monkeypatch.setenv("DEVMEM_TENANT_ID", "  ")
    monkeypatch.setenv("DEVMEM_PRIMARY_STORE", " SQLITE ")
    monkeypatch.setenv("DEVMEM_OPENAI_TIMEOUT_SECONDS", "7.5")

    config = DevMemConfig()

    assert config.sqlite_path == str(db_path)
    assert config.primary_store == "sqlite"
    assert config.normalized_tenant_id() == "default"
    assert config.openai_timeout_seconds == 7.5
