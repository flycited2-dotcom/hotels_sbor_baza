import aiosqlite
import os
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "leads.db")


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                name TEXT NOT NULL,
                object_type TEXT NOT NULL,
                city TEXT NOT NULL,
                region TEXT NOT NULL,
                address TEXT,
                phone TEXT NOT NULL,
                email TEXT,
                telegram TEXT,
                website TEXT,
                size TEXT NOT NULL,
                interests TEXT NOT NULL,
                status TEXT NOT NULL,
                comment TEXT,
                added_by TEXT NOT NULL,
                status_updated_at TEXT
            )
        """)
        await db.commit()


async def add_lead(data: dict) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO leads (
                created_at, name, object_type, city, region, address,
                phone, email, telegram, website, size, interests,
                status, comment, added_by, status_updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now,
            data.get("name", ""),
            data.get("object_type", ""),
            data.get("city", ""),
            data.get("region", ""),
            data.get("address", ""),
            data.get("phone", ""),
            data.get("email", ""),
            data.get("telegram", ""),
            data.get("website", ""),
            data.get("size", ""),
            data.get("interests", ""),
            data.get("status", "Новый"),
            data.get("comment", ""),
            data.get("added_by", ""),
            now,
        ))
        await db.commit()
        return cursor.lastrowid


async def get_leads_today() -> list:
    today = date.today().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM leads WHERE created_at LIKE ? ORDER BY id",
            (f"{today}%",)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_leads_this_week() -> list:
    from datetime import timedelta
    week_ago = (date.today() - timedelta(days=6)).strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM leads WHERE created_at >= ? ORDER BY id",
            (week_ago,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_all_leads() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM leads ORDER BY id")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def count_today() -> int:
    today = date.today().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM leads WHERE created_at LIKE ?",
            (f"{today}%",)
        )
        row = await cursor.fetchone()
        return row[0]


async def count_total() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM leads")
        row = await cursor.fetchone()
        return row[0]


async def get_last_lead_by_user(username: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM leads WHERE added_by = ? ORDER BY id DESC LIMIT 1",
            (username,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_lead_status(lead_id: int, new_status: str) -> str:
    """Обновляет статус, возвращает timestamp изменения."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE leads SET status = ?, status_updated_at = ? WHERE id = ?",
            (new_status, now, lead_id)
        )
        await db.commit()
    return now


async def get_lead_by_id(lead_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def search_leads(query: str) -> list:
    """Поиск по названию, телефону, городу (регистронезависимо, до 20 результатов)."""
    q = f"%{query}%"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM leads WHERE name LIKE ? OR phone LIKE ? OR city LIKE ? "
            "ORDER BY id DESC LIMIT 20",
            (q, q, q)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_recent_leads_by_user(username: str, limit: int = 5) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM leads WHERE added_by = ? ORDER BY id DESC LIMIT ?",
            (username, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
