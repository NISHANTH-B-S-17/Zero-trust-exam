import re
import uuid
import hashlib

ZWSP = "\u200B"
ZWNJ = "\u200C"
ZWJ = "\u200D"

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

def uuid_to_binary(uuid_str: str) -> str:
    # A generic demo UUID might not be a valid hex. Hash it to a 128-bit MD5 hex to guarantee int() parsing.
    md5_hash = hashlib.md5(uuid_str.encode()).hexdigest()
    return bin(int(md5_hash, 16))[2:].zfill(128)

def binary_to_uuid(binary_str: str) -> str:
    if len(binary_str) != 128:
        raise ValueError("Binary string must be 128 bits.")
    return hex(int(binary_str, 2))[2:].zfill(32)

def encode_uuid_zwsp(uuid_str: str) -> str:
    binary_str = uuid_to_binary(uuid_str)
    encoded = "".join(ZWNJ if bit == '1' else ZWSP for bit in binary_str)
    return ZWJ + encoded + ZWJ

def decode_uuid_zwsp(text: str) -> str:
    pattern = re.compile(f"{ZWJ}([{ZWSP}{ZWNJ}]{{128}}){ZWJ}")
    match = pattern.search(text)
    if not match:
        return None
    
    encoded = match.group(1)
    binary_str = "".join('1' if char == ZWNJ else '0' for char in encoded)
    
    try:
        return binary_to_uuid(binary_str)
    except Exception:
        return None

def apply_synonym_swap(text: str, uuid_str: str, question_id: str) -> str:
    watermarked_text = text
    for base_verb, choices in SYNONYM_MAP.items():
        pattern = re.compile(r'\b' + re.escape(base_verb) + r'\b', re.IGNORECASE)
        
        def repl(match):
            original = match.group(0)
            h = int(hashlib.md5(f"{uuid_str}:{question_id}:{base_verb}".encode()).hexdigest(), 16)
            choice = choices[h % len(choices)]
            
            if original.istitle(): return choice.title()
            if original.isupper(): return choice.upper()
            return choice
            
        watermarked_text = pattern.sub(repl, watermarked_text)
    return watermarked_text

def apply_honeytoken(question_dict: dict, uuid_str: str) -> dict:
    """Safe honeytoken mapping - uses spaces on options rather than altering numerical truths."""
    transformed = dict(question_dict)
    h = int(hashlib.md5(f"{uuid_str}:{transformed.get('id', '0')}".encode()).hexdigest(), 16)
    
    if "options" in transformed and isinstance(transformed["options"], list) and len(transformed["options"]) > 0:
        opt_idx = h % len(transformed["options"])
        spaces = " " * ((h % 3) + 1)
        transformed["options"][opt_idx] = str(transformed["options"][opt_idx]) + spaces
        
    return transformed

def embed_watermark(question_dict: dict, student_uuid: str) -> dict:
    watermarked = dict(question_dict)
    text = watermarked.get("text", "")
    q_id = str(watermarked.get("id", "0"))
    
    text = apply_synonym_swap(text, student_uuid, q_id)
    text += encode_uuid_zwsp(student_uuid)
    
    watermarked["text"] = text
    return apply_honeytoken(watermarked, student_uuid)
