import hashlib

def sign_audit_entry(entry_str: str, secret: str = "local_audit_secret") -> str:
    """Creates an HMAC-SHA256 signature for the audit log entry."""
    # In production, use a secure key from KMS. Here we use a local secret.
    h = hashlib.sha256()
    h.update(f"{entry_str}|{secret}".encode('utf-8'))
    return h.hexdigest()

def verify_audit_signature(log: dict, secret: str = "local_audit_secret") -> bool:
    entry_str = f"{log['timestamp']}|{log['student_uuid']}|{log['event_type']}|{log['severity']}|{log['detail']}"
    expected_sig = sign_audit_entry(entry_str, secret)
    return log.get('signature') == expected_sig
