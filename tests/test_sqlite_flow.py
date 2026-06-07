from __future__ import annotations

from pathlib import Path

from devmem.app.services import DevMemFeedbackRecorder, DevMemReporter, DevMemRetriever
from devmem.domain.models import DevMemNoteKind, FeedbackRating
from devmem.infra.local_embedder import LocalHashEmbedder
from devmem.infra.sqlite_store import SqliteDevMemStore


def _services(
    tmp_path: Path,
) -> tuple[SqliteDevMemStore, DevMemReporter, DevMemRetriever, DevMemFeedbackRecorder]:
    store = SqliteDevMemStore(path=str(tmp_path / "devmem.db"))
    embedder = LocalHashEmbedder(dimension=64)
    return (
        store,
        DevMemReporter(store=store, embedder=embedder, repo_slug="owner/project"),
        DevMemRetriever(store=store, embedder=embedder),
        DevMemFeedbackRecorder(store=store),
    )


def test_sqlite_report_search_diagnose_feedback_flow(tmp_path: Path) -> None:
    store, reporter, retriever, feedback = _services(tmp_path)

    report = reporter.report(
        kind=DevMemNoteKind.ERROR_SOLUTION,
        text="Run migrations before opening the SQLite store.",
        summary_text="SQLite missing table fix",
        tenant_id="tenant-a",
        file_paths=("src/db.py",),
        error_pattern="OperationalError: no such table",
    )

    search = retriever.search(tenant_id="tenant-a", query="SQLite table migration", limit=5)
    diagnose = retriever.diagnose(
        tenant_id="tenant-a",
        error_message="OperationalError: no such table",
        limit=5,
    )
    score = feedback.record(
        tenant_id="tenant-a",
        note_id=report.memory_id,
        rating=FeedbackRating.HELPFUL,
    )

    assert report.memory_id.startswith("devmem:")
    assert search.memories
    assert diagnose.memories
    assert score == 1.0
    assert store.feedback_score(tenant_id="tenant-a", note_id=report.memory_id) == 1.0
    assert store.feedback_score(tenant_id="tenant-b", note_id=report.memory_id) == 0.5
    assert store.count_notes() == 1


def test_sqlite_self_initializes_and_embeds_pending(tmp_path: Path) -> None:
    store = SqliteDevMemStore(path=str(tmp_path / "devmem.db"))
    store.put_pending_note(
        note_id="devmem:pending",
        tenant_id="default",
        note_kind="codebase_gotcha",
        summary_text="Pending",
        text="Needs embedding",
        tags=("kind:devmem",),
        metadata={},
    )

    pending = store.get_pending_notes()
    store.complete_pending_note(note_id="devmem:pending", embedding=[1.0, 0.0])

    assert pending[0]["note_id"] == "devmem:pending"
    assert store.query_semantic(embedding=[1.0, 0.0], tenant_id="default")
