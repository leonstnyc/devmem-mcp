from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from devmem.domain.errors import OptionalFeatureError


@dataclass(frozen=True)
class OpenAIEmbedder:
    api_key: str
    model: str
    _client: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            raise OptionalFeatureError(
                "OpenAI embeddings require installing the 'devmem[openai]' extra."
            ) from exc
        object.__setattr__(self, "_client", OpenAI(api_key=self.api_key))

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(model=self.model, input=text)
        return list(response.data[0].embedding)
