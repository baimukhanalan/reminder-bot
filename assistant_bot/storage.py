from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import aiosqlite

from .time_utils import UTC, next_occurrence, utc_now


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  chat_id INTEGER NOT NULL,
  timezone TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL COLLATE NOCASE,
  description TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(user_id, name),
  FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  project_id INTEGER,
  fact_key TEXT NOT NULL COLLATE NOCASE,
  fact_value TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(user_id, project_id, fact_key),
  FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  project_id INTEGER,
  content TEXT NOT NULL,
  source_type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS conversation_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'text',
  created_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reminders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  chat_id INTEGER NOT NULL,
  project_id INTEGER,
  title TEXT NOT NULL,
  due_at_utc TEXT NOT NULL,
  recurrence TEXT NOT NULL DEFAULT 'none',
  reminder_kind TEXT NOT NULL DEFAULT 'notification',
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at TEXT NOT NULL,
  delivered_at TEXT,
  FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS reminders_due_idx
ON reminders(status, due_at_utc);

CREATE INDEX IF NOT EXISTS conversation_messages_user_idx
ON conversation_messages(user_id, id);
"""


class Storage:
    def __init__(self, path: Path):
        self.path = path

    @asynccontextmanager
    async def connect(self):
        db = await aiosqlite.connect(self.path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            await db.close()

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self.connect() as db:
            await db.executescript(SCHEMA)
            # A process may stop after claiming a reminder but before delivery.
            # Recover those rows on the next single-instance startup.
            await db.execute(
                "UPDATE reminders SET status='pending' WHERE status='processing'"
            )
            await db.commit()

    async def ensure_user(self, user_id: int, chat_id: int, tz: str) -> None:
        now = utc_now().isoformat()
        async with self.connect() as db:
            await db.execute(
                """INSERT INTO users(user_id, chat_id, timezone, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET chat_id=excluded.chat_id,
                updated_at=excluded.updated_at""",
                (user_id, chat_id, tz, now, now),
            )
            await db.commit()

    async def claim_or_check_owner(self, user_id: int) -> bool:
        """Atomically let the first user claim a bot without an explicit allow-list."""
        async with self.connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            row = await (await db.execute(
                "SELECT value FROM app_settings WHERE key='owner_user_id'"
            )).fetchone()
            if row is None:
                await db.execute(
                    "INSERT INTO app_settings(key, value) VALUES ('owner_user_id', ?)",
                    (str(user_id),),
                )
                allowed = True
            else:
                allowed = row["value"] == str(user_id)
            await db.commit()
        return allowed

    async def set_app_setting(self, key: str, value: str) -> None:
        async with self.connect() as db:
            await db.execute(
                """INSERT INTO app_settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (key, value),
            )
            await db.commit()

    async def get_app_setting(self, key: str) -> Optional[str]:
        async with self.connect() as db:
            row = await (await db.execute(
                "SELECT value FROM app_settings WHERE key=?", (key,)
            )).fetchone()
        return str(row["value"]) if row else None

    async def get_timezone(self, user_id: int, default: str) -> str:
        async with self.connect() as db:
            row = await (await db.execute(
                "SELECT timezone FROM users WHERE user_id=?", (user_id,)
            )).fetchone()
        return row["timezone"] if row else default

    async def set_timezone(self, user_id: int, timezone_name: str) -> None:
        async with self.connect() as db:
            await db.execute(
                "UPDATE users SET timezone=?, updated_at=? WHERE user_id=?",
                (timezone_name, utc_now().isoformat(), user_id),
            )
            await db.commit()

    async def get_or_create_project(
        self, user_id: int, name: Optional[str], description: str = ""
    ) -> Optional[int]:
        if not name or not name.strip():
            return None
        name = name.strip()[:100]
        now = utc_now().isoformat()
        async with self.connect() as db:
            await db.execute(
                """INSERT INTO projects(user_id, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, name) DO UPDATE SET
                  description=CASE WHEN excluded.description != '' THEN excluded.description ELSE projects.description END,
                  updated_at=excluded.updated_at""",
                (user_id, name, description[:500], now, now),
            )
            row = await (await db.execute(
                "SELECT id FROM projects WHERE user_id=? AND name=? COLLATE NOCASE",
                (user_id, name),
            )).fetchone()
            await db.commit()
        return int(row["id"])

    async def save_memory(
        self, user_id: int, project_id: Optional[int], key: str, value: str, confidence: float
    ) -> None:
        now = utc_now().isoformat()
        async with self.connect() as db:
            if project_id is None:
                row = await (await db.execute(
                    "SELECT id FROM memories WHERE user_id=? AND project_id IS NULL AND fact_key=? COLLATE NOCASE",
                    (user_id, key),
                )).fetchone()
                if row:
                    await db.execute(
                        "UPDATE memories SET fact_value=?, confidence=?, updated_at=? WHERE id=?",
                        (value, confidence, now, row["id"]),
                    )
                else:
                    await db.execute(
                        "INSERT INTO memories(user_id, project_id, fact_key, fact_value, confidence, created_at, updated_at) VALUES (?, NULL, ?, ?, ?, ?, ?)",
                        (user_id, key[:100], value[:1000], confidence, now, now),
                    )
            else:
                await db.execute(
                    """INSERT INTO memories(user_id, project_id, fact_key, fact_value, confidence, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, project_id, fact_key) DO UPDATE SET
                    fact_value=excluded.fact_value, confidence=excluded.confidence, updated_at=excluded.updated_at""",
                    (user_id, project_id, key[:100], value[:1000], confidence, now, now),
                )
            await db.commit()

    async def add_note(
        self, user_id: int, project_id: Optional[int], content: str, source_type: str
    ) -> None:
        async with self.connect() as db:
            await db.execute(
                "INSERT INTO notes(user_id, project_id, content, source_type, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, project_id, content[:4000], source_type, utc_now().isoformat()),
            )
            await db.commit()

    async def add_reminder(
        self, user_id: int, chat_id: int, project_id: Optional[int], title: str,
        due_at: datetime, recurrence: str, reminder_kind: str
    ) -> int:
        async with self.connect() as db:
            cursor = await db.execute(
                """INSERT INTO reminders(user_id, chat_id, project_id, title, due_at_utc,
                recurrence, reminder_kind, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, chat_id, project_id, title[:1000], due_at.astimezone(UTC).isoformat(),
                 recurrence, reminder_kind, utc_now().isoformat()),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def list_reminders(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        async with self.connect() as db:
            rows = await (await db.execute(
                """SELECT r.*, p.name project_name FROM reminders r
                LEFT JOIN projects p ON p.id=r.project_id
                WHERE r.user_id=? AND r.status='pending'
                ORDER BY r.due_at_utc LIMIT ?""",
                (user_id, limit),
            )).fetchall()
        return [dict(row) for row in rows]

    async def cancel_reminder(self, user_id: int, reminder_id: int) -> bool:
        async with self.connect() as db:
            cursor = await db.execute(
                "UPDATE reminders SET status='cancelled' WHERE id=? AND user_id=? AND status='pending'",
                (reminder_id, user_id),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def dashboard(self, user_id: int) -> Dict[str, Any]:
        """Return one bounded payload for the Mini App without request waterfalls."""
        async with self.connect() as db:
            user = await (await db.execute(
                "SELECT timezone FROM users WHERE user_id=?", (user_id,)
            )).fetchone()
            projects = await (await db.execute(
                """SELECT p.id, p.name, p.description, p.updated_at,
                COUNT(DISTINCT n.id) note_count, COUNT(DISTINCT r.id) reminder_count
                FROM projects p
                LEFT JOIN notes n ON n.project_id=p.id
                LEFT JOIN reminders r ON r.project_id=p.id AND r.status='pending'
                WHERE p.user_id=? GROUP BY p.id ORDER BY p.updated_at DESC LIMIT 50""",
                (user_id,),
            )).fetchall()
            notes = await (await db.execute(
                """SELECT n.id, n.content, n.source_type, n.created_at,
                n.project_id, p.name project_name FROM notes n
                LEFT JOIN projects p ON p.id=n.project_id WHERE n.user_id=?
                ORDER BY n.created_at DESC LIMIT 100""",
                (user_id,),
            )).fetchall()
            reminders = await (await db.execute(
                """SELECT r.id, r.title, r.due_at_utc, r.recurrence,
                r.reminder_kind, r.project_id, p.name project_name
                FROM reminders r LEFT JOIN projects p ON p.id=r.project_id
                WHERE r.user_id=? AND r.status='pending'
                ORDER BY r.due_at_utc LIMIT 100""",
                (user_id,),
            )).fetchall()
            memories = await (await db.execute(
                """SELECT m.id, m.fact_key, m.fact_value, m.confidence,
                m.project_id, m.updated_at, p.name project_name FROM memories m
                LEFT JOIN projects p ON p.id=m.project_id WHERE m.user_id=?
                ORDER BY m.updated_at DESC LIMIT 100""",
                (user_id,),
            )).fetchall()
        return {
            "timezone": user["timezone"] if user else "Asia/Almaty",
            "projects": [dict(row) for row in projects],
            "notes": [dict(row) for row in notes],
            "reminders": [dict(row) for row in reminders],
            "memories": [dict(row) for row in memories],
        }

    async def delete_note(self, user_id: int, note_id: int) -> bool:
        async with self.connect() as db:
            cursor = await db.execute(
                "DELETE FROM notes WHERE id=? AND user_id=?", (note_id, user_id)
            )
            await db.commit()
            return cursor.rowcount == 1

    async def delete_memory(self, user_id: int, memory_id: int) -> bool:
        async with self.connect() as db:
            cursor = await db.execute(
                "DELETE FROM memories WHERE id=? AND user_id=?", (memory_id, user_id)
            )
            await db.commit()
            return cursor.rowcount == 1

    async def delete_project(self, user_id: int, project_id: int) -> bool:
        async with self.connect() as db:
            cursor = await db.execute(
                "DELETE FROM projects WHERE id=? AND user_id=?", (project_id, user_id)
            )
            await db.commit()
            return cursor.rowcount == 1

    async def claim_due_reminders(self, limit: int = 20) -> List[Dict[str, Any]]:
        now = utc_now().isoformat()
        async with self.connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            rows = await (await db.execute(
                """SELECT r.*, p.name project_name, u.timezone user_timezone FROM reminders r
                LEFT JOIN projects p ON p.id=r.project_id
                JOIN users u ON u.user_id=r.user_id
                WHERE r.status='pending' AND r.due_at_utc<=?
                ORDER BY r.due_at_utc LIMIT ?""",
                (now, limit),
            )).fetchall()
            ids = [row["id"] for row in rows]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                await db.execute(
                    "UPDATE reminders SET status='processing' WHERE id IN (" + placeholders + ")",
                    ids,
                )
            await db.commit()
        return [dict(row) for row in rows]

    async def mark_delivered(self, reminder: Dict[str, Any]) -> None:
        due = datetime.fromisoformat(reminder["due_at_utc"])
        now = utc_now()
        recurrence = reminder["recurrence"]
        async with self.connect() as db:
            if recurrence == "none":
                await db.execute(
                    "UPDATE reminders SET status='delivered', delivered_at=? WHERE id=?",
                    (now.isoformat(), reminder["id"]),
                )
            else:
                local_due = due.astimezone(ZoneInfo(reminder["user_timezone"]))
                next_due = next_occurrence(local_due, recurrence).astimezone(UTC)
                while next_due <= now:
                    next_due = next_occurrence(
                        next_due.astimezone(ZoneInfo(reminder["user_timezone"])), recurrence
                    ).astimezone(UTC)
                await db.execute(
                    """UPDATE reminders SET status='pending', due_at_utc=?, delivered_at=?,
                    attempts=0, last_error=NULL WHERE id=?""",
                    (next_due.isoformat(), now.isoformat(), reminder["id"]),
                )
            await db.commit()

    async def mark_failed(self, reminder_id: int, error: str) -> None:
        retry_at = (utc_now() + timedelta(minutes=2)).isoformat()
        async with self.connect() as db:
            await db.execute(
                """UPDATE reminders SET status='pending', attempts=attempts+1,
                last_error=?, due_at_utc=? WHERE id=?""",
                (error[:500], retry_at, reminder_id),
            )
            await db.commit()

    async def context(self, user_id: int) -> Dict[str, List[Dict[str, Any]]]:
        async with self.connect() as db:
            projects = await (await db.execute(
                "SELECT id, name, description FROM projects WHERE user_id=? ORDER BY updated_at DESC LIMIT 30",
                (user_id,),
            )).fetchall()
            memories = await (await db.execute(
                """SELECT m.fact_key, m.fact_value, p.name project_name FROM memories m
                LEFT JOIN projects p ON p.id=m.project_id WHERE m.user_id=?
                ORDER BY m.updated_at DESC LIMIT 50""",
                (user_id,),
            )).fetchall()
            notes = await (await db.execute(
                """SELECT n.content, n.created_at, p.name project_name FROM notes n
                LEFT JOIN projects p ON p.id=n.project_id WHERE n.user_id=?
                ORDER BY n.created_at DESC LIMIT 30""",
                (user_id,),
            )).fetchall()
        conversation_history = await self.conversation_history(user_id)
        return {
            "projects": [dict(row) for row in projects],
            "memories": [dict(row) for row in memories],
            "notes": [dict(row) for row in notes],
            "conversation_history": conversation_history,
        }

    async def add_conversation_message(
        self, user_id: int, role: str, content: str, source_type: str = "text"
    ) -> int:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("conversation message cannot be empty")
        async with self.connect() as db:
            cursor = await db.execute(
                """INSERT INTO conversation_messages(
                user_id, role, content, source_type, created_at
                ) VALUES (?, ?, ?, ?, ?)""",
                (user_id, role, clean_content, source_type, utc_now().isoformat()),
            )
            await db.commit()
            return cursor.lastrowid

    async def conversation_history(
        self, user_id: int, limit: int = 80, max_chars: int = 16000
    ) -> List[Dict[str, Any]]:
        """Return a bounded recent window while retaining the full transcript in SQLite."""
        safe_limit = max(1, min(limit, 200))
        async with self.connect() as db:
            rows = await (await db.execute(
                """SELECT id, role, content, source_type, created_at
                FROM conversation_messages WHERE user_id=?
                ORDER BY id DESC LIMIT ?""",
                (user_id, safe_limit),
            )).fetchall()

        selected: List[Dict[str, Any]] = []
        used_chars = 0
        for row in rows:
            item = dict(row)
            content = item["content"]
            remaining = max_chars - used_chars
            if remaining <= 0:
                break
            if len(content) > remaining:
                content = content[:remaining]
                item["content"] = content
            selected.append(item)
            used_chars += len(content)
        selected.reverse()
        return selected

    async def project_report_data(self, user_id: int, project_name: Optional[str]) -> Dict[str, Any]:
        context = await self.context(user_id)
        reminders = await self.list_reminders(user_id, 50)
        if project_name:
            needle = project_name.casefold()
            context["notes"] = [x for x in context["notes"] if (x.get("project_name") or "").casefold() == needle]
            context["memories"] = [x for x in context["memories"] if (x.get("project_name") or "").casefold() == needle]
            reminders = [x for x in reminders if (x.get("project_name") or "").casefold() == needle]
        context["reminders"] = reminders
        context["requested_project"] = project_name
        return context

    async def delete_user_data(self, user_id: int) -> None:
        async with self.connect() as db:
            await db.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            await db.commit()
