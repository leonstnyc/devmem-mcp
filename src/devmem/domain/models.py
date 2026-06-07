from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DevMemNoteKind(StrEnum):
    CODEBASE_GOTCHA = "codebase_gotcha"
    ERROR_SOLUTION = "error_solution"
    ARCHITECTURE_INSIGHT = "architecture_insight"


class FeedbackRating(StrEnum):
    HELPFUL = "helpful"
    OUTDATED = "outdated"
    WRONG = "wrong"


@dataclass(frozen=True)
class DevMemNote:
    note_id: str
    tenant_id: str
    note_kind: DevMemNoteKind
    summary_text: str
    text: str
    file_paths: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    module: str | None = None
    error_pattern: str | None = None
    error_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def embedding_text(self) -> str:
        return f"{self.summary_text}\n\n{self.text}".strip()

    def public_metadata(self) -> dict[str, Any]:
        metadata = dict(self.metadata)
        metadata.update(
            {
                "note_kind": self.note_kind.value,
                "summary_text": self.summary_text,
                "tenant_id": self.tenant_id,
                "file_paths": list(self.file_paths),
            }
        )
        if self.module:
            metadata["module"] = self.module
        if self.error_pattern:
            metadata["error_pattern"] = self.error_pattern
        if self.error_type:
            metadata["error_type"] = self.error_type
        return metadata


def normalize_tenant_id(value: str | None) -> str:
    tenant_id = (value or "default").strip()
    return tenant_id or "default"


def tags_for_note(note: DevMemNote, extra_tags: tuple[str, ...] = ()) -> tuple[str, ...]:
    tags: list[str] = [
        "kind:devmem",
        f"note_kind:{note.note_kind.value}",
        f"tenant:{note.tenant_id}",
    ]
    tags.extend(f"file:{path}" for path in note.file_paths if path)
    if note.module:
        tags.append(f"module:{note.module}")
    tags.extend(tag for tag in note.tags if tag)
    tags.extend(tag for tag in extra_tags if tag)
    return tuple(dict.fromkeys(tags))
