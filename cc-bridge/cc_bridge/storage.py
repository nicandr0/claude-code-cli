import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

# Lives under CLAUDE_CONFIG_DIR (/home/claude/.claude) so it rides the same
# persistent volume as the CLI's own login/session state.
DEFAULT_DATA_DIR = "/home/claude/.claude/cc-bridge"


def _data_dir() -> Path:
    d = Path(os.environ.get("CC_BRIDGE_DATA_DIR", DEFAULT_DATA_DIR))
    d.mkdir(parents=True, exist_ok=True)
    return d


class Storage:
    def load_turns(self) -> List[Tuple[str, str]]:
        raise NotImplementedError

    def append_turn(self, human: str, assistant: str) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError


class SqliteStorage(Storage):
    def __init__(self):
        self.path = _data_dir() / "history.sqlite3"
        with self._conn() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    human TEXT NOT NULL,
                    assistant TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )

    def _conn(self):
        return sqlite3.connect(self.path)

    def load_turns(self):
        with self._conn() as c:
            rows = c.execute(
                "SELECT human, assistant FROM turns ORDER BY id ASC"
            ).fetchall()
        return [(h, a) for h, a in rows]

    def append_turn(self, human, assistant):
        with self._conn() as c:
            c.execute(
                "INSERT INTO turns (human, assistant, created_at) VALUES (?, ?, ?)",
                (human, assistant, datetime.now(timezone.utc).isoformat()),
            )

    def clear(self):
        with self._conn() as c:
            c.execute("DELETE FROM turns")


class MarkdownStorage(Storage):
    """One markdown file, turns separated by a horizontal rule."""

    _SEP = "\n---\n\n"

    def __init__(self):
        self.path = _data_dir() / "history.md"
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def load_turns(self):
        text = self.path.read_text(encoding="utf-8")
        if not text.strip():
            return []
        turns = []
        for block in text.split(self._SEP):
            block = block.strip("\n")
            if not block.strip():
                continue
            if "\n## Assistant\n" not in block:
                continue
            human_part, assistant_part = block.split("\n## Assistant\n", 1)
            human = human_part.replace("## Human\n", "", 1).strip()
            assistant = assistant_part.strip()
            turns.append((human, assistant))
        return turns

    def append_turn(self, human, assistant):
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"## Human\n{human}\n\n## Assistant\n{assistant}\n{self._SEP}")

    def clear(self):
        self.path.write_text("", encoding="utf-8")


class JsonStorage(Storage):
    def __init__(self):
        self.path = _data_dir() / "history.json"
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _read(self):
        raw = self.path.read_text(encoding="utf-8").strip()
        return json.loads(raw) if raw else []

    def load_turns(self):
        return [(t["human"], t["assistant"]) for t in self._read()]

    def append_turn(self, human, assistant):
        data = self._read()
        data.append(
            {
                "human": human,
                "assistant": assistant,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def clear(self):
        self.path.write_text("[]", encoding="utf-8")


_BACKENDS = {
    "sqlite": SqliteStorage,
    "markdown": MarkdownStorage,
    "json": JsonStorage,
}


def get_storage() -> Storage:
    backend = os.environ.get("CC_BRIDGE_STORAGE", "sqlite").lower()
    try:
        return _BACKENDS[backend]()
    except KeyError:
        raise ValueError(
            f"Unknown CC_BRIDGE_STORAGE={backend!r}, must be one of {sorted(_BACKENDS)}"
        )
