"""Small SQLite snapshot store for the single-instance lab."""
import json
import sqlite3
from pathlib import Path
from app.config import settings


def connect():
    path = Path(settings.state_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.execute('CREATE TABLE IF NOT EXISTS snapshots (kind TEXT, id TEXT, payload TEXT NOT NULL, PRIMARY KEY(kind, id))')
    return connection


def save(kind: str, key: str, value: dict) -> None:
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?)', (kind, key, json.dumps(value, ensure_ascii=False)))


def load(kind: str, key: str) -> dict | None:
    with connect() as db:
        row = db.execute('SELECT payload FROM snapshots WHERE kind=? AND id=?', (kind, key)).fetchone()
    return json.loads(row[0]) if row else None


def delete(kind: str, key: str | None = None) -> None:
    with connect() as db:
        if key is None:
            db.execute('DELETE FROM snapshots WHERE kind=?', (kind,))
        else:
            db.execute('DELETE FROM snapshots WHERE kind=? AND id=?', (kind, key))
