import time

def is_within_t5_window(exam_start_timestamp: int, now_timestamp: int = None) -> bool:
    """Unlock allowed only from 5 minutes (300 seconds) before exam start until exam start time."""
    if now_timestamp is None:
        now_timestamp = int(time.time())
        
    window_start = exam_start_timestamp - 300
    window_end = exam_start_timestamp
    
    return window_start <= now_timestamp <= window_end

def validate_t5_unlock(exam_start_timestamp: int, center_secret: str, invigilator_token: str, exam_id: str, totp_code: str, now_timestamp: int = None) -> bool:
    if not all([center_secret, invigilator_token, exam_id, totp_code]):
        raise ValueError("Missing required unlock parameters")
        
    if not is_within_t5_window(exam_start_timestamp, now_timestamp):
        raise ValueError("Unlock rejected: Outside T-5 window")
        
    return True
