# claude-code-cli

Minimal Docker image for the official Anthropic Claude Code CLI. Native
MCP server support, native plugin marketplace, native skills, agents, and
sub-agents — all as shipped by Anthropic, unmodified.

## Installation method

Uses `npm install -g @anthropic-ai/claude-code`. 
Anthropic's currently
recommended install method is `curl -fsSL https://claude.ai/install.sh | bash`,
but that script returns HTTP 403 when run from Docker builds or CI
(Cloudflare blocks non-browser automated requests — see
[anthropics/claude-code#36306](https://github.com/anthropics/claude-code/issues/36306)).
npm is marked deprecated in upstream docs but remains published and
functional, and is the reliable option for unattended builds until that
issue is resolved. Revisit this Dockerfile if/when it closes.

## Build

```bash
docker compose build
```

Version is set via build arg in `docker-compose.yml`
(`CLAUDE_CODE_VERSION`). Defaults to `latest`; set an explicit version
(e.g. `2.1.198`) for reproducible builds.

## Start

```bash
docker compose up -d
```

The container runs `tail -f /dev/null` and does nothing else on its own —
you drive it via `docker exec`.

## First-time login

```bash
docker exec -it claude-code claude login
```

Credentials are written to `/data` (the named volume `claude-code-data`),
set via `CLAUDE_CONFIG_DIR`. This survives `docker restart`, `docker
compose down && up`, and image rebuilds, as long as the volume itself
isn't removed.

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

`DISABLE_AUTOUPDATER=1` is set as a Dockerfile `ENV`, so it applies to
every `docker exec` shell, not just the entrypoint process. Verify:

```bash
docker exec -it claude-code claude doctor
```

Look for `Auto-updates: disabled`.

## Updating the CLI version

There is no in-place auto-update by design. To move to a newer CLI
version: bump `CLAUDE_CODE_VERSION` in `docker-compose.yml`, then

```bash
docker compose build --no-cache
docker compose up -d
```

`--no-cache` matters here — without it, Docker may reuse a cached layer
from the old version's `npm install` step instead of actually fetching
the new one.

## Verifying the pin survives a restart

```bash
docker exec -it claude-code claude --version
docker restart claude-code
docker exec -it claude-code claude --version
```

Both must match. If they don't, something outside the image is shadowing
the binary — check `which -a claude` inside the container and make sure
nothing under the mounted volume (`/data`) has its own copy of the CLI
earlier in `PATH`.

## MCP servers

```bash
docker exec -it claude-code claude mcp add my-server -- npx -y @modelcontextprotocol/server-filesystem /workspace
docker exec -it claude-code claude mcp list
```

Or drop a `.mcp.json` into a project directory. Claude Code picks it up
automatically for that project.

## Plugins

```bash
docker exec -it claude-code claude plugin marketplace add <repo-or-url>
docker exec -it claude-code claude plugin install <plugin-name>@<marketplace-name>
```

## Adding project directories

Add bind mounts under `/workspace` (or wherever) in `docker-compose.yml`.
Claude Code will ask for workspace trust the first time it touches a new
directory — confirm once per directory, that's expected behavior, not a
bug.

## What this image does not include

No web dashboard, no chat-platform bridges, no message bus, no
orchestration daemon, no forced auto-update. Those are separate concerns,
layered on top by whatever you point at this container — not baked into
the image.
