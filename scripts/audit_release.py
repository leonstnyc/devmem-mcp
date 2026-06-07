from __future__ import annotations

import argparse
import json
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path


def _load_contract(root: Path) -> dict[str, object]:
    return json.loads((root / "docs" / "release-contract.json").read_text())


def _forbidden_patterns(contract: dict[str, object]) -> list[str]:
    patterns: list[str] = []
    raw_patterns = contract.get("forbidden_patterns", [])
    if not isinstance(raw_patterns, list):
        return patterns
    for raw in raw_patterns:
        if not isinstance(raw, dict):
            continue
        fragments = raw.get("fragments", [])
        if isinstance(fragments, list) and all(isinstance(fragment, str) for fragment in fragments):
            patterns.append("".join(fragments))
    return patterns


def _public_paths(contract: dict[str, object], root: Path) -> list[Path]:
    raw_paths = contract.get("public_audit_paths", [])
    if not isinstance(raw_paths, list):
        return []
    return [root / str(path) for path in raw_paths]


def _iter_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            if _should_scan(path):
                files.append(path)
        elif path.is_dir():
            files.extend(
                child for child in path.rglob("*") if child.is_file() and _should_scan(child)
            )
    return files


def _should_scan(path: Path) -> bool:
    skipped_parts = {"__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "build", "dist"}
    if skipped_parts.intersection(path.parts):
        return False
    return path.suffix not in {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3"}


def audit_public_tree(root: Path, contract: dict[str, object]) -> list[str]:
    failures: list[str] = []
    patterns = _forbidden_patterns(contract)
    for path in _iter_files(_public_paths(contract, root)):
        text = path.read_text(errors="ignore")
        for pattern in patterns:
            if pattern in text:
                failures.append(f"{path.relative_to(root)} contains forbidden pattern {pattern!r}")
    return failures


def audit_metadata(root: Path, contract: dict[str, object]) -> list[str]:
    failures: list[str] = []
    pyproject_path = root / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text())
    project = pyproject.get("project", {})
    if not isinstance(project, dict):
        return ["pyproject.toml [project] table is missing"]

    expected_distribution = contract.get("distribution_name")
    if not isinstance(expected_distribution, str) or not expected_distribution:
        failures.append("release contract distribution_name must be a non-empty string")
    elif project.get("name") != expected_distribution:
        failures.append(
            "pyproject.toml project.name "
            f"{project.get('name')!r} != contract distribution_name {expected_distribution!r}"
        )

    expected_import = contract.get("import_package")
    if not isinstance(expected_import, str) or not expected_import:
        failures.append("release contract import_package must be a non-empty string")
    else:
        package_init = root / "src" / expected_import / "__init__.py"
        if not package_init.is_file():
            failures.append(f"import package {expected_import!r} is missing src package")

    expected_command = contract.get("console_command")
    scripts = project.get("scripts", {})
    if not isinstance(expected_command, str) or not expected_command:
        failures.append("release contract console_command must be a non-empty string")
    elif not isinstance(scripts, dict):
        failures.append("pyproject.toml project.scripts table is missing")
    elif isinstance(expected_import, str) and scripts.get(expected_command) != (
        f"{expected_import}.__main__:main"
    ):
        failures.append(
            "pyproject.toml console command "
            f"{expected_command!r} does not target {expected_import}.__main__:main"
        )
    return failures


def _required_strings(contract: dict[str, object], key: str) -> set[str]:
    values = contract.get(key)
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        return set()
    return set(values)


def audit_runtime_surface(root: Path, contract: dict[str, object]) -> list[str]:
    failures: list[str] = []
    src_path = str(root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    required_commands = _required_strings(contract, "required_commands")
    if not required_commands:
        failures.append("release contract required_commands must be a non-empty string list")
    else:
        try:
            from devmem.__main__ import build_parser

            parser = build_parser()
            choices = {}
            for action in parser._actions:
                action_choices = getattr(action, "choices", None)
                if isinstance(action_choices, dict) and "mcp" in action_choices:
                    choices = action_choices
                    break
            actual_commands = set(choices)
        except Exception as exc:
            failures.append(
                f"failed to inspect CLI commands: {type(exc).__name__}: {str(exc)[:200]}"
            )
        else:
            if actual_commands != required_commands:
                failures.append(
                    "CLI command mismatch: "
                    f"expected {sorted(required_commands)}, got {sorted(actual_commands)}"
                )

    required_tools = _required_strings(contract, "required_base_mcp_tools")
    if not required_tools:
        failures.append("release contract required_base_mcp_tools must be a non-empty string list")
    else:
        try:
            from devmem.mcp_server import BASE_TOOL_NAMES
        except Exception as exc:
            failures.append(f"failed to inspect MCP tools: {type(exc).__name__}: {str(exc)[:200]}")
        else:
            actual_tools = set(BASE_TOOL_NAMES)
            if actual_tools != required_tools:
                failures.append(
                    "MCP tool mismatch: "
                    f"expected {sorted(required_tools)}, got {sorted(actual_tools)}"
                )
    return failures


def audit_artifacts(root: Path, dist: Path, contract: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if not dist.exists():
        return failures
    patterns = _forbidden_patterns(contract)
    for artifact in dist.iterdir():
        if artifact.suffix == ".whl":
            with zipfile.ZipFile(artifact) as wheel:
                for member in wheel.namelist():
                    data = wheel.read(member)
                    for pattern in patterns:
                        if pattern.encode() in data:
                            failures.append(f"{artifact.name}:{member} contains {pattern!r}")
        elif artifact.suffixes[-2:] == [".tar", ".gz"]:
            with tarfile.open(artifact) as sdist:
                for member in sdist.getmembers():
                    if not member.isfile():
                        continue
                    extracted = sdist.extractfile(member)
                    if extracted is None:
                        continue
                    data = extracted.read()
                    for pattern in patterns:
                        if pattern.encode() in data:
                            failures.append(f"{artifact.name}:{member.name} contains {pattern!r}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--dist")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    contract = _load_contract(root)
    failures = audit_metadata(root, contract)
    failures.extend(audit_runtime_surface(root, contract))
    failures.extend(audit_public_tree(root, contract))
    if args.dist:
        failures.extend(audit_artifacts(root, Path(args.dist), contract))
    if failures:
        for failure in failures:
            print(failure)
        return 1
    print("release audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
