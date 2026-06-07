from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True)
class LocalHashEmbedder:
    dimension: int = 256

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign * (1.0 + digest[5] / 255.0)

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]
