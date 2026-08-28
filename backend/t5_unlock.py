import hmac
import hashlib
import time

def generate_unlock_token(secret: bytes, window: int = 300) -> str:
    """Generate a T-5 minute valid HMAC token."""
    current_window = int(time.time()) // window
    message = str(current_window).encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()

def verify_unlock_token(token: str, secret: bytes, window: int = 300) -> bool:
    """Verify the token is valid for the current or previous 5-minute window."""
    current_window = int(time.time()) // window
    for w in [current_window, current_window - 1]:
        message = str(w).encode()
        expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
        if hmac.compare_digest(token, expected):
            return True
    return False
