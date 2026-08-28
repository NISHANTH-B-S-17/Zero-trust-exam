import re
import uuid
import hashlib

# ---------------------------------------------------------
# Layer 1: Invisible zero-width Unicode fingerprint
# ---------------------------------------------------------
ZWSP = "\u200B"
ZWNJ = "\u200C"
ZWJ = "\u200D"

def uuid_to_binary(uuid_str: str) -> str:
    """Convert a UUID string (ignoring dashes) to binary string."""
    clean_uuid = uuid_str.replace("-", "").lower()
    return bin(int(clean_uuid, 16))[2:].zfill(128)

def binary_to_uuid(binary_str: str) -> str:
    """Convert a binary string back to UUID string format."""
    if len(binary_str) != 128:
        raise ValueError("Binary string must be 128 bits.")
    hex_str = hex(int(binary_str, 2))[2:].zfill(32)
    return str(uuid.UUID(hex_str))

def encode_uuid_zwsp(uuid_str: str) -> str:
    """Encode a UUID string into zero-width characters."""
    binary_str = uuid_to_binary(uuid_str)
    encoded = ""
    for bit in binary_str:
        if bit == '0':
            encoded += ZWSP
        else:
            encoded += ZWNJ
    return ZWJ + encoded + ZWJ

def decode_uuid_zwsp(text: str) -> str:
    """Extract and decode UUID from zero-width characters in text."""
    pattern = re.compile(f"{ZWJ}([{ZWSP}{ZWNJ}]{{128}}){ZWJ}")
    match = pattern.search(text)
    if not match:
        return None
        
    encoded = match.group(1)
    binary_str = ""
    for char in encoded:
        if char == ZWSP:
            binary_str += '0'
        elif char == ZWNJ:
            binary_str += '1'
            
    try:
        return binary_to_uuid(binary_str)
    except Exception:
        return None

def inject_zwsp(question_text: str, uuid_str: str) -> str:
    """Inject zero-width fingerprint at the end of the text."""
    watermark = encode_uuid_zwsp(uuid_str)
    return question_text + watermark

# ---------------------------------------------------------
# Layer 2: Semantic synonym variation
# ---------------------------------------------------------

# Instructional verb map
SYNONYM_MAP = {
    "determine": ["determine", "find out", "ascertain"],
    "explain": ["explain", "clarify", "elucidate"],
    "calculate": ["calculate", "compute", "work out"],
    "identify": ["identify", "recognize", "spot"],
    "analyze": ["analyze", "examine", "investigate"],
    "estimate": ["estimate", "approximate", "guess"],
    "compare": ["compare", "contrast", "weigh"],
    "evaluate": ["evaluate", "assess", "appraise"],
    "describe": ["describe", "detail", "outline"],
    "compute": ["compute", "calculate", "figure"]
}

def get_synonym_choice(uuid_str: str, question_id: str, verb: str, choices: list) -> str:
    """Deterministically pick a synonym based on UUID and Question ID."""
    hash_input = f"{uuid_str}:{question_id}:{verb}".encode('utf-8')
    h = int(hashlib.md5(hash_input).hexdigest(), 16)
    return choices[h % len(choices)]

def apply_synonym_swap(text: str, uuid_str: str, question_id: str) -> str:
    """Replace instructional verbs with deterministic synonyms."""
    # Simple regex fallback instead of SpaCy for robust operation
    watermarked_text = text
    for base_verb, choices in SYNONYM_MAP.items():
        # Case insensitive word replacement
        pattern = re.compile(r'\b' + re.escape(base_verb) + r'\b', re.IGNORECASE)
        
        def repl(match):
            original = match.group(0)
            choice = get_synonym_choice(uuid_str, str(question_id), base_verb, choices)
            # Preserve basic capitalization
            if original.istitle():
                return choice.title()
            elif original.isupper():
                return choice.upper()
            return choice
            
        watermarked_text = pattern.sub(repl, watermarked_text)
    return watermarked_text

def synonym_fingerprint(text: str) -> dict:
    """Extract which synonyms were used in the text."""
    fingerprint = {}
    lower_text = text.lower()
    for base_verb, choices in SYNONYM_MAP.items():
        for choice in choices:
            if re.search(r'\b' + re.escape(choice) + r'\b', lower_text):
                fingerprint[base_verb] = choice
                break # Just record the first found
    return fingerprint

def identify_uuid_by_synonyms(text: str, candidate_uuids: list) -> dict:
    """Attempt to identify the source UUID based on synonyms present."""
    found_synonyms = synonym_fingerprint(text)
    if not found_synonyms:
        return {"match": None, "confidence": 0.0}
        
    scores = {uuid: 0 for uuid in candidate_uuids}
    
    # We can only guess based on assumed question IDs (e.g., 1 to 100)
    # A real system would know the question ID of the leaked text.
    # For now, we just do a simplified check for demo purposes.
    # Since we need a question_id, this is tricky without it.
    # We'll just return low confidence if we use this method blindly.
    return {"match": None, "confidence": 0.1, "note": "Requires question context"}

# ---------------------------------------------------------
# Layer 3: Honeytoken / numeric marker
# ---------------------------------------------------------

def apply_honeytoken_transform(question_dict: dict, uuid_str: str) -> dict:
    """Add a subtle invisible trace token to the question options or text."""
    # We will just append a non-breaking space (or a few) based on the UUID
    # to the end of one of the options.
    transformed = dict(question_dict)
    
    hash_input = f"{uuid_str}:{transformed.get('id', 'unknown')}".encode('utf-8')
    h = int(hashlib.md5(hash_input).hexdigest(), 16)
    
    if "options" in transformed and isinstance(transformed["options"], list) and len(transformed["options"]) > 0:
        opt_idx = h % len(transformed["options"])
        spaces = " " * ((h % 3) + 1) # 1 to 3 spaces
        transformed["options"][opt_idx] = str(transformed["options"][opt_idx]) + spaces
        
    return transformed

# ---------------------------------------------------------
# Orchestration
# ---------------------------------------------------------

def embed_watermark(question_dict: dict, student_uuid: str) -> dict:
    """Apply all 3 layers of watermarking to a question dictionary."""
    watermarked = dict(question_dict)
    
    # Layer 2: Synonyms
    text = watermarked.get("text", "")
    q_id = str(watermarked.get("id", "0"))
    text = apply_synonym_swap(text, student_uuid, q_id)
    
    # Layer 1: ZWSP
    text = inject_zwsp(text, student_uuid)
    watermarked["text"] = text
    
    # Layer 3: Honeytoken
    watermarked = apply_honeytoken_transform(watermarked, student_uuid)
    
    return watermarked

def trace_leak(leaked_text: str, candidate_uuids: list = None) -> dict:
    """Analyze leaked text to find the source."""
    if not candidate_uuids:
        candidate_uuids = []
        
    # 1. Try ZWSP first (highest confidence)
    extracted_uuid = decode_uuid_zwsp(leaked_text)
    if extracted_uuid:
        return {
            "student_uuid": extracted_uuid,
            "method": "zwsp",
            "confidence": 0.99,
            "details": {"extracted_raw": extracted_uuid},
            "language": "investigation_lead"
        }
        
    # 2. Try Synonyms if candidates are provided
    if candidate_uuids:
        syn_result = identify_uuid_by_synonyms(leaked_text, candidate_uuids)
        if syn_result["match"]:
            return {
                "student_uuid": syn_result["match"],
                "method": "synonym",
                "confidence": syn_result["confidence"],
                "details": {"synonyms_found": synonym_fingerprint(leaked_text)},
                "language": "investigation_lead"
            }
            
    # Fallback to none if ambiguous
    return {
        "student_uuid": None,
        "method": "none",
        "confidence": 0.0,
        "details": {},
        "language": "investigation_lead"
    }
