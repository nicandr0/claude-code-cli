# claude-code-cli

Minimal Docker image for the official Anthropic Claude Code CLI. Native
MCP server support, native plugin marketplace, native skills, agents, and
sub-agents — all as shipped by Anthropic, unmodified. Verified end-to-end
(build, restart persistence, MCP round-trip, plugin install, skill
invocation, sub-agent spawn, container recreate) before being tagged
`validated` and pushed.

Two optional pieces are baked into the same image, on top of the
vanilla CLI:

- **A browser-terminal WebUI** ([ttyd](https://github.com/tsl0922/ttyd))
  that opens straight into an authenticated `claude` session — the
  equivalent of `docker exec -it claude-code claude`, in a browser tab.
  Not a dashboard, not a general-purpose shell.
- **cc-bridge**, a small FastAPI HTTP server for programmatic access
  (e.g. a Telegram bot or other chat frontend) that calls `claude -p` as
  a local subprocess. See [cc-bridge](#cc-bridge) below.

No message bus, no PTY supervisor, no custom plugin-loading mechanism —
both pieces are just processes launched by one startup script
([docker/start.sh](docker/start.sh)), calling Claude Code's own commands
directly.

An [Unraid Docker template](#unraid-template) is included for anyone
running this on Unraid — see that section for how to add it.

## What's actually in the image

- Base: `node:22-bookworm-slim`
- Runs as a dedicated non-root user (`claude`), not root
- `DISABLE_AUTOUPDATER=1` set as a Dockerfile `ENV`
- `CLAUDE_CONFIG_DIR=/home/claude/.claude` — where login credentials and
  Claude Code settings live
- npm global prefix redirected to `/home/claude/.npm-global` so global
  installs don't need root
- Extra packages: `git`, `curl`, `ca-certificates`, `ripgrep`, `procps`
  (ripgrep backs Claude Code's Grep tool; procps is for basic process
  visibility inside the container)
- Installs `@anthropic-ai/claude-code@latest` via npm at build time — no
  version pin baked in. To pin a version, edit the `npm install` line in
  the Dockerfile directly (`@anthropic-ai/claude-code@X.Y.Z`) and rebuild.
- `ttyd` (pinned to `1.7.7`, static binary) launches `claude` directly on
  port `7681` — see [WebUI](#webui-browser-terminal)
- A Python venv at `/home/claude/.venvs/cc-bridge` runs cc-bridge
  (FastAPI + uvicorn) on port `8642` — see [cc-bridge](#cc-bridge)
- `docker/start.sh` is the image's `ENTRYPOINT`: it backgrounds the
  cc-bridge uvicorn process, then `exec`s `ttyd` as PID 1. You can still
  `docker exec` into the container for anything else (`claude`, `claude
  mcp`, `claude plugin`, etc.) exactly as before

## Installation method

Uses `npm install -g @anthropic-ai/claude-code`. Anthropic's currently
recommended install method is `curl -fsSL https://claude.ai/install.sh | bash`,
but that script returns HTTP 403 when run from Docker builds or CI
(Cloudflare blocks non-browser automated requests — see
[anthropics/claude-code#36306](https://github.com/anthropics/claude-code/issues/36306)).
npm is marked deprecated in upstream docs but remains published and
functional, and is the reliable option for unattended builds until that
issue is resolved.

## Build

```bash
docker compose build
```

## Start

```bash
docker compose up -d
```

`docker-compose.yml` sets `stdin_open: true` and `tty: true` — needed for
Ink-based TUI output (e.g. `claude doctor`) to render correctly through
`docker exec -it`.

## First-time login

```bash
docker exec -it claude-code claude login
```

Runs as the `claude` user (the container's default user). Credentials
land in the `claude-config` named volume, mounted at
`/home/claude/.claude` — survives `docker restart`, `docker compose down
&& up`, and image rebuilds, as long as the volume itself isn't removed.

## Using it

Interactive session:

```bash
docker exec -it claude-code claude
```

Non-interactive / scriptable:

```bash
docker exec -i claude-code claude -p "your prompt here"
```

Streaming JSON output, for a caller that parses turn-by-turn:

```bash
docker exec -i claude-code claude -p "your prompt" --output-format stream-json
```

## Auto-update

Verify it's actually off:

```bash
docker exec -it claude-code claude doctor
```

Look for `Auto-updates: disabled`.

## Updating the CLI version

No in-place auto-update by design. The Dockerfile installs `@latest` at
build time, so a plain rebuild picks up whatever is newest on npm:

```bash
docker compose build --no-cache
docker compose up -d
```

`--no-cache` matters — without it, Docker may reuse the cached
`npm install` layer instead of actually re-running it.

To pin an exact version instead of tracking `latest`, edit the Dockerfile:

```dockerfile
RUN npm install -g @anthropic-ai/claude-code@2.1.198
```

then rebuild with `--no-cache` as above.

## Verifying the pin/version survives a restart

```bash
docker exec -it claude-code claude --version
docker restart claude-code
docker exec -it claude-code claude --version
```

Both must match.

## MCP servers

```bash
docker exec -it claude-code claude mcp add my-server -- npx -y @modelcontextprotocol/server-filesystem /workspace
docker exec -it claude-code claude mcp list
```

Or drop a `.mcp.json` into a project directory under `/workspace`. Claude
Code picks it up automatically for that project.

## Plugins

```bash
docker exec -it claude-code claude plugin marketplace add <repo-or-url>
docker exec -it claude-code claude plugin install <plugin-name>@<marketplace-name>
```

## WebUI (browser terminal)

Open `http://<host>:7681/` in a browser. You land directly inside a live
`claude` session — same as running `docker exec -it claude-code claude`
yourself, just over HTTP/WebSocket instead of a local terminal. Login
persists the same way: once you run `claude login` in that session (or
any other), it's saved to the `claude-config` volume and every future
WebUI session (and every `docker exec`) picks it up.

It's read-write (`ttyd -W`), so you can type into it normally. It is
**not** a general-purpose shell — `ttyd` is configured to spawn `claude`
directly, not `bash`. If you need a real shell in the container, use
`docker exec -it claude-code bash`.

## cc-bridge

A small FastAPI server (source: [`cc-bridge/`](cc-bridge/)) on port
`8642`, for programmatic or chat-frontend access — not meant to be
opened in a browser. It calls `claude -p` as a local subprocess; there's
no separate service, no Redis, no database server, and no auth (it's a
single-user container — put it behind your own reverse proxy/auth if you
expose it beyond your LAN).

### API

**`POST /chat`**

```json
{ "message": "your message", "model": "claude-sonnet-4-6" }
```

Returns `{ "reply": "..." }`. Internally: prior turns are assembled into

```
Human: ...

Assistant: ...

Human: <your message>

Assistant:
```

and piped to `claude -p --model <model>` on stdin. The subprocess has a
120-second timeout. If it times out, the call fails (HTTP 504) but your
message is **not** written to history — the session is untouched, and
your next `/chat` call continues right where the last successful turn
left off. Only `DELETE /session` starts a fresh session.

**`DELETE /session`** — clears history. Next `/chat` call starts a new
conversation with no memory of anything before this call.

**`GET /health`** — `{ "status": "ok", "claude_path": "..." }` if
`claude` is found on `PATH`, otherwise HTTP 503.

### Storage backends

Set via `CC_BRIDGE_STORAGE` (env var), default `sqlite`. All three
persist under `/home/claude/.claude/cc-bridge/` — inside the same
`claude-config` volume that already persists your login, so history
survives restarts and recreates exactly like everything else:

| Value | File | Trade-off |
|---|---|---|
| `sqlite` (default) | `history.sqlite3` | Compact, scales best for long histories |
| `markdown` | `history.md` | Human-readable, easy to skim/edit by hand |
| `json` | `history.json` | Easiest to parse from other scripts |

Changing the backend requires a container recreate (it's read once at
process startup):

```bash
CC_BRIDGE_STORAGE=markdown docker compose up -d
```

### Authenticating cc-bridge's subprocess calls

`claude -p` needs *some* valid auth. Either:

- Log in once via the [WebUI](#webui-browser-terminal) (`claude login`)
  — persists in the `claude-config` volume, works for cc-bridge too, or
- Set `ANTHROPIC_API_KEY` as an env var on the container (see
  `docker-compose.yml` — it's declared but empty by default, so it's a
  no-op unless you set it in your shell/`.env` before `docker compose up`)

## Unraid template

An Unraid Docker template ships in [`unraid/claude-code-cli.xml`](unraid/claude-code-cli.xml).
This is **not** in Unraid's official Community Applications feed — it's
a self-hosted template you add via your own template repository:

1. Unraid → **Docker** tab → **Template repositories**
2. Add this raw URL:
   `https://raw.githubusercontent.com/nicandr0/claude-code-cli/main/unraid/claude-code-cli.xml`
3. Save. The container now appears when you click **Add Container** and
   browse templates, like any Community Applications entry.

The template declares:

- **AppData path** → `/home/claude/.claude` (default host suggestion:
  `/mnt/user/appdata/claude-code-cli/config`) — this is what makes login,
  MCP servers, and plugins survive a recreate/update. Don't delete this
  volume unless you want to lose your login.
- **Workspace path** → `/workspace` (default host suggestion:
  `/mnt/user/appdata/claude-code-cli/workspace`) — point this at a real
  share for actual project work instead of the appdata default.
- **WebUI port** → `7681` (ttyd)
- **cc-bridge port** → `8642`
- **CC_BRIDGE_STORAGE** variable → `sqlite` / `markdown` / `json`
- **ANTHROPIC_API_KEY** variable → optional, see above

Nothing in the template is hardcoded to a specific server — host paths
are Unraid-convention defaults (`/mnt/user/appdata/...`) that you can
override in the Unraid UI like any other template field, and the WebUI
field uses Unraid's own `[IP]:[PORT:7681]` placeholder so it resolves to
whichever host you install it on.

## Working with actual project files

`/workspace` is a named Docker volume (`workspace`) by default, not a
host bind mount — files placed there live inside Docker's storage, not on
your host filesystem. For real project work, replace the `workspace`
volume with a bind mount in `docker-compose.yml`:

```yaml
    volumes:
      - claude-config:/home/claude/.claude
      - /path/on/host/to/your/project:/workspace
```

Claude Code will ask for workspace trust the first time it touches a new
directory — confirm once per directory, that's expected behavior, not a
bug.

## What this image does not include

No dashboard, no message bus, no orchestration daemon, no custom
plugin-loading mechanism, no forced auto-update. The only two things
running besides the CLI itself are `ttyd` (a browser terminal launching
`claude` directly) and cc-bridge (a plain HTTP wrapper around `claude -p`
subprocess calls) — both documented above, both just calling Claude
Code's own commands, nothing wrapping or replacing them. A chat-platform
bridge (Telegram, Slack, etc.) is not baked in — cc-bridge is what such a
bridge would call, but writing that bridge itself is out of scope here.
