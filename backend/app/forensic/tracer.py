from app.forensic import watermark

def trace_leak(leaked_text: str, candidate_uuids: list = None) -> dict:
    if not candidate_uuids:
        candidate_uuids = []
        
    extracted_md5 = watermark.decode_uuid_zwsp(leaked_text)
    likely_session = None
    
    if extracted_md5 and candidate_uuids:
        import hashlib
        for uid in candidate_uuids:
            if hashlib.md5(uid.encode()).hexdigest() == extracted_md5:
                likely_session = uid
                break
                
    if likely_session:
        return {
            "likely_source_session": likely_session,
            "method": "zwsp",
            "confidence": 0.99,
            "forensic_investigation_lead": "Exact invisible Unicode match found. Review telemetry for this session.",
            "note": "Provides investigation leads, not legal proof of guilt."
        }
        
    return {
        "likely_source_session": None,
        "method": "none",
        "confidence": 0.0,
        "forensic_investigation_lead": "No strong watermark recovered. Consider OCR or manual semantic review.",
        "note": "Provides investigation leads, not legal proof of guilt."
    }
