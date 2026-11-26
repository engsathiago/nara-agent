# Nara installation, recovery, and release operations

## Supported command and state

The product command is `nara`. Mission Control is bundled. Temporal memory is distributed from
`extensions/nara_temporal_memory`; REA is pinned in `plugin-catalog/rea.yaml`. Runtime state belongs
to the selected `NARA_HOME` profile, not to the source checkout.

## Local installation

1. Clone or unpack the Nara source release.
2. Run `scripts/install.sh` on macOS/Linux, `scripts/install.ps1` in PowerShell, or
   `scripts/install.cmd` from Command Prompt.
3. Install/copy the temporal provider as documented in
   `extensions/nara_temporal_memory/README.md` and select `memory.provider: nara_temporal`.
4. Run `nara pm repair`, `nara plugins validate plugins/mission_control`, `nara memory status`, and
   `nara doctor`.
5. Verify `nara --version`, `nara mission list`, and the authenticated Nara Office dashboard.

For external memory access, configure the owner-only client file and start
`nara nara_temporal serve --clients-file /absolute/private/path/memory-clients.json`.
The command serves authenticated API and MCP on loopback using the selected
profile's canonical temporal database. See the provider README for endpoint,
token, scope and candidate rules. This service is optional and has its own
process lifecycle; start it again after provider code or client-file changes.
For local semantic recall, pull `embeddinggemma`, select it in the temporal
provider settings, run `nara nara_temporal index`, and inspect
`nara nara_temporal status`. The embedding service runs on loopback. If it
fails, each search reports `lexical_degraded` in its receipt rather than
silently claiming hybrid retrieval.

For procedural learning, use `nara mission learn-extract` after a verified
mission, then `learn-evaluate` on reserved cases, `learn-show`, and
`learn-promote`. The executable evaluator contract and rollback path are in
`docs/NARA_LEARNING_EVALUATION.md`. A candidate is not active merely because
the extraction file exists. The gateway also runs due-gated consolidation for
completed missions and proposes inactive candidates. Run
`nara mission learn-consolidate` to process them immediately; the command
reports created, unchanged, skipped, and failed missions.
Use `nara mission learn-status` or the `nara_learning_status` tool to inspect
pending missions, the last gateway pass, and visible extraction errors.

For local audio/video source learning, see `docs/NARA_MEDIA_LEARNING.md`.

The validated offline baseline is Ollama at `http://127.0.0.1:11434/v1` with `qwen3.5:4b` and a
64,000-token configured context. Confirm the model with a text turn and a real Mission Control tool
call; a direct Ollama response alone does not prove agent integration. Other local or cloud providers
remain replaceable.

On macOS, keep the autonomous runtime supervised with:

```sh
nara gateway install --start-now --start-on-login
nara gateway status
```

This installs the per-user LaunchAgent. Use `nara gateway stop` before changing runtime code or the
active profile, then restart the service so it does not retain old plugin handlers. Start the visual
surface with `nara dashboard --no-open`; verify `/api/dashboard/plugins` lists `mission-control` and
the authenticated `/api/plugins/mission-control/state` response before relying on Nara Office.

The current macOS profile already uses the external temporal provider. A Linux/VPS install repeats
the same checks after the host and credentials are supplied; it is not represented as tested before
that machine exists.

## Backup and restore

Create a full state archive before updates:

```sh
nara backup --output /absolute/path/nara-backup.zip
```

This includes profile configuration, missions, plugin data, memory, skills, sessions, evaluations,
and installed user plugins according to the built-in backup policy. Keep the archive private: a full
profile may contain credentials. Restore into the selected profile with:

```sh
NARA_HOME=/absolute/path/to/profile nara import --force /absolute/path/nara-backup.zip
```

The importer preflights ZIP integrity and traversal, restores SQLite through safe page copies, and
preserves runtime epoch rules. After restore, run `nara doctor`, `nara mission list`, and
`nara memory status` before resuming workers.

## Update and rollback

Use `nara update --plan` first. Production updates use `nara update --backup --yes`; do not use
`--no-backup`. If validation fails, stop the affected gateways, restore the pre-update archive into
the exact profile, return the source checkout/package to the manifest commit, run `nara pm repair`,
then resume the mission. Confirmed effect receipts remain authoritative and must not be replayed.

The acceptance test creates a running mission plus memory, a learned skill, and a holdout result;
it archives and restores all four, then confirms that the mission remains `running` rather than
being recreated.

## Release manifest

Generate the secret-free content manifest only from a clean release commit:

```sh
scripts/nara-python scripts/nara_product_manifest.py --output /absolute/path/nara-manifest.json
```

The manifest records the Nara command, commit, branch, content hashes, required components, and state
schema compatibility. Refuse publication when `working_tree_clean` is false or any release gate is
not evidenced. Public publication, signing keys, and release-channel upload require a separate
explicit authorization; local packaging does not publish anything.
