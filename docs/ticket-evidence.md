# Ticket Evidence

Each ticket below closes under the release-contract approval shape:

- `scope_complete`: the required repository surface exists.
- `acceptance_evidence_present`: tests, scripts, docs, or CI prove the surface.
- `invariant_preserved`: release-contract invariants still hold.
- `no_regression_to_prior_tickets`: later tickets cite the same contract.

## DMST-00

Release contract: `docs/release-contract.json` and `docs/release-contract.md`.
CI and `scripts/audit_release.py` read the same command, MCP tool, optional
feature, forbidden-pattern, and artifact-clean rules.

## DMST-01

Standalone layout: normal `src/devmem` package, PyPI distribution name
`devmem-mcp`, top-level `pyproject.toml`, README, license, docs, examples,
tests, scripts, and CI workflow.

## DMST-02

Public imports use `devmem`, while the installable distribution is
`devmem-mcp` because the plain `devmem` PyPI project name is already occupied.
The audit script assembles the legacy import pattern from fragments and scans
public source, tests, docs, examples, and package metadata.

## DMST-03

Base MCP exposes only DevMem tools. Shared errors are local. Repository identity
defaults are derived from Git remote or folder name.

## DMST-04

`docs/configuration.md` lists all public environment variables. Config tests
cover explicit slug, Git remote slug, folder fallback, tenant normalization,
SQLite path expansion, and status output.

## DMST-05

`[project.scripts]` exposes `devmem`. The CLI implements the required commands.
MCP preflight spawns `python -m devmem mcp` with an argv list and an optional
`.env` merge.

## DMST-06

Base runtime imports no optional provider, API, database, skill-sync, or
code-indexing modules. Optional OpenAI and API code paths import lazily and
raise explicit feature errors when the needed extra is missing.

## DMST-07

`devmem.mcp_server.BASE_TOOL_NAMES` is the exact base tool surface. Tests verify
the list and assert no workspace-bridge tools are registered.

## DMST-08

Hook templates use the installed `devmem` command, contain no private paths, and
quietly exit when DevMem is absent.

## DMST-09

SQLite self-initializes and has an end-to-end test for reporting, searching,
diagnosing, and feedback with tenant-scoped feedback keys.

## DMST-10

OpenAI and API are isolated extras. Code search and skill sync are deferred in
the release contract and are absent from the base MCP surface.

## DMST-11

Postgres is deferred in the release contract. Public package metadata and docs
do not advertise a usable Postgres extra.

## DMST-12

README, install docs, MCP client docs, configuration docs, privacy docs, and
examples match the implemented CLI and MCP surface.

## DMST-13

CI runs Python 3.11, 3.12, and 3.13. It runs tests, lint, type check, build,
fresh install/import smoke checks, MCP preflight, forbidden-pattern scans, and
artifact inspection.

## DMST-14

Preview publication is guarded by the same CI contract. The local artifact is
built from this standalone layout. `.github/workflows/release.yml` reruns lint,
type check, tests, build, and artifact audit before its manual publish step.
Migration notes for legacy users live outside the public package audit surface.
