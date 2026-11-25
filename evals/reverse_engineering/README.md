# Reverse Engineering Lab acceptance fixture

This fixture is owned by the Nara test suite and exists only to prove the read-only routing and
evidence contract.

Validated locally on 2026-11-22:

- `rea-agents@6.7.0` reported 153 CLI commands, 207 MCP tools, 6 prompts, and catalog digest
  `96d8f6e6ea1b1ba13557216624a3461c738729d53c79b4b0100d1f3a3a32441c`.
- `analyze-javascript-application` parsed `electron_fixture/index.js` as inert text and sealed the
  application evidence without executing the fixture.
- Clang produced an arm64 Mach-O fixture with SHA-256
  `a4484c9fcef2fed5cec6ac8943340803a4c555f3c68bcddc27bf479df87f5edc` in the observed run.
- Ghidra 12.1.4, invoked through REA, recovered `_nara_fixture_transform` as
  `return param_1 * 7 + 3;` and linked its caller. Ghidra used an ephemeral project and did not write
  to the original binary.

The compiled artifact is intentionally not committed. Its digest can change with compiler or SDK;
the source behavior and the evidence assertions are the stable acceptance criteria.
