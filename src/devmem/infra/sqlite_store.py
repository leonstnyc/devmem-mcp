from __future__ import annotations

import json
import math
import posixpath
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from devmem.domain.models import FeedbackRating

_SCHEMA_VERSION = 1
_RATING_SCORES: dict[FeedbackRating, float] = {
    FeedbackRating.HELPFUL: 1.0,
    FeedbackRating.OUTDATED: 0.1,
    FeedbackRating.WRONG: 0.0,
}


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _loads_json(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _text_score(query: str, row: dict[str, Any]) -> float:
    terms = {term for term in query.lower().split() if term}
    if not terms:
        return 0.0
    haystack = " ".join(
        str(row.get(key, ""))
        for key in ("summary_text", "text", "note_kind", "tags_json", "metadata_json")
    ).lower()
    matches = sum(1 for term in terms if term in haystack)
    return matches / len(terms)


def _normalize_file_path(value: str) -> str:
    path = posixpath.normpath(value.strip().replace("\\", "/"))
    return "" if path == "." else path


def _is_absolute_file_path(value: str) -> bool:
    return value.startswith("/") or (len(value) >= 3 and value[1:3] == ":/")


def _file_path_matches(left: str, right: str) -> bool:
    left_path = _normalize_file_path(left)
    right_path = _normalize_file_path(right)
    if not left_path or not right_path:
        return False
    if left_path == right_path:
        return True
    if not (_is_absolute_file_path(left_path) or _is_absolute_file_path(right_path)):
        return False

    left_parts = tuple(part for part in left_path.split("/") if part)
    right_parts = tuple(part for part in right_path.split("/") if part)
    if len(left_parts) <= len(right_parts):
        shorter, longer = left_parts, right_parts
    else:
        shorter, longer = right_parts, left_parts
    if len(shorter) < 2:
        return False
    return longer[-len(shorter) :] == shorter


@dataclass
class SqliteDevMemStore:
    path: str
    _schema_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _schema_ready: bool = field(default=False, init=False, repr=False)

    def _connect(self) -> sqlite3.Connection:
        db_path = Path(self.path).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        self._ensure_schema(conn)
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS devmem_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS devmem_notes (
                    note_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    note_kind TEXT NOT NULL,
                    summary_text TEXT NOT NULL,
                    text TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding_status TEXT NOT NULL DEFAULT 'complete',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_devmem_notes_tenant_kind
                    ON devmem_notes (tenant_id, note_kind, created_at);
                CREATE TABLE IF NOT EXISTS devmem_feedback (
                    tenant_id TEXT NOT NULL,
                    note_id TEXT NOT NULL,
                    rating TEXT NOT NULL,
                    score REAL NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, note_id)
                );
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO devmem_meta (key, value) VALUES (?, ?)",
                ("schema_version", str(_SCHEMA_VERSION)),
            )
            conn.commit()
            self._schema_ready = True

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
        self._upsert_note(
            note_id=note_id,
            tenant_id=tenant_id,
            note_kind=note_kind,
            summary_text=summary_text,
            text=text,
            embedding_json=json.dumps(embedding),
            tags=tags,
            metadata=metadata,
            embedding_status="complete",
        )

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
        self._upsert_note(
            note_id=note_id,
            tenant_id=tenant_id,
            note_kind=note_kind,
            summary_text=summary_text,
            text=text,
            embedding_json="[]",
            tags=tags,
            metadata=metadata,
            embedding_status="pending",
        )

    def _upsert_note(
        self,
        *,
        note_id: str,
        tenant_id: str,
        note_kind: str,
        summary_text: str,
        text: str,
        embedding_json: str,
        tags: tuple[str, ...],
        metadata: dict[str, Any],
        embedding_status: str,
    ) -> None:
        now = _utcnow_iso()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO devmem_notes (
                    note_id, tenant_id, note_kind, summary_text, text, embedding_json,
                    tags_json, metadata_json, embedding_status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(note_id) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    note_kind = excluded.note_kind,
                    summary_text = excluded.summary_text,
                    text = excluded.text,
                    embedding_json = excluded.embedding_json,
                    tags_json = excluded.tags_json,
                    metadata_json = excluded.metadata_json,
                    embedding_status = excluded.embedding_status,
                    updated_at = excluded.updated_at
                """,
                (
                    note_id,
                    tenant_id,
                    note_kind,
                    summary_text,
                    text,
                    embedding_json,
                    json.dumps(list(tags)),
                    json.dumps(metadata),
                    embedding_status,
                    now,
                    now,
                ),
            )

    def get_pending_notes(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT note_id, tenant_id, note_kind, summary_text, text, embedding_json,
                       tags_json, metadata_json, embedding_status, created_at, updated_at
                FROM devmem_notes
                WHERE embedding_status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return [self._row_to_result(row, similarity=0.0) for row in rows]

    def complete_pending_note(self, *, note_id: str, embedding: list[float]) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE devmem_notes
                SET embedding_json = ?, embedding_status = 'complete', updated_at = ?
                WHERE note_id = ?
                """,
                (json.dumps(embedding), _utcnow_iso(), note_id),
            )

    def query_semantic(
        self,
        *,
        embedding: list[float],
        tenant_id: str,
        kinds: tuple[str, ...] = (),
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        rows = self._candidate_rows(tenant_id=tenant_id, kinds=kinds, complete_only=True)
        scored = [
            self._row_to_result(
                row,
                similarity=_cosine(embedding, _loads_json(row["embedding_json"], [])),
            )
            for row in rows
        ]
        scored.sort(
            key=lambda item: (
                float(item.get("similarity", 0.0))
                + self.feedback_score(tenant_id=tenant_id, note_id=str(item["note_id"])) * 0.05,
                str(item.get("created_at", "")),
            ),
            reverse=True,
        )
        return scored[: max(0, limit)]

    def query_text(
        self,
        *,
        query: str,
        tenant_id: str,
        kinds: tuple[str, ...] = (),
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        rows = self._candidate_rows(tenant_id=tenant_id, kinds=kinds, complete_only=False)
        results = [
            self._row_to_result(row, similarity=_text_score(query, dict(row))) for row in rows
        ]
        results = [result for result in results if float(result.get("similarity", 0.0)) > 0.0]
        results.sort(key=lambda item: float(item.get("similarity", 0.0)), reverse=True)
        return results[: max(0, limit)]

    def query_by_files(
        self,
        *,
        file_paths: tuple[str, ...],
        tenant_id: str,
        include_kinds: tuple[str, ...] = (),
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        wanted = {_normalize_file_path(path) for path in file_paths if path}
        wanted.discard("")
        if not wanted:
            return []
        rows = self._candidate_rows(tenant_id=tenant_id, kinds=include_kinds, complete_only=False)
        matches: list[dict[str, Any]] = []
        for row in rows:
            result = self._row_to_result(row, similarity=1.0)
            metadata = result.get("metadata")
            raw_row_paths = metadata.get("file_paths", []) if isinstance(metadata, dict) else []
            row_paths = {
                _normalize_file_path(path) for path in raw_row_paths if isinstance(path, str)
            }
            tags = set(result.get("tags", []))
            tag_paths = {
                _normalize_file_path(tag.removeprefix("file:"))
                for tag in tags
                if isinstance(tag, str) and tag.startswith("file:")
            }
            available_paths = (row_paths | tag_paths) - {""}
            if any(
                _file_path_matches(wanted_path, row_path)
                for wanted_path in wanted
                for row_path in available_paths
            ):
                matches.append(result)
            if len(matches) >= limit:
                break
        return matches

    def set_feedback(
        self,
        *,
        tenant_id: str,
        note_id: str,
        rating: FeedbackRating,
    ) -> float:
        score = _RATING_SCORES[rating]
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO devmem_feedback (tenant_id, note_id, rating, score, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, note_id) DO UPDATE SET
                    rating = excluded.rating,
                    score = excluded.score,
                    updated_at = excluded.updated_at
                """,
                (tenant_id, note_id, rating.value, score, _utcnow_iso()),
            )
        return score

    def feedback_score(self, *, tenant_id: str, note_id: str) -> float:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT score FROM devmem_feedback WHERE tenant_id = ? AND note_id = ?",
                (tenant_id, note_id),
            ).fetchone()
        if row is None:
            return 0.5
        return float(row["score"])

    def count_notes(self) -> int:
        with self._connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM devmem_notes").fetchone()
        return int(row["count"]) if row is not None else 0

    def _candidate_rows(
        self,
        *,
        tenant_id: str,
        kinds: tuple[str, ...],
        complete_only: bool,
    ) -> list[sqlite3.Row]:
        predicates = ["tenant_id = ?"]
        params: list[Any] = [tenant_id]
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            predicates.append(f"note_kind IN ({placeholders})")
            params.extend(kinds)
        if complete_only:
            predicates.append("embedding_status = 'complete'")
        where = " AND ".join(predicates)
        with self._connection() as conn:
            return conn.execute(
                f"""
                SELECT note_id, tenant_id, note_kind, summary_text, text, embedding_json,
                       tags_json, metadata_json, embedding_status, created_at, updated_at
                FROM devmem_notes
                WHERE {where}
                ORDER BY created_at DESC
                """,
                tuple(params),
            ).fetchall()

    @staticmethod
    def _row_to_result(row: sqlite3.Row, *, similarity: float) -> dict[str, Any]:
        tags = tuple(str(tag) for tag in _loads_json(row["tags_json"], []))
        metadata = _loads_json(row["metadata_json"], {})
        return {
            "note_id": row["note_id"],
            "tenant_id": row["tenant_id"],
            "note_kind": row["note_kind"],
            "summary_text": row["summary_text"],
            "text": row["text"],
            "tags": tags,
            "metadata": metadata if isinstance(metadata, dict) else {},
            "embedding_status": row["embedding_status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "similarity": similarity,
        }
