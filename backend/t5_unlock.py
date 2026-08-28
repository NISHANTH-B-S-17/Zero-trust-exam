import hmac
import hashlib
import time

def derive_session_key(center_secret: str, invigilator_token: str, exam_id: str, totp_code: str) -> bytes:
    """Derive the actual decryption key for the exam payload."""
    # In a real scenario, totp_code would be validated against a shared secret.
    # Here we just use it as key material to ensure all parts are present.
    key_material = f"{center_secret}|{invigilator_token}|{exam_id}|{totp_code}".encode('utf-8')
    
    # Hash it to get a 32-byte key
    return hashlib.sha256(key_material).digest()

def is_within_t5_window(exam_start_timestamp: int, now_timestamp: int = None) -> bool:
    """
    Check if current time is within the T-5 window.
    Unlock allowed only from 5 minutes (300 seconds) before exam start until exam start time.
    """
    if now_timestamp is None:
        now_timestamp = int(time.time())
        
    window_start = exam_start_timestamp - 300
    window_end = exam_start_timestamp
    
    return window_start <= now_timestamp <= window_end

def validate_t5_unlock(exam_start_timestamp: int, center_secret: str, invigilator_token: str, exam_id: str, totp_code: str, now_timestamp: int = None) -> bool:
    """
    Validate all parameters and the time window for the T-5 unlock.
    Raises ValueError if outside window or parameters are invalid.
    """
    if not all([center_secret, invigilator_token, exam_id, totp_code]):
        raise ValueError("Missing required unlock parameters")
        
    if not is_within_t5_window(exam_start_timestamp, now_timestamp):
        raise ValueError("Unlock rejected: Outside T-5 window")
        
    # In a real system, we'd also validate the TOTP code here.
    return True
