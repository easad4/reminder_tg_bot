import database as db
import config


async def ensure_user(tg_id: int) -> None:
    conn = db.db()
    await conn.execute(
        "INSERT OR IGNORE INTO users (tg_id, timezone, digest_time) VALUES (?,?,?)",
        (tg_id, config.DEFAULT_TZ, config.DEFAULT_DIGEST_TIME),
    )
    await conn.commit()


async def get_user(tg_id: int):
    cur = await db.db().execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
    row = await cur.fetchone()
    await cur.close()
    return row


async def set_timezone(tg_id: int, tz: str) -> None:
    conn = db.db()
    await conn.execute("UPDATE users SET timezone=? WHERE tg_id=?", (tz, tg_id))
    await conn.commit()


async def set_digest_time(tg_id: int, hhmm: str) -> None:
    conn = db.db()
    await conn.execute("UPDATE users SET digest_time=? WHERE tg_id=?", (hhmm, tg_id))
    await conn.commit()


async def all_users():
    cur = await db.db().execute("SELECT * FROM users")
    rows = await cur.fetchall()
    await cur.close()
    return rows