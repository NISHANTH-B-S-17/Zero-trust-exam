import aiosqlite
import json
import os
import time
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DB_PATH = "nivasha.db"
# Ephemeral SQLite text-field encryption key in RAM
SQLITE_TDE_KEY = os.urandom(32)

def encrypt_field(text: str) -> str:
    """Encrypt a text field for DB storage."""
    if not text:
        return ""
    aesgcm = AESGCM(SQLITE_TDE_KEY)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, text.encode('utf-8'), None)
    return base64.b64encode(nonce + ciphertext).decode('utf-8')

def decrypt_field(encoded_text: str) -> str:
    """Decrypt a text field from DB storage."""
    if not encoded_text:
        return ""
    try:
        data = base64.b64decode(encoded_text)
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(SQLITE_TDE_KEY)
        return aesgcm.decrypt(nonce, ciphertext, None).decode('utf-8')
    except Exception:
        return "" # Return empty on failure for safety

async def init_db():
    """Initialize async SQLite with WAL mode and create tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('PRAGMA journal_mode=WAL')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS Students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE,
                roll_no TEXT UNIQUE,
                name TEXT,
                seat_no TEXT,
                status TEXT,
                cached_state_json TEXT,
                created_at INTEGER,
                updated_at INTEGER
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS Question_Vault (
                id INTEGER PRIMARY KEY,
                subject TEXT,
                topic TEXT,
                irt_difficulty REAL,
                question_type TEXT,
                question_text_encrypted TEXT,
                options_json_encrypted TEXT,
                correct_answer_encrypted TEXT,
                created_at INTEGER
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS Generated_Papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_uuid TEXT,
                paper_json TEXT,
                honeytoken_answers_json TEXT,
                duration_minutes INTEGER,
                created_at INTEGER
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS Telemetry_Events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_uuid TEXT,
                session_id TEXT,
                event_type TEXT,
                severity TEXT,
                detail TEXT,
                timestamp INTEGER
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS Audit_Logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                student_uuid TEXT,
                event_type TEXT,
                severity TEXT,
                detail TEXT,
                signature TEXT
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS Submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_uuid TEXT,
                answers_json TEXT,
                score REAL,
                total_questions INTEGER,
                correct_count INTEGER,
                receipt_hash TEXT,
                receipt_json TEXT,
                submitted_at INTEGER
            )
        ''')
        await db.commit()

async def seed_demo_data():
    """Seed demo data. Marked clearly as demo seed data."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Check if already seeded
        cursor = await db.execute('SELECT COUNT(*) FROM Students')
        count = (await cursor.fetchone())[0]
        if count > 0:
            return
            
        now = int(time.time())
        # Demo Student
        await db.execute('''
            INSERT INTO Students (uuid, roll_no, name, seat_no, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ("demo-uuid-1234", "ROLL001", "Demo Student", "A1", "registered", now, now))
        
        # Demo Questions
        demo_questions = [
            (1, "Science", "Physics", 0.5, "MCQ", "determine the velocity of an unladen swallow.", '["10m/s", "11m/s", "African or European?"]', "African or European?"),
            (2, "Math", "Algebra", 0.6, "MCQ", "explain how to solve for x in 2x=4.", '["x=1", "x=2", "x=3"]', "x=2"),
            (3, "History", "WW2", 0.4, "MCQ", "identify the year WWII ended.", '["1943", "1944", "1945"]', "1945"),
            (4, "Science", "Chemistry", 0.7, "MCQ", "calculate the molar mass of water.", '["16", "18", "20"]', "18")
        ]
        
        for q in demo_questions:
            await db.execute('''
                INSERT INTO Question_Vault 
                (id, subject, topic, irt_difficulty, question_type, question_text_encrypted, options_json_encrypted, correct_answer_encrypted, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                q[0], q[1], q[2], q[3], q[4],
                encrypt_field(q[5]),
                encrypt_field(q[6]),
                encrypt_field(q[7]),
                now
            ))
            
        await db.commit()

# --- Students ---

async def get_student(uuid: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Students WHERE uuid = ?', (uuid,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_student_by_roll(roll_no: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Students WHERE roll_no = ?', (roll_no,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def register_student(uuid: str, roll_no: str, name: str, seat_no: str):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO Students (uuid, roll_no, name, seat_no, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (uuid, roll_no, name, seat_no, "registered", now, now))
        await db.commit()

async def save_student_heartbeat(uuid: str, state_json: str):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE Students SET cached_state_json = ?, updated_at = ? WHERE uuid = ?
        ''', (state_json, now, uuid))
        await db.commit()

# --- Questions ---

async def fetch_all_questions() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Question_Vault')
        rows = await cursor.fetchall()
        
        questions = []
        for r in rows:
            q = dict(r)
            # Decrypt fields on the fly
            q['text'] = decrypt_field(q['question_text_encrypted'])
            q['options'] = json.loads(decrypt_field(q['options_json_encrypted']) or "[]")
            q['correct_answer'] = decrypt_field(q['correct_answer_encrypted'])
            questions.append(q)
        return questions

async def bulk_insert_questions(questions: list):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        for q in questions:
            await db.execute('''
                INSERT INTO Question_Vault 
                (id, subject, topic, irt_difficulty, question_type, question_text_encrypted, options_json_encrypted, correct_answer_encrypted, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                q.get('id'), q.get('subject', ''), q.get('topic', ''), q.get('irt_difficulty', 0.5), q.get('question_type', 'MCQ'),
                encrypt_field(q.get('text', '')),
                encrypt_field(json.dumps(q.get('options', []))),
                encrypt_field(q.get('correct_answer', '')),
                now
            ))
        await db.commit()

# --- Papers ---

async def save_paper(student_uuid: str, paper: list, honeytoken_answers: dict, duration_minutes: int):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO Generated_Papers (student_uuid, paper_json, honeytoken_answers_json, duration_minutes, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (student_uuid, json.dumps(paper), json.dumps(honeytoken_answers), duration_minutes, now))
        await db.commit()

async def get_paper(student_uuid: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Generated_Papers WHERE student_uuid = ? ORDER BY created_at DESC LIMIT 1', (student_uuid,))
        row = await cursor.fetchone()
        return dict(row) if row else None

# --- Telemetry & Audit ---

async def record_telemetry_event(student_uuid: str, session_id: str, event_type: str, severity: str, detail: str):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO Telemetry_Events (student_uuid, session_id, event_type, severity, detail, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_uuid, session_id, event_type, severity, detail, now))
        await db.commit()

async def list_live_sessions(recent_seconds: int = 300) -> list:
    cutoff = int(time.time()) - recent_seconds
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT uuid, name, updated_at FROM Students WHERE updated_at >= ?', (cutoff,))
        return [dict(r) for r in await cursor.fetchall()]
        
async def fetch_recent_incidents(limit: int = 50) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Telemetry_Events ORDER BY timestamp DESC LIMIT ?', (limit,))
        return [dict(r) for r in await cursor.fetchall()]

def sign_audit_entry(entry: str) -> str:
    """Mock signature for audit logs."""
    return "SIGNED_" + hashlib.sha256(entry.encode()).hexdigest()[:16]

async def log_audit(student_uuid: str, event_type: str, severity: str, detail: str):
    now = int(time.time())
    entry_str = f"{now}|{student_uuid}|{event_type}|{severity}|{detail}"
    sig = sign_audit_entry(entry_str)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO Audit_Logs (timestamp, student_uuid, event_type, severity, detail, signature)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (now, student_uuid, event_type, severity, detail, sig))
        await db.commit()

async def fetch_audit_logs() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Audit_Logs ORDER BY timestamp DESC')
        return [dict(r) for r in await cursor.fetchall()]

def verify_audit_signature(log: dict) -> bool:
    entry_str = f"{log['timestamp']}|{log['student_uuid']}|{log['event_type']}|{log['severity']}|{log['detail']}"
    expected_sig = sign_audit_entry(entry_str)
    return log['signature'] == expected_sig

# --- Submissions ---

async def record_submission(student_uuid: str, answers: dict, score: float, total: int, correct: int, receipt_hash: str, receipt: dict):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO Submissions (student_uuid, answers_json, score, total_questions, correct_count, receipt_hash, receipt_json, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_uuid, json.dumps(answers), score, total, correct, receipt_hash, json.dumps(receipt), now))
        await db.commit()

async def get_submission(student_uuid: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Submissions WHERE student_uuid = ? ORDER BY submitted_at DESC LIMIT 1', (student_uuid,))
        row = await cursor.fetchone()
        return dict(row) if row else None
