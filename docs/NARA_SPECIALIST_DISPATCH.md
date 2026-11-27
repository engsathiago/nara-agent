# Specialist instructions at native delegation

With Mission Control loaded, a native `delegate_task` call resolves each task against
Legião and installed skills before child dispatch. It loads the complete instructions
of the selected candidate, verifies their SHA-256 against the resolver's selection,
and appends them to that child's context. The existing native delegation implementation
continues to create, route, track and finish children.

Configure the catalog in the active profile's `config.yaml`:

```yaml
plugins:
  entries:
    mission_control:
      settings:
        legiao_path: /absolute/path/to/Legiao-Local
        specialist_delegation: true
```

Automatic composition defaults to enabled when Mission Control is loaded. Set
`specialist_delegation: false` to retain ordinary delegation. Legacy
`plugins.mission_control.legiao_path` remains a fallback; an existing
`NARA_LEGIAO_HOME` override retains precedence. The catalog needs `data/agents.json`
and `data/commands.json`. No match leaves that task's context unchanged. Single-goal
and task-list calls are supported; list/steer/stop controls are passed through.
Skill contexts also name the originating `SKILL.md` so relative references can be resolved.

Preparation is frozen per `(session_id, tool_call_id)` in the active profile's
`plugin-data/mission-control/specialist-bindings.db`. Replaying the same original
arguments returns the same instructions even if the catalog changes; different
arguments under that identity are a technical error. A new call can use a newer
catalog. The transaction serializes competing first preparations. The store contains
full prepared context and selected instructions, stays local with restricted file
permissions, and is not exported to external telemetry by this implementation.
Original parent tool-call arguments are not mutated. Without both stable IDs, a fresh
binding is created and cross-call replay is not promised.

A request or serialized binding above 1 MiB, storage errors, or a changed/corrupt
prompt hash returns the public pre-tool `error` directive. The tool fails before
execution, including in unrestricted authorization mode. This requires the host
support introduced in PR #75. Effect receipts/policy checks see the composed arguments.
Other independently registered hooks follow host ordering and may modify the same
keys; this binding records Mission Control preparation, not every later middleware result.

## Verified scope and remaining work

The runtime test loads the plugin through real discovery, runs a real parent AIAgent,
and inspects the child's HTTP request at a deterministic local provider. It verifies
selected instructions and original context reach the child, other specialists' prompts
do not, parent tool-call arguments remain unchanged, and a preparation failure is
reported without child dispatch. This proves wiring, not model quality or three-model
team performance.

The stored model recommendation is advisory. Actual model routing remains owned by
the configured delegation backend, including `nara-measured`. This feature does not
freeze a full Agent Profile, apply new per-worker tool/MCP permissions, allocate new
budgets or memory scopes, or grant orchestrator authority from catalog metadata.
Those integrations and the real varied-model acceptance remain open.
