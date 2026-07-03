import os
import shutil
import subprocess

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .storage import get_storage

app = FastAPI(title="cc-bridge")

# Overridable for testing the timeout path without waiting 120s for real;
# production deployments should leave this at the default.
SUBPROCESS_TIMEOUT_SECONDS = int(os.environ.get("CC_BRIDGE_SUBPROCESS_TIMEOUT", "120"))

# One storage backend for the process lifetime; reads/writes hit disk on
# every call so history still survives a container restart.
storage = get_storage()


class ChatRequest(BaseModel):
    message: str
    model: str


class ChatResponse(BaseModel):
    reply: str


def build_prompt(turns, current_message: str) -> str:
    parts = [f"Human: {human}\n\nAssistant: {assistant}" for human, assistant in turns]
    parts.append(f"Human: {current_message}\n\nAssistant:")
    return "\n\n".join(parts)


@app.get("/health")
def health():
    claude_path = shutil.which("claude")
    if not claude_path:
        raise HTTPException(status_code=503, detail="claude not found on PATH")
    return {"status": "ok", "claude_path": claude_path}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    turns = storage.load_turns()
    prompt_text = build_prompt(turns, req.message)

    try:
        result = subprocess.run(
            ["claude", "-p", "--model", req.model],
            input=prompt_text,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        # The hung subprocess is aborted and the request fails, but the
        # session itself is untouched: req.message was never written to
        # history, so the next /chat call still continues from the last
        # successful turn. Only DELETE /session starts a new session.
        raise HTTPException(
            status_code=504,
            detail=f"claude subprocess timed out after {SUBPROCESS_TIMEOUT_SECONDS}s",
        )

    if result.returncode != 0:
        raise HTTPException(
            status_code=502,
            detail=f"claude exited {result.returncode}: {result.stderr.strip()[:2000]}",
        )

    reply = result.stdout.strip()
    storage.append_turn(req.message, reply)
    return ChatResponse(reply=reply)


@app.delete("/session")
def delete_session():
    storage.clear()
    return {"status": "cleared"}
