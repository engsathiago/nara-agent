# Nara CLI Reference

Live sources when anything looks stale: `nara --help`, `nara <command> --help`,
https://nara-agent.nousresearch.com/docs/reference/cli-commands

### Global Flags

```
nara [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
nara chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
nara setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
nara model                Interactive model/provider picker
nara fallback [add|remove|list]  Fallback provider chain
nara config [show|edit|get|set|unset|path|env-path|check|migrate]
nara login / logout       OAuth sign-in / clear stored auth
nara doctor [--fix]       Check dependencies and config
nara status [--full]      Component summary (--full: every section)
```

### Tools & Skills

```
nara tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

nara skills list|browse|search QUERY|inspect ID
nara skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
nara skills config        Enable/disable skills per platform
nara skills check|update|uninstall|publish PATH
nara skills tap add REPO  Add a GitHub repo as a skill source
nara bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
nara mcp add NAME (--url or --command) | remove | list | test NAME
nara mcp catalog | install NAME     Curated catalog install
nara mcp configure NAME             Toggle tool selection
nara mcp-serve                      Run Nara as an MCP server (mcp-serve plugin)
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
nara gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `nara photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://nara-agent.nousresearch.com/docs/user-guide/messaging/

### Sessions

```
nara sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
nara cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
nara webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
nara profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
nara profile rename A B | alias NAME | export NAME | import FILE
nara profile migrate-identity A B   Retry a completed rename's session/routing identity migration
```

### Credentials & Pools

```
nara auth                 Interactive credential manager
nara auth add [PROVIDER]  Add OAuth or API-key credential (nous, openai-codex, qwen-oauth, …)
nara auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
nara desktop / gui        Native desktop app
nara dashboard            Web admin panel + embedded chat (--stop / --status)
nara proxy                OpenAI-compatible local proxy backed by an OAuth provider
nara portal               Quick setup / sign in via Nous Portal
nara kanban <verb>        Multi-agent work-queue board
nara project              Named multi-folder workspaces (see references/projects-and-folders.md)
nara skin list|use|set    Switch/tweak skins (see references/themes.md)
nara pets <verb>          Pet mascots (see references/petdex.md)
nara memory setup|status|off|reset   Memory provider
nara secrets bitwarden|onepassword   External secret stores
nara moa                  Mixture-of-Agents slots
nara hooks / security / backup / import / checkpoints / console
nara logs [-f] [errors]   View agent/error logs
nara send                 One-off message through a gateway platform
nara pairing / plugins / insights / journey / computer-use
nara acp                  ACP server (IDE integration)
nara completion bash|zsh|fish
nara update / uninstall
```

Plugin- and provider-supplied subcommands (e.g. `nara photon setup`) only appear once their plugin is installed/active. Importing from OpenClaw, Claude Code, Codex CLI or Cursor (`nara import-agent <agent>`, plus the older `nara claw migrate|cleanup`) comes from the `agent-importers` plugin; a fresh `nara setup` that finds one of those agents offers to install it.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `nara config edit` · [Configuration docs](https://nara-agent.nousresearch.com/docs/user-guide/configuration) |
| Tools / toolsets | `nara tools list` · [Tools reference](https://nara-agent.nousresearch.com/docs/reference/tools-reference) |
| Skills catalog | `nara skills browse` · [Skills catalog](https://nara-agent.nousresearch.com/docs/reference/skills-catalog) |
| Provider setup | `nara model` · [Providers guide](https://nara-agent.nousresearch.com/docs/integrations/providers) |
| Env variables | `nara config env-path` · [Env vars reference](https://nara-agent.nousresearch.com/docs/reference/environment-variables) |
| Gateway logs | `~/.nara/logs/gateway.log` (or `nara logs`) |
| Sessions | `nara sessions browse` (reads state.db) |
