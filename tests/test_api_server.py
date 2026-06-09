from __future__ import annotations

import pytest

from devmem.api_server import create_app

TestClient = pytest.importorskip("fastapi.testclient").TestClient


def test_api_status_is_open_when_api_key_is_unset(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(tmp_path / "devmem.db"))
    monkeypatch.setenv("DEVMEM_REPO_SLUG", "owner/project")
    monkeypatch.delenv("DEVMEM_API_KEY", raising=False)

    client = TestClient(create_app())

    response = client.get("/status")

    assert response.status_code == 200
    assert response.json()["repo_slug"] == "owner/project"


def test_api_status_requires_bearer_token_when_api_key_is_set(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(tmp_path / "devmem.db"))
    monkeypatch.setenv("DEVMEM_REPO_SLUG", "owner/project")
    monkeypatch.setenv("DEVMEM_API_KEY", "local-secret")

    client = TestClient(create_app())

    assert client.get("/status").status_code == 401
    assert client.get("/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert (
        client.get("/status", headers={"Authorization": "Bearer local-secret"}).status_code == 200
    )


def test_api_status_rejects_non_ascii_token_without_crashing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DEVMEM_SQLITE_PATH", str(tmp_path / "devmem.db"))
    monkeypatch.setenv("DEVMEM_REPO_SLUG", "owner/project")
    monkeypatch.setenv("DEVMEM_API_KEY", "local-secret")

    client = TestClient(create_app())

    # Bytes headers bypass httpx's client-side ASCII check the way a raw
    # malicious client would; ASGI decodes them as latin-1 on the server side.
    response = client.get(
        "/status",
        headers=[(b"authorization", "Bearer s\xe9cret".encode("latin-1"))],
    )

    assert response.status_code == 401
