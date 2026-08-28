from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import random
from datetime import datetime
import uvicorn

app = FastAPI(title="Project Nivasha Core API", version="1.0.0")

# Enable CORS so our dashboard.html can connect to it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for the prototype
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Return a 204 No Content to silence favicon errors
    return Response(status_code=204)

@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
async def devtools_json():
    # Return a 204 No Content to silence chrome devtools errors
    return Response(status_code=204)

# --- MOCK DATA STORES ---
CANDIDATES = [
    {"roll": "RN-8921", "name": "Sarah Jenkins", "seat": "LAB-A-12", "status": "IN_PROGRESS"},
    {"roll": "RN-8922", "name": "Michael Chang", "seat": "LAB-B-05", "status": "REGISTERED"},
    {"roll": "RN-8923", "name": "David Okafor", "seat": "LAB-A-02", "status": "SUBMITTED"},
    {"roll": "RN-8924", "name": "Elena Rostova", "seat": "LAB-C-10", "status": "IN_PROGRESS"}
]

AUDIT_LOGS = [
    {"time": "10:42:05", "msg": "System heartbeat synchronized across all labs.", "type": "info"},
    {"time": "10:45:12", "msg": "RN-8922 window blur detected (Alt+Tab event).", "type": "warn"},
    {"time": "10:46:00", "msg": "RN-8924 registered session start.", "type": "info"},
    {"time": "10:48:33", "msg": "Unauthorized USB device blocked on LAB-B-05.", "type": "danger"}
]

# --- API ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "online", "system": "Project Nivasha Core"}

@app.get("/api/v1/admin/live-monitor")
def get_live_telemetry(authorization: str = Header(None)):
    """
    Endpoint polled every 3 seconds by the Admin Dashboard.
    Provides live candidate telemetry and real-time audit logs.
    """
    # Simulate dynamic ping generation for active candidates
    live_candidates = []
    for c in CANDIDATES:
        c_copy = c.copy()
        if c_copy["status"] == "IN_PROGRESS":
            c_copy["ping"] = f"{random.randint(10, 45)}ms"
        elif c_copy["status"] == "REGISTERED":
            c_copy["ping"] = "45ms"
        else:
            c_copy["ping"] = "-"
        live_candidates.append(c_copy)
        
    return {
        "status": "success",
        "timestamp": datetime.utcnow().isoformat(),
        "stats": {
            "active_candidates": f"{random.randint(138, 142)} / 150",
            "attendance": "94%",
            "kiosk_status": "Secure",
            "active_violations": 2,
            "security_alerts": random.randint(3, 8),
            "payload_status": "LOCKED"
        },
        "telemetry": live_candidates,
        "audit_logs": AUDIT_LOGS
    }

class ForensicRequest(BaseModel):
    leak_text: str

@app.post("/api/v1/admin/forensic-scan")
def forensic_scan(req: ForensicRequest):
    """
    Analyzes text for Zero-Width Space (ZWSP) markers or synonym frequency.
    """
    # Reject empty submissions
    if not req.leak_text.strip():
        raise HTTPException(status_code=400, detail="Empty leak_text provided")
    
    # Simulated backend response for the forensic engine
    return {
        "status": "matched",
        "candidate": {
            "name": "Michael Chang",
            "roll": "RN-8922",
            "seat": "LAB-B-05",
            "initials": "MC"
        },
        "forensics": {
            "method": "ZWSP Bit-Exact",
            "payload": "0x4A 0x82 0x11",
            "confidence": "99.8%"
        }
    }

class T5Request(BaseModel):
    key_a: str
    key_b: str

@app.post("/api/v1/admin/t5-ceremony")
def execute_t5(req: T5Request):
    """
    Validates the dual-keys to unlock the exam payload.
    """
    if req.key_a and req.key_b:
        return {"status": "unlocked", "message": "Payload decryption successful."}
    raise HTTPException(status_code=400, detail="Missing required cryptographic keys.")

if __name__ == "__main__":
    print("Starting Project Nivasha Core API Backend on http://127.0.0.1:8080")
    uvicorn.run(app, host="127.0.0.1", port=8080)
