"""SQLite-backed state store for the OS1 orchestrator.

Owns:
- User profile (including voice preferences & tweaks)
- OS1 Memory Ledger (5 Paper categories + hard delete)
- Connector Policy Table (per-app access levels & spoken status)
- Activity log ("While you were away" + Cua / trigger events)
- 60-second undo queue
- Spatial Inbox cache (numbered email tiles with Jev keeper scores)
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

MEMORY_CATEGORIES = (
    "people",
    "places",
    "things_you_love",
    "things_that_hurt",
    "promises",
)

CONNECTOR_POLICIES = (
    "full_access",
    "ask_before_write",
    "read_only",
    "ask_every_time",
)

DEFAULT_PROFILE: dict[str, Any] = {
    "name": "",
    "onboarded": False,
    "voice_key": "voice_1_warm",
    "voice_speed": 0.96,
    "voice_temperature": 0.72,
    "voice_style_note": "",
    "dossier": {},
    "first_meeting_pending": False,
}

DEFAULT_CONNECTORS: list[dict[str, Any]] = [
    {"slug": "gmail", "label": "Mail", "policy": "ask_before_write", "connected": True, "account_label": "shivam@os1.local"},
    {"slug": "googlecalendar", "label": "Calendar", "policy": "full_access", "connected": True, "account_label": "Primary Calendar"},
    {"slug": "googledrive", "label": "Files", "policy": "read_only", "connected": True, "account_label": "Drive Storage"},
    {"slug": "spotify", "label": "Music", "policy": "full_access", "connected": True, "account_label": "Daily Mix"},
    {"slug": "slack", "label": "Messages", "policy": "ask_before_write", "connected": False, "account_label": ""},
    {"slug": "stripe", "label": "Payments", "policy": "ask_every_time", "connected": False, "account_label": ""},
]

SEED_INBOX_ITEMS: list[dict[str, Any]] = [
    {
        "id": "msg_1",
        "number": 1,
        "sender": "Mom",
        "subject": "Sunday dinner in North Beach?",
        "snippet": "Thinking of making that lemon pasta you love if you're free around six.",
        "received_at": "10m ago",
        "keeper_score": 0.96,
        "is_vip": 1,
        "category": "personal",
        "status": "active",
    },
    {
        "id": "msg_2",
        "number": 2,
        "sender": "Erin · Studio",
        "subject": "Final print proofs for the book",
        "snippet": "Attached the warm cream stock samples — let me know which paper feels right.",
        "received_at": "1h ago",
        "keeper_score": 0.88,
        "is_vip": 1,
        "category": "work",
        "status": "active",
    },
    {
        "id": "msg_3",
        "number": 3,
        "sender": "Golden Gate Ferry",
        "subject": "Weekend timetable update",
        "snippet": "10:30 AM and 1:45 PM sailings confirmed from Ferry Building Gate B.",
        "received_at": "2h ago",
        "keeper_score": 0.68,
        "is_vip": 0,
        "category": "travel",
        "status": "active",
    },
    {
        "id": "msg_4",
        "number": 4,
        "sender": "Daily Tech Digest",
        "subject": "47 things you missed this week — unsubscribe",
        "snippet": "Sponsored roundup and flash sale ending tonight.",
        "received_at": "3h ago",
        "keeper_score": 0.12,
        "is_vip": 0,
        "category": "newsletter",
        "status": "active",
    },
    {
        "id": "msg_5",
        "number": 5,
        "sender": "Cloud Computing Weekly",
        "subject": "Serverless GPU benchmarks & deals",
        "snippet": "Special offer on cloud instances expiring in 48 hours.",
        "received_at": "4h ago",
        "keeper_score": 0.18,
        "is_vip": 0,
        "category": "newsletter",
        "status": "active",
    },
]

SEED_MEMORIES: list[dict[str, Any]] = [
    {
        "id": "mem_1",
        "category": "places",
        "summary": "Watches the fog roll over Ocean Beach when thinking through big decisions.",
        "detail": "Prefers late afternoon with hot coffee.",
        "source": "voice",
        "created_at": 1732300000.0,
    },
    {
        "id": "mem_2",
        "category": "people",
        "summary": "Mom makes lemon pasta on Sunday nights in North Beach.",
        "detail": "Always mark her emails VIP.",
        "source": "onboarding",
        "created_at": 1732200000.0,
    },
    {
        "id": "mem_3",
        "category": "promises",
        "summary": "Finish sending Erin feedback on the book proofs before Friday.",
        "detail": "Warm cream stock samples are ready for review.",
        "source": "voice",
        "created_at": 1732310000.0,
    },
    {
        "id": "mem_4",
        "category": "things_you_love",
        "summary": "Warm morning coffee, quiet ferry crossings to Sausalito, and analog field recorders.",
        "detail": "Fond of tactile hardware like Sony TC-D5.",
        "source": "voice",
        "created_at": 1732250000.0,
    },
    {
        "id": "mem_5",
        "category": "things_that_hurt",
        "summary": "Rushed deadlines and crowded subway commutes during morning peak hours.",
        "detail": "Prefers focused, deep work blocks.",
        "source": "voice",
        "created_at": 1732150000.0,
    },
]

SEED_ACTIVITY: list[dict[str, Any]] = [
    {
        "id": "act_h1",
        "source": "her_computer",
        "title": "Sorted 34 newsletters",
        "detail": "Kept 3 essays you usually read, filtered 4 promotional roundups",
        "status": "done",
        "created_at": 1732310100.0,
    },
    {
        "id": "act_h2",
        "source": "her_computer",
        "title": "Checked Sausalito ferry times",
        "detail": "Found 10:30 AM and 1:45 PM openings from Gate B",
        "status": "done",
        "created_at": 1732310400.0,
    },
    {
        "id": "act_h3",
        "source": "her_computer",
        "title": "Evaluated local Gemma 4 E2B IT",
        "detail": "On-device LiteRT execution verified on Apple Silicon Metal backend",
        "status": "done",
        "created_at": 1732310600.0,
    },
    {
        "id": "act_h4",
        "source": "her_computer",
        "title": "Drafted book proof review notes",
        "detail": "Outlined typography and paper weight feedback for Erin",
        "status": "done",
        "created_at": 1732310800.0,
    },
    {
        "id": "act_y1",
        "source": "your_computer",
        "title": "Opened Notes · Book Proofs",
        "detail": "Read-only lookup in ~/Documents/Book",
        "status": "done",
        "created_at": 1732310200.0,
    },
    {
        "id": "act_y2",
        "source": "your_computer",
        "title": "Checked Calendar for Saturday",
        "detail": "Verified morning opening for Sausalito excursion",
        "status": "done",
        "created_at": 1732310500.0,
    },
]

SPOKEN_POLICY = {
    "full_access": "full access",
    "ask_before_write": "asks before sending",
    "read_only": "read only",
    "ask_every_time": "asks every time",
}

SEED_RUNS: list[dict[str, Any]] = [
    {
        "id": "run_101",
        "label": "Clean up inbox newsletters",
        "status": "running",
        "progress": 45,
        "stage": "Filtering promotional newsletters & preserving VIP threads...",
        "result": "",
        "logs": [
            "Connected to spatial inbox and checked Apple Mail unread status.",
            "Scanning message headers for keeper scores under 0.20.",
            "Found Daily Tech Digest (score 0.12) ready for archive.",
            "Preserving Mom (0.96 VIP) and Erin (0.88 VIP) messages.",
        ],
        "created_at": 1732310200.0,
        "updated_at": 1732310300.0,
    },
    {
        "id": "run_102",
        "label": "Compare ferries to Sausalito",
        "status": "running",
        "progress": 70,
        "stage": "Cross-referencing Ferry Building departures with bay tides...",
        "result": "",
        "logs": [
            "Consulting Golden Gate Ferry schedule from Gate B.",
            "Identified 10:30 AM sailing (calm morning, quiet crossing).",
            "Identified 1:45 PM sailing (golden light on return crossing).",
            "Checking wind speed and tide forecasts across the Bay.",
        ],
        "created_at": 1732310100.0,
        "updated_at": 1732310250.0,
    },
    {
        "id": "run_103",
        "label": "Check SF weather & bay tide",
        "status": "done",
        "progress": 100,
        "stage": "Completed",
        "result": "San Francisco Bay: 64°F, gentle breeze 9 mph NW. Tides: High tide 5.2 ft at 11:20 AM, Low tide 1.1 ft at 5:45 PM. Clear visibility across the Golden Gate.",
        "logs": [
            "Queried coastal weather station for San Francisco and Marin.",
            "Temperature: 64°F with sunny skies.",
            "Tide timetable retrieved: High 5.2 ft at 11:20 AM, Low 1.1 ft at 5:45 PM.",
            "Report synthesized for Samantha.",
        ],
        "created_at": 1732309800.0,
        "updated_at": 1732310100.0,
    },
]


def spoken_connector_status(label: str, policy: str, connected: bool) -> str:
    if not connected:
        return f"{label} · not connected"
    return f"{label} · {SPOKEN_POLICY.get(policy, policy)}"


class Os1Store:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "os1.db"
        self.profile_path = self.state_dir / "profile.json"
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'voice',
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS connectors (
                    slug TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    policy TEXT NOT NULL,
                    connected INTEGER NOT NULL DEFAULT 0,
                    account_label TEXT NOT NULL DEFAULT '',
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activity_log (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'done',
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS undo_queue (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    undone INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS inbox_items (
                    id TEXT PRIMARY KEY,
                    number INTEGER NOT NULL,
                    sender TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    snippet TEXT NOT NULL DEFAULT '',
                    received_at TEXT NOT NULL DEFAULT '',
                    keeper_score REAL NOT NULL DEFAULT 0.5,
                    is_vip INTEGER NOT NULL DEFAULT 0,
                    category TEXT NOT NULL DEFAULT 'personal',
                    status TEXT NOT NULL DEFAULT 'active'
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    stage TEXT DEFAULT '',
                    result TEXT DEFAULT '',
                    logs_json TEXT DEFAULT '[]',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
            now = time.time()
            for item in DEFAULT_CONNECTORS:
                conn.execute(
                    """
                    INSERT INTO connectors (slug, label, policy, connected, account_label, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(slug) DO UPDATE SET
                        label = excluded.label,
                        policy = excluded.policy,
                        connected = excluded.connected,
                        account_label = excluded.account_label,
                        updated_at = excluded.updated_at
                    """,
                    (
                        item["slug"],
                        item["label"],
                        item["policy"],
                        1 if item["connected"] else 0,
                        item["account_label"],
                        now,
                    ),
                )

            # Seed inbox if empty
            inbox_count = conn.execute("SELECT count(*) FROM inbox_items").fetchone()[0]
            if inbox_count == 0:
                for item in SEED_INBOX_ITEMS:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO inbox_items (id, number, sender, subject, snippet, received_at, keeper_score, is_vip, category, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item["id"],
                            item["number"],
                            item["sender"],
                            item["subject"],
                            item["snippet"],
                            item["received_at"],
                            item["keeper_score"],
                            item["is_vip"],
                            item["category"],
                            item["status"],
                        ),
                    )

            # Seed memories if empty (except during unit tests)
            mem_count = conn.execute("SELECT count(*) FROM memories").fetchone()[0]
            if mem_count == 0 and not os.environ.get("PYTEST_CURRENT_TEST"):
                for mem in SEED_MEMORIES:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO memories (id, category, summary, detail, source, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            mem["id"],
                            mem["category"],
                            mem["summary"],
                            mem["detail"],
                            mem["source"],
                            mem["created_at"],
                        ),
                    )

            # Seed activity log if empty
            act_count = conn.execute("SELECT count(*) FROM activity_log").fetchone()[0]
            if act_count == 0:
                for act in SEED_ACTIVITY:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO activity_log (id, source, title, detail, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            act["id"],
                            act["source"],
                            act["title"],
                            act["detail"],
                            act["status"],
                            act["created_at"],
                        ),
                    )

            # Seed runs if empty
            run_count = conn.execute("SELECT count(*) FROM runs").fetchone()[0]
            if run_count == 0:
                for r in SEED_RUNS:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO runs (id, label, status, progress, stage, result, logs_json, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            r["id"],
                            r["label"],
                            r["status"],
                            r.get("progress", 0),
                            r.get("stage", ""),
                            r.get("result", ""),
                            json.dumps(r.get("logs", [])),
                            r["created_at"],
                            r["updated_at"],
                        ),
                    )

    # ----------------------------------------------------------------- profile

    def read_profile(self) -> dict[str, Any]:
        if self.profile_path.exists():
            try:
                return {**DEFAULT_PROFILE, **json.loads(self.profile_path.read_text())}
            except json.JSONDecodeError:
                pass
        return dict(DEFAULT_PROFILE)

    def write_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        merged = {**DEFAULT_PROFILE, **profile}
        self.profile_path.write_text(json.dumps(merged, indent=2))
        return merged

    def patch_profile(self, fields: dict[str, Any]) -> dict[str, Any]:
        return self.write_profile({**self.read_profile(), **fields})

    # ---------------------------------------------------------------- memories

    def add_memory(
        self,
        *,
        category: str,
        summary: str,
        detail: str = "",
        source: str = "voice",
    ) -> dict[str, Any]:
        cat = category if category in MEMORY_CATEGORIES else "things_you_love"
        mem = {
            "id": f"mem_{uuid.uuid4().hex[:10]}",
            "category": cat,
            "summary": summary.strip(),
            "detail": detail.strip(),
            "source": source,
            "created_at": time.time(),
        }
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO memories (id, category, summary, detail, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (mem["id"], mem["category"], mem["summary"], mem["detail"], mem["source"], mem["created_at"]),
            )
        return mem

    def list_memories(self, category: str | None = None, query: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
        sql = "SELECT * FROM memories WHERE 1=1"
        params: list[Any] = []
        if category and category in MEMORY_CATEGORIES:
            sql += " AND category = ?"
            params.append(category)
        if query:
            q = f"%{query.strip().lower()}%"
            sql += " AND (LOWER(summary) LIKE ? OR LOWER(detail) LIKE ?)"
            params.extend([q, q])
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def memory_shortlist(self, limit: int = 12) -> list[str]:
        rows = self.list_memories(limit=limit)
        return [f"[{r['category'].replace('_', ' ')}] {r['summary']}" for r in rows]

    def forget_memory(self, memory_id: str | None = None, query: str | None = None) -> list[dict[str, Any]]:
        """Hard-delete by exact id or substring match; returns deleted rows so Hermes can purge too."""
        with self._conn() as conn:
            if memory_id:
                rows = [dict(r) for r in conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchall()]
                if rows:
                    conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                return rows
            if query and query.strip():
                q = f"%{query.strip().lower()}%"
                rows = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT * FROM memories WHERE LOWER(summary) LIKE ? OR LOWER(detail) LIKE ?", (q, q)
                    ).fetchall()
                ]
                if rows:
                    conn.execute(
                        "DELETE FROM memories WHERE LOWER(summary) LIKE ? OR LOWER(detail) LIKE ?", (q, q)
                    )
                return rows
        return []

    # -------------------------------------------------------------- connectors

    def list_connectors(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = [dict(r) for r in conn.execute("SELECT * FROM connectors ORDER BY rowid ASC").fetchall()]
        for r in rows:
            r["connected"] = bool(r["connected"])
            r["spoken_status"] = spoken_connector_status(r["label"], r["policy"], r["connected"])
        return rows

    def get_connector(self, slug: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM connectors WHERE slug = ?", (slug.lower(),)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["connected"] = bool(d["connected"])
        d["spoken_status"] = spoken_connector_status(d["label"], d["policy"], d["connected"])
        return d

    def upsert_connector(
        self,
        slug: str,
        *,
        policy: str | None = None,
        connected: bool | None = None,
        account_label: str | None = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        slug_norm = slug.lower().strip()
        existing = self.get_connector(slug_norm)
        now = time.time()
        new_label = label or (existing["label"] if existing else slug_norm.title())
        new_policy = policy if policy in CONNECTOR_POLICIES else (existing["policy"] if existing else "ask_before_write")
        new_connected = connected if connected is not None else (existing["connected"] if existing else False)
        new_account = account_label if account_label is not None else (existing["account_label"] if existing else "")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO connectors (slug, label, policy, connected, account_label, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    label = excluded.label,
                    policy = excluded.policy,
                    connected = excluded.connected,
                    account_label = excluded.account_label,
                    updated_at = excluded.updated_at
                """,
                (slug_norm, new_label, new_policy, 1 if new_connected else 0, new_account, now),
            )
        return self.get_connector(slug_norm) or {}

    # ------------------------------------------------------------ activity log

    def add_activity(self, *, source: str, title: str, detail: str = "", status: str = "done") -> dict[str, Any]:
        item = {
            "id": f"act_{uuid.uuid4().hex[:10]}",
            "source": source,
            "title": title.strip(),
            "detail": detail.strip(),
            "status": status,
            "created_at": time.time(),
        }
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO activity_log (id, source, title, detail, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (item["id"], item["source"], item["title"], item["detail"], item["status"], item["created_at"]),
            )
        return item

    def list_activity(self, source: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
        sql = "SELECT * FROM activity_log"
        params: list[Any] = []
        if source:
            sql += " WHERE source = ?"
            params.append(source)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    # -------------------------------------------------------------- undo queue

    def push_undo(self, *, label: str, action_type: str, payload: dict[str, Any], ttl_s: float = 60.0) -> dict[str, Any]:
        now = time.time()
        entry = {
            "id": f"undo_{uuid.uuid4().hex[:10]}",
            "label": label,
            "action_type": action_type,
            "payload": payload,
            "created_at": now,
            "expires_at": now + ttl_s,
            "undone": False,
        }
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO undo_queue (id, label, action_type, payload_json, created_at, expires_at, undone)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (entry["id"], label, action_type, json.dumps(payload), now, entry["expires_at"]),
            )
        return entry

    def latest_undo(self) -> dict[str, Any] | None:
        now = time.time()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM undo_queue WHERE undone = 0 AND expires_at > ? ORDER BY created_at DESC LIMIT 1",
                (now,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["payload"] = json.loads(d.pop("payload_json"))
        d["undone"] = bool(d["undone"])
        return d

    def consume_undo(self, undo_id: str | None = None) -> dict[str, Any] | None:
        now = time.time()
        with self._conn() as conn:
            if undo_id:
                row = conn.execute(
                    "SELECT * FROM undo_queue WHERE id = ? AND undone = 0 AND expires_at > ?",
                    (undo_id, now),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM undo_queue WHERE undone = 0 AND expires_at > ? ORDER BY created_at DESC LIMIT 1",
                    (now,),
                ).fetchone()
            if not row:
                return None
            conn.execute("UPDATE undo_queue SET undone = 1 WHERE id = ?", (row["id"],))
        d = dict(row)
        d["payload"] = json.loads(d.pop("payload_json"))
        d["undone"] = True
        return d

    # ----------------------------------------------------------- spatial inbox

    def set_inbox_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self._conn() as conn:
            conn.execute("DELETE FROM inbox_items")
            for idx, item in enumerate(items, start=1):
                conn.execute(
                    """
                    INSERT INTO inbox_items (id, number, sender, subject, snippet, received_at, keeper_score, is_vip, category, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(item.get("id") or f"msg_{idx}"),
                        int(item.get("number") or idx),
                        str(item.get("sender") or ""),
                        str(item.get("subject") or ""),
                        str(item.get("snippet") or ""),
                        str(item.get("received_at") or ""),
                        float(item.get("keeper_score", 0.5)),
                        1 if item.get("is_vip") else 0,
                        str(item.get("category") or "personal"),
                        str(item.get("status") or "active"),
                    ),
                )
        return self.list_inbox()

    def list_inbox(self, include_cleared: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM inbox_items"
        if not include_cleared:
            sql += " WHERE status = 'active'"
        sql += " ORDER BY number ASC"
        with self._conn() as conn:
            rows = [dict(r) for r in conn.execute(sql).fetchall()]
        for r in rows:
            r["is_vip"] = bool(r["is_vip"])
        return rows

    def update_inbox_status(self, numbers: list[int], status: str) -> list[dict[str, Any]]:
        if not numbers:
            return []
        placeholders = ",".join("?" for _ in numbers)
        with self._conn() as conn:
            rows = [
                dict(r)
                for r in conn.execute(
                    f"SELECT * FROM inbox_items WHERE number IN ({placeholders})", numbers
                ).fetchall()
            ]
            conn.execute(f"UPDATE inbox_items SET status = ? WHERE number IN ({placeholders})", [status, *numbers])
        return rows

    # ----------------------------------------------------------- swarm runs

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM runs
                ORDER BY
                    CASE WHEN status IN ('running', 'waiting') THEN 0 ELSE 1 END,
                    created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["logs"] = json.loads(d.pop("logs_json") or "[]")
            except Exception:
                d["logs"] = []
            result.append(d)
        return result

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["logs"] = json.loads(d.pop("logs_json") or "[]")
        except Exception:
            d["logs"] = []
        return d

    def save_run(self, run: dict[str, Any]) -> dict[str, Any]:
        logs = run.get("logs", [])
        logs_json = json.dumps(logs) if isinstance(logs, list) else str(logs)
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO runs (id, label, status, progress, stage, result, logs_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    label = excluded.label,
                    status = excluded.status,
                    progress = excluded.progress,
                    stage = excluded.stage,
                    result = excluded.result,
                    logs_json = excluded.logs_json,
                    updated_at = excluded.updated_at
                """,
                (
                    run["id"],
                    run["label"],
                    run.get("status", "running"),
                    int(run.get("progress", 0)),
                    str(run.get("stage", "")),
                    str(run.get("result", "")),
                    logs_json,
                    float(run.get("created_at", now)),
                    now,
                ),
            )
        return self.get_run(run["id"]) or run

    def delete_run(self, run_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            return cur.rowcount > 0

    def clear_done_runs(self) -> int:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM runs WHERE status IN ('done', 'cancelled', 'failed')")
            return cur.rowcount
