FROM node:22-bookworm-slim

ENV DISABLE_AUTOUPDATER=1 \
    CLAUDE_CONFIG_DIR=/home/claude/.claude \
    NPM_CONFIG_PREFIX=/home/claude/.npm-global \
    PATH=/home/claude/.npm-global/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    ripgrep \
    procps \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash claude \
    && mkdir -p /workspace /home/claude/.claude /home/claude/.npm-global \
    && chown -R claude:claude /workspace /home/claude

USER claude
WORKDIR /workspace

RUN npm install -g @anthropic-ai/claude-code@latest

ENTRYPOINT ["sleep", "infinity"]
