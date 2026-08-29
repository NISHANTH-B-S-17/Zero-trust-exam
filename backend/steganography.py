import re
import uuid

# Zero-Width Spaces for Layer 1
ZWSP = '\u200b'
ZWNJ = '\u200c'

def encode_uuid_zwsp(uid: str) -> str:
    """Encode a UUID into a binary ZWSP string."""
    binary = ''.join(format(int(c, 16), '04b') for c in uid.replace('-', ''))
    return ''.join(ZWSP if b == '0' else ZWNJ for b in binary)

def decode_uuid_zwsp(text: str) -> str | None:
    """Extract and decode a ZWSP encoded UUID from text."""
    zwsp_chars = [c for c in text if c in (ZWSP, ZWNJ)]
    if not zwsp_chars or len(zwsp_chars) < 128:
        return None
    
    binary = ''.join('0' if c == ZWSP else '1' for c in zwsp_chars[:128])
    try:
        hex_str = f"{int(binary, 2):032x}"
        return str(uuid.UUID(hex_str))
    except ValueError:
        return None

def apply_layer1(text: str, uid: str) -> str:
    """Inject the ZWSP payload at the end of the first paragraph."""
    encoded = encode_uuid_zwsp(uid)
    paragraphs = text.split('\n')
    if paragraphs:
        paragraphs[0] += encoded
    return '\n'.join(paragraphs)

def trace_leak(text: str) -> dict:
    """Extract forensics from leaked text."""
    uid = decode_uuid_zwsp(text)
    return {
        "layer1_uuid": uid,
        "layer2_confidence": 0.0, # Placeholder for NLP fallback
        "honeytokens_found": []
    }
