# Release Contract

This contract is the closure authority for the preview release. The JSON file
next to this document is the machine-readable source used by CI and local
audits.

## Invariants

- The preview distribution name must be `devmem-mcp`; the import package and
  installed command remain `devmem`.
- Public commands must match `required_commands`.
- Base MCP tools must match `required_base_mcp_tools` exactly.
- Base import and `devmem status` must work without optional provider, API,
  database, skill-sync, or code-indexing packages.
- Optional extras must be documented with the distribution name
  `devmem-mcp[...]`; stale import-name extras install strings are invalid.
- Public source, tests, docs, examples, metadata, wheel, and sdist must not
  contain any assembled forbidden pattern from the JSON contract.
- Hook templates must be portable and degrade quietly when the `devmem` command
  is unavailable.
- SQLite must self-initialize and support `report -> search -> diagnose ->
  feedback` without external services.

## Ticket Approval Record

Ticket approvals are recorded in `docs/ticket-evidence.md`. Each ticket closes
only when scope, evidence, invariant preservation, and non-regression are true.
The proof obligation is Lean-style: the text is a formal closure contract, while
CI and local audit commands provide executable evidence.
