import os
import logging
import aiosqlite
import config

log = logging.getLogger(__name__)
_conn: aiosqlite.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    tg_id       INTEGER PRIMARY KEY,
    timezone    TEXT NOT NULL DEFAULT 'Europe/Moscow',
    digest_time TEXT NOT NULL DEFAULT '09:00',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    title         TEXT NOT NULL,
    description   TEXT,
    due_utc       TEXT NOT NULL,
    priority      TEXT NOT NULL DEFAULT 'medium',
    status        TEXT NOT NULL DEFAULT 'active',
    remind_before INTEGER NOT NULL DEFAULT 0,
    repeat_rule   TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at  TEXT
);

CREATE TABLE IF NOT EXISTS reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    fire_at_utc TEXT NOT NULL,
    sent        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tasks_user   ON tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_rem_pending  ON reminders(sent, fire_at_utc);
"""


async def init_db() -> None:
    global _conn
    directory = os.path.dirname(config.DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    _conn = await aiosqlite.connect(config.DB_PATH)
    _conn.row_factory = aiosqlite.Row
    await _conn.executescript(SCHEMA)
    await _conn.commit()
    log.info("DB initialised at %s", config.DB_PATH)


def db() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("DB is not initialised")
    return _conn


async def close_db() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None