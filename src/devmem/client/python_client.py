from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class DevMemClient:
    base_url: str
    api_key: str = ""
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def status(self) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout_seconds, headers=self._headers()) as client:
            response = client.get(f"{self.base_url.rstrip('/')}/status")
            response.raise_for_status()
            return dict(response.json())
