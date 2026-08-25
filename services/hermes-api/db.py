"""SQLite-first Hermes store (campaigns + knowledge nodes). Optional DATABASE_URL Postgres."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
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
                "pip install -r requirements.postgres.txt "
                "(optional extra; SQLite remains the default). "
                "Cost: $0 extra on existing VPS 187.77.98.177 vs advertised intro "
                "~$6.49/mo new Hostinger KVM 1 (paid upfront). Do not buy a KVM."
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
        """
        CREATE TABLE IF NOT EXISTS walking_scripts (
            id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            audience TEXT NOT NULL,
            script TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS walking_storyboards (
            id TEXT PRIMARY KEY,
            script_id TEXT NOT NULL,
            scenes TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS walking_thumbnails (
            id TEXT PRIMARY KEY,
            script_id TEXT NOT NULL,
            storyboard_id TEXT NOT NULL,
            thumbnail_url TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS knowledge_edges (
            src TEXT NOT NULL,
            dst TEXT NOT NULL,
            rel TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (src, dst, rel)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS debug_events (
            id TEXT PRIMARY KEY,
            ts REAL NOT NULL,
            kind TEXT NOT NULL,
            detail TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS kv_store (
            k TEXT PRIMARY KEY,
            v TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            campaign_id TEXT,
            stage TEXT,
            status TEXT NOT NULL,
            progress REAL NOT NULL,
            detail TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS opportunities (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            score INTEGER NOT NULL,
            source TEXT NOT NULL,
            rank INTEGER NOT NULL,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            number INTEGER NOT NULL,
            title TEXT NOT NULL,
            campaign_id TEXT,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS experiment_variants (
            id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            label TEXT NOT NULL,
            category TEXT NOT NULL,
            score INTEGER NOT NULL,
            state TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS metric_points (
            id TEXT PRIMARY KEY,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            run_index INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS learnings (
            id TEXT PRIMARY KEY,
            insight TEXT NOT NULL,
            lift REAL NOT NULL,
            category TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS pipeline_agents (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            agent_key TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            progress REAL NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (campaign_id, agent_key)
        )
        """,
    )


def _ensure_column(db: Any, table: str, column: str, decl: str) -> None:
    try:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    except Exception:
        pass


def init_schema(conn: Any | None = None) -> None:
    own = conn is None
    db = connect() if own else conn
    try:
        for stmt in _schema_sql():
            db.execute(stmt)
        _ensure_column(db, "knowledge_nodes", "mode", "TEXT")
        _ensure_column(db, "knowledge_nodes", "label", "TEXT")
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


def _mode_label(mode: str | None, label: str | None, trend: str) -> tuple[str, str]:
    if (trend or "").startswith("[DRY-RUN]"):
        inferred_mode, inferred_label = "dry_run", "DRY-RUN"
    else:
        inferred_mode, inferred_label = "live", "live"
    return (mode or inferred_mode), (label or inferred_label)


def upsert_knowledge_node(
    topic: str,
    trend: str,
    *,
    source: str = "research",
    mode: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    ensure_db()
    now = _now_iso()
    slug = (topic or "topic").strip() or "topic"
    node_id = slug.lower()[:80]
    mode, label = _mode_label(mode, label, trend)
    db = connect()
    try:
        existing = db.execute(
            "SELECT id, created_at FROM knowledge_nodes WHERE topic = ?",
            (slug,),
        ).fetchone()
        if existing:
            created = existing[1] if not hasattr(existing, "keys") else existing["created_at"]
            db.execute(
                """
                UPDATE knowledge_nodes
                SET trend = ?, source = ?, updated_at = ?, mode = ?, label = ?
                WHERE topic = ?
                """,
                (trend, source, now, mode, label, slug),
            )
            nid = existing[0] if not hasattr(existing, "keys") else existing["id"]
        else:
            created = now
            nid = node_id
            db.execute(
                """
                INSERT INTO knowledge_nodes
                    (id, topic, trend, source, created_at, updated_at, mode, label)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (nid, slug, trend, source, created, now, mode, label),
            )
        db.commit()
    finally:
        db.close()
    return {
        "id": nid,
        "topic": slug,
        "trend": trend,
        "source": source,
        "mode": mode,
        "label": label,
        "created_at": created,
        "updated_at": now,
    }


def _node_from_row(row: Any) -> dict[str, Any]:
    if hasattr(row, "keys"):
        item = {k: row[k] for k in row.keys()}
    else:
        item = {
            "id": row[0],
            "topic": row[1],
            "trend": row[2],
            "source": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }
        if len(row) > 6:
            item["mode"] = row[6]
            item["label"] = row[7]
    trend = str(item.get("trend") or "")
    mode, label = _mode_label(item.get("mode"), item.get("label"), trend)
    item["mode"] = mode
    item["label"] = label
    return item


def list_knowledge_nodes() -> list[dict[str, Any]]:
    ensure_db()
    db = connect()
    try:
        try:
            rows = db.execute(
                """
                SELECT id, topic, trend, source, created_at, updated_at, mode, label
                FROM knowledge_nodes ORDER BY updated_at DESC
                """
            ).fetchall()
        except Exception:
            rows = db.execute(
                "SELECT id, topic, trend, source, created_at, updated_at FROM knowledge_nodes ORDER BY updated_at DESC"
            ).fetchall()
    finally:
        db.close()
    return [_node_from_row(row) for row in rows]


def get_knowledge_node(topic: str) -> dict[str, Any] | None:
    ensure_db()
    slug = (topic or "").strip()
    if not slug:
        return None
    db = connect()
    try:
        row = db.execute(
            """
            SELECT id, topic, trend, source, created_at, updated_at, mode, label
            FROM knowledge_nodes WHERE topic = ? OR id = ?
            """,
            (slug, slug.lower()[:80]),
        ).fetchone()
    finally:
        db.close()
    return _node_from_row(row) if row is not None else None


def upsert_knowledge_edge(src: str, dst: str, rel: str = "researched_with") -> dict[str, Any] | None:
    ensure_db()
    a = (src or "").strip()
    b = (dst or "").strip()
    kind = (rel or "researched_with").strip() or "researched_with"
    if not a or not b or a == b:
        return None
    if a > b and kind == "researched_with":
        a, b = b, a
    now = _now_iso()
    db = connect()
    try:
        try:
            db.execute(
                """
                INSERT INTO knowledge_edges (src, dst, rel, created_at) VALUES (?, ?, ?, ?)
                ON CONFLICT(src, dst, rel) DO UPDATE SET created_at = excluded.created_at
                """,
                (a, b, kind, now),
            )
        except Exception:
            db.execute(
                "DELETE FROM knowledge_edges WHERE src = ? AND dst = ? AND rel = ?",
                (a, b, kind),
            )
            db.execute(
                "INSERT INTO knowledge_edges (src, dst, rel, created_at) VALUES (?, ?, ?, ?)",
                (a, b, kind, now),
            )
        db.commit()
    finally:
        db.close()
    return {"source": a, "target": b, "rel": kind, "created_at": now}


def list_knowledge_edges() -> list[dict[str, Any]]:
    ensure_db()
    db = connect()
    try:
        rows = db.execute(
            "SELECT src, dst, rel, created_at FROM knowledge_edges ORDER BY created_at DESC"
        ).fetchall()
    finally:
        db.close()
    links: list[dict[str, Any]] = []
    for row in rows:
        if hasattr(row, "keys"):
            links.append(
                {
                    "source": row["src"],
                    "target": row["dst"],
                    "rel": row["rel"],
                    "created_at": row["created_at"],
                }
            )
        else:
            links.append({"source": row[0], "target": row[1], "rel": row[2], "created_at": row[3]})
    return links


def knowledge_graph() -> dict[str, Any]:
    nodes = list_knowledge_nodes()
    links = list_knowledge_edges()
    ids = {str(n.get("id")) for n in nodes}
    topics = {str(n.get("topic")) for n in nodes}
    aliases = ids | topics | {value.lower() for value in ids | topics}
    filtered = [
        link
        for link in links
        if str(link["source"]) in aliases and str(link["target"]) in aliases
    ]
    return {"nodes": nodes, "links": filtered, "count": len(nodes)}


def kv_get(key: str) -> str | None:
    ensure_db()
    db = connect()
    try:
        row = db.execute("SELECT v FROM kv_store WHERE k = ?", (key,)).fetchone()
    finally:
        db.close()
    if row is None:
        return None
    return row[0] if not hasattr(row, "keys") else row["v"]


def kv_set(key: str, value: str) -> None:
    ensure_db()
    db = connect()
    try:
        db.execute(
            """
            INSERT INTO kv_store (k, v) VALUES (?, ?)
            ON CONFLICT(k) DO UPDATE SET v = excluded.v
            """,
            (key, value),
        )
        db.commit()
    finally:
        db.close()


def link_research_session(node_id: str) -> dict[str, Any] | None:
    last = kv_get("last_research_node_id")
    edge = None
    if last:
        edge = upsert_knowledge_edge(last, node_id, "researched_with")
    kv_set("last_research_node_id", node_id)
    return edge


def link_campaign_niche(niche: str) -> dict[str, Any] | None:
    slug = (niche or "").strip()
    if not slug:
        return None
    node = get_knowledge_node(slug)
    if node is None:
        node = upsert_knowledge_node(
            slug,
            f"Campaign niche: {slug}",
            source="campaign",
            mode="pending",
            label="pending",
        )
    last = kv_get("last_research_node_id")
    nid = str(node.get("id") or "")
    if last and last != nid:
        return upsert_knowledge_edge(last, nid, "campaign")
    return None


DEBUG_RING = 80


def append_debug_event(kind: str, detail: str | dict[str, Any]) -> dict[str, Any]:
    ensure_db()
    payload = json.dumps(detail) if isinstance(detail, dict) else str(detail)
    event = {
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": str(kind or "event"),
        "detail": payload,
    }
    db = connect()
    try:
        db.execute(
            "INSERT INTO debug_events (id, ts, kind, detail) VALUES (?, ?, ?, ?)",
            (event["id"], event["ts"], event["kind"], event["detail"]),
        )
        extra = db.execute(
            "SELECT id FROM debug_events ORDER BY ts DESC"
        ).fetchall()
        if extra and len(extra) > DEBUG_RING:
            for row in extra[DEBUG_RING:]:
                rid = row[0] if not hasattr(row, "keys") else row["id"]
                db.execute("DELETE FROM debug_events WHERE id = ?", (rid,))
        db.commit()
    finally:
        db.close()
    return event


def list_debug_events(limit: int = 50) -> list[dict[str, Any]]:
    ensure_db()
    cap = max(1, min(int(limit or 50), DEBUG_RING))
    db = connect()
    try:
        rows = db.execute(
            "SELECT id, ts, kind, detail FROM debug_events ORDER BY ts DESC LIMIT ?",
            (cap,),
        ).fetchall()
    finally:
        db.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        if hasattr(row, "keys"):
            item = {k: row[k] for k in row.keys()}
        else:
            item = {"id": row[0], "ts": row[1], "kind": row[2], "detail": row[3]}
        raw = item.get("detail")
        if isinstance(raw, str) and raw.startswith("{"):
            try:
                item["detail"] = json.loads(raw)
            except json.JSONDecodeError:
                pass
        out.append(item)
    return out


def upsert_walking_script(row: dict[str, Any]) -> dict[str, Any]:
    ensure_db()
    db = connect()
    try:
        db.execute(
            """
            INSERT INTO walking_scripts (id, topic, audience, script, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                topic = excluded.topic,
                audience = excluded.audience,
                script = excluded.script,
                created_at = excluded.created_at
            """,
            (
                str(row["id"]),
                str(row.get("topic") or ""),
                str(row.get("audience") or ""),
                str(row.get("script") or ""),
                str(row.get("created_at") or _now_iso()),
            ),
        )
        db.commit()
    finally:
        db.close()
    return row


def get_walking_script(script_id: str) -> dict[str, Any] | None:
    ensure_db()
    sid = str(script_id or "")
    if not sid:
        return None
    db = connect()
    try:
        row = db.execute(
            "SELECT id, topic, audience, script, created_at FROM walking_scripts WHERE id = ?",
            (sid,),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return {
        "id": row[0],
        "topic": row[1],
        "audience": row[2],
        "script": row[3],
        "created_at": row[4],
    }


def upsert_walking_storyboard(row: dict[str, Any]) -> dict[str, Any]:
    ensure_db()
    scenes = row.get("scenes")
    payload = json.dumps(scenes if isinstance(scenes, list) else [])
    db = connect()
    try:
        db.execute(
            """
            INSERT INTO walking_storyboards (id, script_id, scenes, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                script_id = excluded.script_id,
                scenes = excluded.scenes,
                created_at = excluded.created_at
            """,
            (
                str(row["id"]),
                str(row.get("script_id") or ""),
                payload,
                str(row.get("created_at") or _now_iso()),
            ),
        )
        db.commit()
    finally:
        db.close()
    return row


def get_walking_storyboard(storyboard_id: str) -> dict[str, Any] | None:
    ensure_db()
    sid = str(storyboard_id or "")
    if not sid:
        return None
    db = connect()
    try:
        row = db.execute(
            "SELECT id, script_id, scenes, created_at FROM walking_storyboards WHERE id = ?",
            (sid,),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        return None
    if hasattr(row, "keys"):
        item = {k: row[k] for k in row.keys()}
    else:
        item = {"id": row[0], "script_id": row[1], "scenes": row[2], "created_at": row[3]}
    raw = item.get("scenes")
    if isinstance(raw, str):
        try:
            item["scenes"] = json.loads(raw)
        except json.JSONDecodeError:
            item["scenes"] = []
    return item


def upsert_walking_thumbnail(row: dict[str, Any]) -> dict[str, Any]:
    ensure_db()
    db = connect()
    try:
        db.execute(
            """
            INSERT INTO walking_thumbnails (id, script_id, storyboard_id, thumbnail_url, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                script_id = excluded.script_id,
                storyboard_id = excluded.storyboard_id,
                thumbnail_url = excluded.thumbnail_url,
                created_at = excluded.created_at
            """,
            (
                str(row["id"]),
                str(row.get("script_id") or ""),
                str(row.get("storyboard_id") or ""),
                str(row.get("thumbnail_url") or ""),
                str(row.get("created_at") or _now_iso()),
            ),
        )
        db.commit()
    finally:
        db.close()
    return row


def get_walking_thumbnail(thumbnail_id: str) -> dict[str, Any] | None:
    ensure_db()
    tid = str(thumbnail_id or "")
    if not tid:
        return None
    db = connect()
    try:
        row = db.execute(
            """
            SELECT id, script_id, storyboard_id, thumbnail_url, created_at
            FROM walking_thumbnails WHERE id = ?
            """,
            (tid,),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return {
        "id": row[0],
        "script_id": row[1],
        "storyboard_id": row[2],
        "thumbnail_url": row[3],
        "created_at": row[4],
    }


def _as_dict(row: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return {keys[i]: row[i] for i in range(len(keys))}


def upsert_job(row: dict[str, Any]) -> dict[str, Any]:
    ensure_db()
    now = _now_iso()
    item = {
        "id": str(row.get("id") or uuid.uuid4()),
        "kind": str(row.get("kind") or "stage"),
        "campaign_id": row.get("campaign_id"),
        "stage": row.get("stage"),
        "status": str(row.get("status") or "queued"),
        "progress": float(row.get("progress") or 0),
        "detail": json.dumps(row.get("detail") if isinstance(row.get("detail"), (dict, list)) else (row.get("detail") or {})),
        "created_at": str(row.get("created_at") or now),
        "updated_at": now,
    }
    db = connect()
    try:
        db.execute(
            """
            INSERT INTO jobs (id, kind, campaign_id, stage, status, progress, detail, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                kind = excluded.kind,
                campaign_id = excluded.campaign_id,
                stage = excluded.stage,
                status = excluded.status,
                progress = excluded.progress,
                detail = excluded.detail,
                updated_at = excluded.updated_at
            """,
            (
                item["id"],
                item["kind"],
                item["campaign_id"],
                item["stage"],
                item["status"],
                item["progress"],
                item["detail"],
                item["created_at"],
                item["updated_at"],
            ),
        )
        db.commit()
    finally:
        db.close()
    return decode_job(item)


def decode_job(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("detail")
    if isinstance(raw, str):
        try:
            item["detail"] = json.loads(raw)
        except json.JSONDecodeError:
            pass
    return item


def list_jobs(*, campaign_id: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
    ensure_db()
    cap = max(1, min(int(limit or 80), 200))
    db = connect()
    try:
        if campaign_id:
            rows = db.execute(
                """
                SELECT id, kind, campaign_id, stage, status, progress, detail, created_at, updated_at
                FROM jobs WHERE campaign_id = ? ORDER BY updated_at DESC LIMIT ?
                """,
                (campaign_id, cap),
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT id, kind, campaign_id, stage, status, progress, detail, created_at, updated_at
                FROM jobs ORDER BY updated_at DESC LIMIT ?
                """,
                (cap,),
            ).fetchall()
    finally:
        db.close()
    keys = ("id", "kind", "campaign_id", "stage", "status", "progress", "detail", "created_at", "updated_at")
    return [decode_job(_as_dict(row, keys)) for row in rows]


def get_job(job_id: str) -> dict[str, Any] | None:
    ensure_db()
    db = connect()
    try:
        row = db.execute(
            """
            SELECT id, kind, campaign_id, stage, status, progress, detail, created_at, updated_at
            FROM jobs WHERE id = ?
            """,
            (str(job_id),),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        return None
    keys = ("id", "kind", "campaign_id", "stage", "status", "progress", "detail", "created_at", "updated_at")
    return decode_job(_as_dict(row, keys))


def upsert_opportunity(row: dict[str, Any]) -> dict[str, Any]:
    ensure_db()
    now = _now_iso()
    extra = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    item = {
        "id": str(row.get("id") or uuid.uuid4()),
        "title": str(row.get("title") or "Untitled"),
        "score": int(row.get("score") or 0),
        "source": str(row.get("source") or "Trends"),
        "rank": int(row.get("rank") or 0),
        "payload": json.dumps(extra),
        "updated_at": now,
    }
    db = connect()
    try:
        db.execute(
            """
            INSERT INTO opportunities (id, title, score, source, rank, payload, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                score = excluded.score,
                source = excluded.source,
                rank = excluded.rank,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (item["id"], item["title"], item["score"], item["source"], item["rank"], item["payload"], item["updated_at"]),
        )
        db.commit()
    finally:
        db.close()
    return list_opportunities_decoded([item])[0]


def list_opportunities_decoded(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in items:
        raw = item.get("payload")
        payload = {}
        if isinstance(raw, str):
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {}
        elif isinstance(raw, dict):
            payload = raw
        out.append({**item, "payload": payload})
    return out


def list_opportunities() -> list[dict[str, Any]]:
    ensure_db()
    db = connect()
    try:
        rows = db.execute(
            "SELECT id, title, score, source, rank, payload, updated_at FROM opportunities ORDER BY score DESC, rank ASC"
        ).fetchall()
    finally:
        db.close()
    keys = ("id", "title", "score", "source", "rank", "payload", "updated_at")
    return list_opportunities_decoded([_as_dict(row, keys) for row in rows])


def upsert_experiment(row: dict[str, Any]) -> dict[str, Any]:
    ensure_db()
    now = _now_iso()
    extra = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    item = {
        "id": str(row.get("id") or uuid.uuid4()),
        "number": int(row.get("number") or 1),
        "title": str(row.get("title") or "Experiment"),
        "campaign_id": row.get("campaign_id"),
        "payload": json.dumps(extra),
        "updated_at": now,
    }
    db = connect()
    try:
        db.execute(
            """
            INSERT INTO experiments (id, number, title, campaign_id, payload, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                number = excluded.number,
                title = excluded.title,
                campaign_id = excluded.campaign_id,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (item["id"], item["number"], item["title"], item["campaign_id"], item["payload"], item["updated_at"]),
        )
        db.commit()
    finally:
        db.close()
    return item


def upsert_experiment_variant(row: dict[str, Any]) -> dict[str, Any]:
    ensure_db()
    now = _now_iso()
    item = {
        "id": str(row.get("id") or uuid.uuid4()),
        "experiment_id": str(row.get("experiment_id") or ""),
        "label": str(row.get("label") or ""),
        "category": str(row.get("category") or "variant"),
        "score": int(row.get("score") or 0),
        "state": str(row.get("state") or "testing"),
        "updated_at": now,
    }
    db = connect()
    try:
        db.execute(
            """
            INSERT INTO experiment_variants (id, experiment_id, label, category, score, state, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                label = excluded.label,
                category = excluded.category,
                score = excluded.score,
                state = excluded.state,
                updated_at = excluded.updated_at
            """,
            (
                item["id"],
                item["experiment_id"],
                item["label"],
                item["category"],
                item["score"],
                item["state"],
                item["updated_at"],
            ),
        )
        db.commit()
    finally:
        db.close()
    return item


def get_experiment(experiment_id: str) -> dict[str, Any] | None:
    ensure_db()
    db = connect()
    try:
        row = db.execute(
            "SELECT id, number, title, campaign_id, payload, updated_at FROM experiments WHERE id = ?",
            (str(experiment_id),),
        ).fetchone()
        variants = db.execute(
            """
            SELECT id, experiment_id, label, category, score, state, updated_at
            FROM experiment_variants WHERE experiment_id = ? ORDER BY score DESC
            """,
            (str(experiment_id),),
        ).fetchall()
    finally:
        db.close()
    if row is None:
        return None
    exp_keys = ("id", "number", "title", "campaign_id", "payload", "updated_at")
    var_keys = ("id", "experiment_id", "label", "category", "score", "state", "updated_at")
    item = _as_dict(row, exp_keys)
    raw = item.get("payload")
    if isinstance(raw, str):
        try:
            item["payload"] = json.loads(raw)
        except json.JSONDecodeError:
            item["payload"] = {}
    item["variants"] = [_as_dict(v, var_keys) for v in variants]
    return item


def list_experiments() -> list[dict[str, Any]]:
    ensure_db()
    db = connect()
    try:
        rows = db.execute(
            "SELECT id FROM experiments ORDER BY number DESC, updated_at DESC"
        ).fetchall()
    finally:
        db.close()
    out = []
    for row in rows:
        eid = row[0] if not hasattr(row, "keys") else row["id"]
        item = get_experiment(str(eid))
        if item:
            out.append(item)
    return out


def set_variant_state(variant_id: str, state: str) -> dict[str, Any] | None:
    ensure_db()
    now = _now_iso()
    db = connect()
    try:
        db.execute(
            "UPDATE experiment_variants SET state = ?, updated_at = ? WHERE id = ?",
            (state, now, str(variant_id)),
        )
        db.commit()
        row = db.execute(
            """
            SELECT id, experiment_id, label, category, score, state, updated_at
            FROM experiment_variants WHERE id = ?
            """,
            (str(variant_id),),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        return None
    return _as_dict(row, ("id", "experiment_id", "label", "category", "score", "state", "updated_at"))


def append_metric_point(metric: str, value: float, run_index: int | None = None) -> dict[str, Any]:
    ensure_db()
    now = _now_iso()
    db = connect()
    try:
        if run_index is None:
            row = db.execute(
                "SELECT MAX(run_index) FROM metric_points WHERE metric = ?",
                (metric,),
            ).fetchone()
            last = row[0] if row is not None else None
            run_index = int(last or 0) + 1
        item = {
            "id": str(uuid.uuid4()),
            "metric": metric,
            "value": float(value),
            "run_index": int(run_index),
            "created_at": now,
        }
        db.execute(
            "INSERT INTO metric_points (id, metric, value, run_index, created_at) VALUES (?, ?, ?, ?, ?)",
            (item["id"], item["metric"], item["value"], item["run_index"], item["created_at"]),
        )
        db.commit()
    finally:
        db.close()
    return item


def list_metric_series(metric: str | None = None, limit: int = 24) -> list[dict[str, Any]]:
    ensure_db()
    cap = max(1, min(int(limit or 24), 100))
    db = connect()
    try:
        if metric:
            rows = db.execute(
                """
                SELECT id, metric, value, run_index, created_at
                FROM metric_points WHERE metric = ? ORDER BY run_index ASC LIMIT ?
                """,
                (metric, cap),
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT id, metric, value, run_index, created_at
                FROM metric_points ORDER BY metric, run_index ASC
                """
            ).fetchall()
    finally:
        db.close()
    keys = ("id", "metric", "value", "run_index", "created_at")
    return [_as_dict(row, keys) for row in rows]


def upsert_learning(row: dict[str, Any]) -> dict[str, Any]:
    ensure_db()
    now = _now_iso()
    item = {
        "id": str(row.get("id") or uuid.uuid4()),
        "insight": str(row.get("insight") or ""),
        "lift": float(row.get("lift") or 0),
        "category": str(row.get("category") or "memory"),
        "created_at": str(row.get("created_at") or now),
    }
    db = connect()
    try:
        db.execute(
            """
            INSERT INTO learnings (id, insight, lift, category, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET insight = excluded.insight, lift = excluded.lift, category = excluded.category
            """,
            (item["id"], item["insight"], item["lift"], item["category"], item["created_at"]),
        )
        db.commit()
    finally:
        db.close()
    return item


def list_learnings() -> list[dict[str, Any]]:
    ensure_db()
    db = connect()
    try:
        rows = db.execute(
            "SELECT id, insight, lift, category, created_at FROM learnings ORDER BY lift DESC"
        ).fetchall()
    finally:
        db.close()
    return [_as_dict(row, ("id", "insight", "lift", "category", "created_at")) for row in rows]


def upsert_pipeline_agent(row: dict[str, Any]) -> dict[str, Any]:
    ensure_db()
    now = _now_iso()
    item = {
        "id": str(row.get("id") or f"{row.get('campaign_id')}:{row.get('agent_key')}"),
        "campaign_id": str(row.get("campaign_id") or ""),
        "agent_key": str(row.get("agent_key") or ""),
        "status": str(row.get("status") or "queued"),
        "message": str(row.get("message") or ""),
        "progress": float(row.get("progress") or 0),
        "updated_at": now,
    }
    db = connect()
    try:
        db.execute(
            """
            INSERT INTO pipeline_agents (id, campaign_id, agent_key, status, message, progress, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                message = excluded.message,
                progress = excluded.progress,
                updated_at = excluded.updated_at
            """,
            (
                item["id"],
                item["campaign_id"],
                item["agent_key"],
                item["status"],
                item["message"],
                item["progress"],
                item["updated_at"],
            ),
        )
        db.commit()
    finally:
        db.close()
    return item


def list_pipeline_agents(campaign_id: str | None = None) -> list[dict[str, Any]]:
    ensure_db()
    db = connect()
    try:
        if campaign_id:
            rows = db.execute(
                """
                SELECT id, campaign_id, agent_key, status, message, progress, updated_at
                FROM pipeline_agents WHERE campaign_id = ? ORDER BY updated_at DESC
                """,
                (campaign_id,),
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT id, campaign_id, agent_key, status, message, progress, updated_at
                FROM pipeline_agents ORDER BY updated_at DESC LIMIT 80
                """
            ).fetchall()
    finally:
        db.close()
    keys = ("id", "campaign_id", "agent_key", "status", "message", "progress", "updated_at")
    return [_as_dict(row, keys) for row in rows]


def reset_migrate_flag() -> None:
    global _migrated
    _migrated = False
