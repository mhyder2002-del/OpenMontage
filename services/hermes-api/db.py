"""SQLite-first Hermes store (campaigns + knowledge nodes). Optional DATABASE_URL Postgres."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_HERE = Path(__file__).resolve().parent
_DEFAULT_SQLITE = _HERE / "data" / "hermes.db"
_lock = threading.RLock()
_migrated = False


def sqlite_path() -> Path:
    raw = (os.environ.get("HERMES_DB_PATH") or "").strip()
    return Path(raw) if raw else _DEFAULT_SQLITE


def database_url() -> str:
    return (os.environ.get("DATABASE_URL") or "").strip()


def backend_name() -> str:
    url = database_url()
    if url.startswith("postgres"):
        return "postgres"
    return "sqlite"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class _PgConn:
    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        cur = self._raw.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        return cur

    def commit(self) -> None:
        self._raw.commit()

    def close(self) -> None:
        self._raw.close()


def connect() -> Any:
    url = database_url()
    if url.startswith("postgres"):
        try:
            import psycopg  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "DATABASE_URL is set to Postgres but psycopg is not installed. "
                "Default remains local SQLite; do not purchase hosted Postgres for this scaffold."
            ) from exc
        parsed = urlparse(url)
        if not parsed.hostname:
            raise RuntimeError("DATABASE_URL is missing a host")
        return _PgConn(psycopg.connect(url))
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _schema_sql() -> tuple[str, ...]:
    return (
        """
        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS knowledge_nodes (
            id TEXT PRIMARY KEY,
            topic TEXT NOT NULL UNIQUE,
            trend TEXT NOT NULL,
            source TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
    )


def init_schema(conn: Any | None = None) -> None:
    own = conn is None
    db = connect() if own else conn
    try:
        for stmt in _schema_sql():
            db.execute(stmt)
        if hasattr(db, "commit"):
            db.commit()
    finally:
        if own:
            db.close()


def _campaign_json_path() -> Path:
    raw = (os.environ.get("HERMES_CAMPAIGN_STORE") or "").strip()
    if raw:
        return Path(raw)
    return _HERE / "data" / "campaigns.json"


def migrate_json_campaigns(conn: Any | None = None) -> int:
    path = _campaign_json_path()
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    campaigns = data.get("campaigns") if isinstance(data, dict) else None
    if not isinstance(campaigns, dict):
        return 0
    own = conn is None
    db = connect() if own else conn
    count = 0
    try:
        init_schema(db)
        for cid, item in campaigns.items():
            if not isinstance(item, dict):
                continue
            payload = json.dumps(item)
            updated = float(item.get("updated_at") or 0)
            existing = db.execute("SELECT id FROM campaigns WHERE id = ?", (str(cid),)).fetchone()
            if existing:
                continue
            db.execute(
                "INSERT INTO campaigns (id, payload, updated_at) VALUES (?, ?, ?)",
                (str(cid), payload, updated),
            )
            count += 1
        if hasattr(db, "commit"):
            db.commit()
    finally:
        if own:
            db.close()
    return count


def ensure_db() -> Path | str:
    global _migrated
    with _lock:
        init_schema()
        if not _migrated:
            migrate_json_campaigns()
            _migrated = True
    if backend_name() == "postgres":
        return database_url()
    return sqlite_path()


def upsert_campaign_row(campaign: dict[str, Any]) -> None:
    ensure_db()
    cid = str(campaign.get("id") or "")
    if not cid:
        return
    db = connect()
    try:
        db.execute(
            """
            INSERT INTO campaigns (id, payload, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
            """,
            (cid, json.dumps(campaign), float(campaign.get("updated_at") or 0)),
        )
        db.commit()
    finally:
        db.close()


def get_campaign_row(campaign_id: str) -> dict[str, Any] | None:
    ensure_db()
    cid = str(campaign_id or "")
    if not cid:
        return None
    db = connect()
    try:
        row = db.execute("SELECT payload FROM campaigns WHERE id = ?", (cid,)).fetchone()
    finally:
        db.close()
    if row is None:
        return None
    payload = row[0] if not hasattr(row, "keys") else row["payload"]
    try:
        item = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return item if isinstance(item, dict) else None


def list_campaign_rows() -> list[dict[str, Any]]:
    ensure_db()
    db = connect()
    try:
        rows = db.execute("SELECT payload FROM campaigns ORDER BY updated_at DESC").fetchall()
    finally:
        db.close()
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = row[0] if not hasattr(row, "keys") else row["payload"]
        try:
            item = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            items.append(item)
    return items


def upsert_knowledge_node(topic: str, trend: str, *, source: str = "research") -> dict[str, Any]:
    ensure_db()
    now = _now_iso()
    slug = (topic or "topic").strip() or "topic"
    node_id = slug.lower()[:80]
    db = connect()
    try:
        existing = db.execute(
            "SELECT id, created_at FROM knowledge_nodes WHERE topic = ?",
            (slug,),
        ).fetchone()
        if existing:
            created = existing[1] if not hasattr(existing, "keys") else existing["created_at"]
            db.execute(
                "UPDATE knowledge_nodes SET trend = ?, source = ?, updated_at = ? WHERE topic = ?",
                (trend, source, now, slug),
            )
            nid = existing[0] if not hasattr(existing, "keys") else existing["id"]
        else:
            created = now
            nid = node_id
            db.execute(
                """
                INSERT INTO knowledge_nodes (id, topic, trend, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (nid, slug, trend, source, created, now),
            )
        db.commit()
    finally:
        db.close()
    return {
        "id": nid,
        "topic": slug,
        "trend": trend,
        "source": source,
        "created_at": created,
        "updated_at": now,
    }


def list_knowledge_nodes() -> list[dict[str, Any]]:
    ensure_db()
    db = connect()
    try:
        rows = db.execute(
            "SELECT id, topic, trend, source, created_at, updated_at FROM knowledge_nodes ORDER BY updated_at DESC"
        ).fetchall()
    finally:
        db.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        if hasattr(row, "keys"):
            out.append({k: row[k] for k in row.keys()})
        else:
            out.append(
                {
                    "id": row[0],
                    "topic": row[1],
                    "trend": row[2],
                    "source": row[3],
                    "created_at": row[4],
                    "updated_at": row[5],
                }
            )
    return out


def reset_migrate_flag() -> None:
    global _migrated
    _migrated = False
