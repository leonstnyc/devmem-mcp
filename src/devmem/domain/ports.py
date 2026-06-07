from __future__ import annotations

from typing import Any, Protocol

from devmem.domain.models import FeedbackRating


class TextEmbedderPort(Protocol):
    def embed(self, text: str) -> list[float]:
        """Return an embedding vector for text."""
        ...


class DevMemStorePort(Protocol):
    path: str

    def put(
        self,
        *,
        note_id: str,
        tenant_id: str,
        note_kind: str,
        summary_text: str,
        text: str,
        embedding: list[float],
        tags: tuple[str, ...],
        metadata: dict[str, Any],
    ) -> None:
        """Persist a complete memory note."""

    def put_pending_note(
        self,
        *,
        note_id: str,
        tenant_id: str,
        note_kind: str,
        summary_text: str,
        text: str,
        tags: tuple[str, ...],
        metadata: dict[str, Any],
    ) -> None:
        """Persist a note that still needs embedding."""

    def get_pending_notes(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """Return pending notes for embedding replay."""
        ...

    def complete_pending_note(self, *, note_id: str, embedding: list[float]) -> None:
        """Attach an embedding and mark a pending note complete."""

    def query_semantic(
        self,
        *,
        embedding: list[float],
        tenant_id: str,
        kinds: tuple[str, ...] = (),
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search complete notes by vector similarity."""
        ...

    def query_text(
        self,
        *,
        query: str,
        tenant_id: str,
        kinds: tuple[str, ...] = (),
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search notes with a dependency-free text fallback."""
        ...

    def query_by_files(
        self,
        *,
        file_paths: tuple[str, ...],
        tenant_id: str,
        include_kinds: tuple[str, ...] = (),
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find memories related to any file path."""
        ...

    def set_feedback(
        self,
        *,
        tenant_id: str,
        note_id: str,
        rating: FeedbackRating,
    ) -> float:
        """Record tenant-scoped feedback and return the score."""
        ...

    def feedback_score(self, *, tenant_id: str, note_id: str) -> float:
        """Return a note's tenant-scoped feedback score."""
        ...

    def count_notes(self) -> int:
        """Return complete and pending note count."""
        ...
