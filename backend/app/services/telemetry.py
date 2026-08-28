def evaluate_incident_severity(event_type: str, detail: str) -> str:
    rules = {
        "heartbeat": "LOW",
        "focus_returned": "LOW",
        "exam_submit": "INFO",
        "focus_loss": "MEDIUM",
        "suspicious_keystroke": "HIGH",
        "clipboard_attempt": "HIGH",
        "shortcut_attempt": "HIGH"
    }
    
    # If the detail mentions "repeated" or we track state, we could escalate to CRITICAL
    # For now, base mapping:
    return rules.get(event_type, "LOW")
