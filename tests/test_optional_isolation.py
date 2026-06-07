from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_base_import_does_not_import_optional_modules() -> None:
    src_path = Path(__file__).resolve().parents[1] / "src"
    code = """
import sys
import devmem
forbidden = {"openai", "psycopg", "fastapi", "uvicorn", "anthropic", "requests"}
loaded = sorted(name for name in forbidden if name in sys.modules)
print(",".join(loaded))
raise SystemExit(1 if loaded else 0)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(src_path)},
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_api_import_is_lazy() -> None:
    import devmem.api_server as api_server

    assert callable(api_server.create_app)
