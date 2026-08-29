import aiosqlite
import json
import time
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings

def encrypt_field(text: str) -> str:
    if not text:
        return ""
    import os
    aesgcm = AESGCM(settings.SQLITE_TDE_KEY)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, text.encode('utf-8'), None)
    return base64.b64encode(nonce + ciphertext).decode('utf-8')

def decrypt_field(encoded_text: str) -> str:
    if not encoded_text:
        return ""
    try:
        data = base64.b64decode(encoded_text)
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(settings.SQLITE_TDE_KEY)
        return aesgcm.decrypt(nonce, ciphertext, None).decode('utf-8')
    except Exception:
        return ""

async def init_db():
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('PRAGMA journal_mode=WAL')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS Students (
            id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT UNIQUE, roll_no TEXT UNIQUE,
            name TEXT, status TEXT, updated_at INTEGER)''')
            
        await db.execute('''CREATE TABLE IF NOT EXISTS Question_Vault (
            id INTEGER PRIMARY KEY, subject TEXT, topic TEXT, irt_difficulty REAL,
            question_type TEXT, marks INTEGER, estimated_time_seconds INTEGER,
            question_text_encrypted TEXT, options_json_encrypted TEXT, correct_answer_encrypted TEXT)''')
            
        await db.execute('''CREATE TABLE IF NOT EXISTS Generated_Papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_uuid TEXT, paper_json TEXT,
            honeytoken_answers_json TEXT, created_at INTEGER)''')
            
        await db.execute('''CREATE TABLE IF NOT EXISTS Telemetry_Events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_uuid TEXT, session_id TEXT,
            event_type TEXT, severity TEXT, detail TEXT, timestamp INTEGER)''')
            
        await db.execute('''CREATE TABLE IF NOT EXISTS Audit_Logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER, student_uuid TEXT,
            event_type TEXT, severity TEXT, detail TEXT, signature TEXT)''')
            
        await db.execute('''CREATE TABLE IF NOT EXISTS Submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_uuid TEXT, score REAL,
            receipt_hash TEXT, receipt_json TEXT, submitted_at INTEGER)''')
            
        await db.commit()

async def seed_demo_data():
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cursor = await db.execute('SELECT COUNT(*) FROM Students')
        if (await cursor.fetchone())[0] > 0:
            return
            
        now = int(time.time())
        await db.execute('INSERT INTO Students (uuid, roll_no, name, status, updated_at) VALUES (?, ?, ?, ?, ?)',
                         ("demo-uuid-1234", "ROLL001", "Demo Student", "registered", now))
        
        demo_qs = [
            (1, "Science", "Physics", 0.5, "MCQ", 1, 60, "determine the velocity.", '["10", "11"]', "11"),
            (2, "Math", "Algebra", 0.6, "MCQ", 1, 60, "explain 2x=4.", '["1", "2"]', "2"),
        ]
        
        for q in demo_qs:
            await db.execute('''INSERT INTO Question_Vault 
                (id, subject, topic, irt_difficulty, question_type, marks, estimated_time_seconds,
                question_text_encrypted, options_json_encrypted, correct_answer_encrypted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (q[0], q[1], q[2], q[3], q[4], q[5], q[6], encrypt_field(q[7]), encrypt_field(q[8]), encrypt_field(q[9])))
                
        await db.commit()

async def fetch_all_questions() -> list:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM Question_Vault')
        rows = await cursor.fetchall()
        
        questions = []
        for r in rows:
            q = dict(r)
            q['text'] = decrypt_field(q['question_text_encrypted'])
            q['options'] = json.loads(decrypt_field(q['options_json_encrypted']) or "[]")
            q['correct_answer'] = decrypt_field(q['correct_answer_encrypted'])
            questions.append(q)
        return questions
