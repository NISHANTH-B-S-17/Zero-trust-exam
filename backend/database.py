import aiosqlite
import os

SQLITE_TDE_KEY = os.environ.get("SQLITE_TDE_KEY", "default-volatile-key")

async def get_db():
    # In a real scenario with sqlcipher, we would pass the key here.
    # We use a standard sqlite memory or file DB for this blueprint.
    db = await aiosqlite.connect("file:nivasha_volatile.db?mode=memory&cache=shared", uri=True)
    await db.execute("PRAGMA journal_mode=WAL")
    
    # Initialize schema
    await db.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            student_uuid TEXT,
            details TEXT,
            signature TEXT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_uuid TEXT NOT NULL,
            payload TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    await db.commit()
    return db

async def log_event(db: aiosqlite.Connection, event_type: str, student_uuid: str, details: str):
    import datetime
    ts = datetime.datetime.utcnow().isoformat()
    # Simple mock signature
    signature = "signed-mock-hash"
    await db.execute(
        "INSERT INTO audit_logs (timestamp, event_type, student_uuid, details, signature) VALUES (?, ?, ?, ?, ?)",
        (ts, event_type, student_uuid, details, signature)
    )
    await db.commit()
