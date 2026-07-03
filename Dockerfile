FROM node:22-bookworm-slim

ENV DISABLE_AUTOUPDATER=1 \
    CLAUDE_CONFIG_DIR=/home/claude/.claude \
    NPM_CONFIG_PREFIX=/home/claude/.npm-global \
    PATH=/home/claude/.npm-global/bin:$PATH \
    CC_BRIDGE_STORAGE=sqlite \
    TTYD_PORT=7681 \
    CC_BRIDGE_PORT=8642

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    ripgrep \
    procps \
    python3 \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# ttyd: static prebuilt binary, pinned for a reproducible build
RUN curl -fsSL -o /usr/local/bin/ttyd \
    https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64 \
    && chmod +x /usr/local/bin/ttyd

RUN useradd -m -s /bin/bash claude \
    && mkdir -p /workspace /home/claude/.claude /home/claude/.npm-global \
    && chown -R claude:claude /workspace /home/claude

USER claude
WORKDIR /workspace

RUN npm install -g @anthropic-ai/claude-code@latest

RUN python3 -m venv /home/claude/.venvs/cc-bridge \
    && /home/claude/.venvs/cc-bridge/bin/pip install --no-cache-dir --upgrade pip

COPY --chown=claude:claude cc-bridge/requirements.txt /home/claude/cc-bridge-requirements.txt
RUN /home/claude/.venvs/cc-bridge/bin/pip install --no-cache-dir -r /home/claude/cc-bridge-requirements.txt

COPY --chown=claude:claude cc-bridge/cc_bridge /home/claude/cc-bridge/cc_bridge
COPY --chown=claude:claude docker/start.sh /home/claude/start.sh
RUN chmod +x /home/claude/start.sh

EXPOSE 7681 8642

ENTRYPOINT ["/home/claude/start.sh"]
