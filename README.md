# claude-code-cli

Minimal Docker image for the official Anthropic Claude Code CLI. Native
MCP server support, native plugin marketplace, native skills, agents, and
sub-agents — all as shipped by Anthropic, unmodified. Verified end-to-end
(build, restart persistence, MCP round-trip, plugin install, skill
invocation, sub-agent spawn, container recreate) before being tagged
`validated` and pushed.

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
- `ENTRYPOINT ["sleep", "infinity"]` — the container does nothing on its
  own; you drive it via `docker exec`

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

No web dashboard, no chat-platform bridges, no message bus, no
orchestration daemon, no forced auto-update. Those are separate concerns,
layered on top by whatever you point at this container — not baked into
the image.
