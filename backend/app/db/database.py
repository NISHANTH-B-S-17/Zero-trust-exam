import aiosqlite
import json
import time
import base64
import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings
from app.services import audit

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
    os.makedirs(os.path.dirname(os.path.abspath(settings.DB_PATH)), exist_ok=True)
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute('PRAGMA journal_mode=WAL')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS Students (
            id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT UNIQUE, roll_no TEXT UNIQUE,
            name TEXT, status TEXT, cached_state_json TEXT, updated_at INTEGER)''')
            
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
            
        # --- Staff Security Tables ---
        await db.execute('''CREATE TABLE IF NOT EXISTS Staff_Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, role TEXT,
            status TEXT, risk_score INTEGER, last_seen INTEGER)''')
            
        await db.execute('''CREATE TABLE IF NOT EXISTS Reviewer_Assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, reviewer_id INTEGER,
            reviewer_name TEXT, question_ids TEXT, access_status TEXT,
            last_viewed INTEGER, risk_score INTEGER)''')
            
        await db.execute('''CREATE TABLE IF NOT EXISTS Risk_Events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, staff_user_id INTEGER,
            staff_name TEXT, role TEXT, risk_score INTEGER, risk_level TEXT,
            trigger_reason TEXT, action_taken TEXT, timestamp INTEGER)''')
            
        await db.execute('''CREATE TABLE IF NOT EXISTS Blocked_Actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, staff_user_id INTEGER,
            staff_name TEXT, attempted_action TEXT, reason_blocked TEXT,
            policy_rule TEXT, timestamp INTEGER)''')
            
        await db.execute('''CREATE TABLE IF NOT EXISTS Staff_Audit_Logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, staff_user_id INTEGER,
            staff_name TEXT, role TEXT, event TEXT, question_id INTEGER,
            session_id TEXT, trace_token TEXT, timestamp INTEGER)''')
            
        await db.commit()

async def seed_demo_data():
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cursor = await db.execute('SELECT COUNT(*) FROM Students')
        if (await cursor.fetchone())[0] > 0:
            return
            
        now = int(time.time())
        
        # 1. Students (10 Realistic Records)
        students_data = [
            ("demo-uuid-1234", "ROLL001", "Aarav Sharma", "A-101", "Delhi Center", "registered", now),
            ("student-uuid-002", "ROLL002", "Priya Patel", "A-102", "Mumbai Center", "registered", now - 120),
            ("student-uuid-003", "ROLL003", "Rohan Gupta", "B-201", "Delhi Center", "registered", now - 300),
            ("student-uuid-004", "ROLL004", "Sneha Reddy", "B-202", "Hyderabad Center", "registered", now - 600),
            ("student-uuid-005", "ROLL005", "Karan Singh", "C-301", "Bengaluru Center", "registered", now - 45),
            ("student-uuid-006", "ROLL006", "Meera Iyer", "C-302", "Chennai Center", "registered", now - 1000),
            ("student-uuid-007", "ROLL007", "Arjun Nair", "D-401", "Kochi Center", "registered", now - 1500),
            ("student-uuid-008", "ROLL008", "Kavya Menon", "D-402", "Kochi Center", "registered", now - 2000),
            ("student-uuid-009", "ROLL009", "Aditya Rao", "E-501", "Pune Center", "registered", now - 30),
            ("student-uuid-010", "ROLL010", "Nisha Verma", "E-502", "Kolkata Center", "registered", now - 500)
        ]
        
        for s in students_data:
            await db.execute('''INSERT INTO Students (uuid, roll_no, name, status, updated_at) 
                VALUES (?, ?, ?, ?, ?)''', (s[0], s[1], s[2], s[5], s[6]))

        # 2. Questions (10 Real Questions across subjects and types)
        questions_data = [
            (1, "Physics", "Thermodynamics", 0.4, "MCQ", 2, 90, "determine the work done in an isothermal expansion of an ideal gas.", '["W = nRT ln(V2/V1)", "W = nR(T2-T1)", "W = 0", "W = P(V2-V1)"]', "W = nRT ln(V2/V1)"),
            (2, "Physics", "Electromagnetism", 0.6, "single_choice", 2, 120, "calculate the magnetic force on a moving charge in a uniform magnetic field.", '["F = q(v x B)", "F = qE", "F = m(v^2/r)", "F = I(L x B)"]', "F = q(v x B)"),
            (3, "Mathematics", "Calculus", 0.5, "numerical", 3, 150, "compute the derivative of f(x) = x^3 - 3x + 5 at x = 2.", '[]', "9"),
            (4, "Mathematics", "Linear Algebra", 0.7, "multiple_choice", 3, 180, "identify the orthogonal matrices among the following options.", '["Matrix with A^T = A^-1", "Matrix with det(A) = 1 or -1", "Matrix with det(A) = 0", "Matrix with A^T = A"]', "Matrix with A^T = A^-1"),
            (5, "Computer Science", "Algorithms", 0.5, "MCQ", 2, 90, "explain the time complexity of QuickSort in the average case.", '["O(N log N)", "O(N^2)", "O(N)", "O(log N)"]', "O(N log N)"),
            (6, "Computer Science", "Data Structures", 0.3, "true_false", 1, 45, "evaluate whether a Binary Search Tree always guarantees O(log N) search time without balancing.", '["True", "False"]', "False"),
            (7, "Computer Science", "Operating Systems", 0.8, "short_answer", 3, 180, "describe the primary condition required for a deadlock to occur in a multi-threaded system.", '[]', "Mutual exclusion, Hold and wait, No preemption, and Circular wait."),
            (8, "Logical Reasoning", "Deductive Logic", 0.4, "single_choice", 2, 60, "analyze the syllogism: All A are B. All B are C. Therefore, all A are C.", '["Valid", "Invalid", "Ambiguous", "Incomplete"]', "Valid"),
            (9, "Logical Reasoning", "Patterns", 0.3, "numerical", 2, 60, "estimate the next number in the series: 2, 6, 12, 20, 30, ?", '[]', "42"),
            (10, "Physics", "Optics", 0.6, "long_answer", 4, 240, "compare the focal length of a convex lens in air versus when immersed in water.", '[]', "Focal length increases in water due to smaller relative refractive index.")
        ]

        for q in questions_data:
            await db.execute('''INSERT INTO Question_Vault 
                (id, subject, topic, irt_difficulty, question_type, marks, estimated_time_seconds,
                question_text_encrypted, options_json_encrypted, correct_answer_encrypted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (q[0], q[1], q[2], q[3], q[4], q[5], q[6], encrypt_field(q[7]), encrypt_field(q[8]), encrypt_field(q[9])))

        # 3. Submissions (1 realistic submission for preview)
        sub_receipt = {"student_uuid": "student-uuid-002", "submitted_at": now - 120, "total_answered": 10}
        receipt_hash = hashlib.sha256(json.dumps(sub_receipt, sort_keys=True).encode()).hexdigest()
        await db.execute('''INSERT INTO Submissions (student_uuid, score, receipt_hash, receipt_json, submitted_at)
            VALUES (?, ?, ?, ?, ?)''', ("student-uuid-002", 85.0, receipt_hash, json.dumps(sub_receipt), now - 120))

        # 4. Audit Logs (System events)
        audit_events = [
            (now - 3600, "system", "SERVER_START", "INFO", "Examination Node active"),
            (now - 1000, "demo-uuid-1234", "STUDENT_AUTHENTICATED", "INFO", "Logged in successfully from A-101"),
            (now - 950, "demo-uuid-1234", "PAPER_GENERATED", "INFO", "Unique watermarked form dispatched"),
            (now - 500, "student-uuid-002", "HEARTBEAT_RECEIVED", "LOW", "State digest synced"),
            (now - 300, "student-uuid-002", "AUTOSAVE_RECEIVED", "LOW", "10 responses preserved"),
            (now - 120, "student-uuid-002", "EXAM_SUBMITTED", "INFO", f"Hash: {receipt_hash}"),
            (now - 60, "admin", "TRACE_LEAK", "MEDIUM", "Forensic trace executed"),
            (now - 30, "unknown", "ACCESS_DENIED", "HIGH", "Unauthorized token attempt")
        ]
        
        for ae in audit_events:
            entry = f"{ae[0]}|{ae[1]}|{ae[2]}|{ae[3]}|{ae[4]}"
            sig = audit.sign_audit_entry(entry)
            await db.execute('''INSERT INTO Audit_Logs (timestamp, student_uuid, event_type, severity, detail, signature)
                VALUES (?, ?, ?, ?, ?, ?)''', (ae[0], ae[1], ae[2], ae[3], ae[4], sig))

        # 5. Staff Data
        await db.execute('INSERT INTO Staff_Users (name, role, status, risk_score, last_seen) VALUES (?, ?, ?, ?, ?)',
                         ("Dr. Meera Rao", "QUESTION_CREATOR", "active", 10, now))
        await db.execute('INSERT INTO Staff_Users (name, role, status, risk_score, last_seen) VALUES (?, ?, ?, ?, ?)',
                         ("Prof. Arjun Sen", "REVIEWER", "active", 45, now))
        await db.execute('INSERT INTO Staff_Users (name, role, status, risk_score, last_seen) VALUES (?, ?, ?, ?, ?)',
                         ("Exam Cell Controller", "EXAM_CONTROLLER", "active", 0, now))
        await db.execute('INSERT INTO Staff_Users (name, role, status, risk_score, last_seen) VALUES (?, ?, ?, ?, ?)',
                         ("Security Officer", "SECURITY_ADMIN", "active", 75, now))
                         
        await db.execute('INSERT INTO Reviewer_Assignments (reviewer_id, reviewer_name, question_ids, access_status, last_viewed, risk_score) VALUES (?, ?, ?, ?, ?, ?)',
                         (2, "Prof. Arjun Sen", "[1, 2, 3, 4, 5]", "assigned", now, 45))
                         
        await db.execute('INSERT INTO Risk_Events (staff_user_id, staff_name, role, risk_score, risk_level, trigger_reason, action_taken, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                         (4, "Security Officer", "SECURITY_ADMIN", 75, "HIGH", "Unusual access pattern", "Alerted", now))

        await db.commit()

async def ensure_db_initialized():
    if not os.path.exists(settings.DB_PATH):
        await init_db()
        await seed_demo_data()

async def fetch_all_questions() -> list:
    await ensure_db_initialized()
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
