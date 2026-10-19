"""Minimal SQLite history — export log (TRAKK family pattern)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    base TEXT NOT NULL DEFAULT '',
    preset TEXT NOT NULL DEFAULT '',
    params_json TEXT NOT NULL DEFAULT '{}',
    files_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT ''
)
"""


class HistoryStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def log_export(self, base: str, preset: str, params: dict, files: list[str]) -> int:
        cur = self.conn.execute(
            "INSERT INTO exports (base, preset, params_json, files_json, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                base,
                preset,
                json.dumps(params or {}, ensure_ascii=False),
                json.dumps([str(f) for f in files], ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()
        # Prune: history never grows unbounded (cap 500).
        self.conn.execute(
            "DELETE FROM exports WHERE id NOT IN "
            "(SELECT id FROM exports ORDER BY id DESC LIMIT 500)"
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_exports(self, limit: int = 50) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM exports ORDER BY id DESC LIMIT ?", (int(limit),))
        return [dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
