import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag

MAGIC_HEADER = b"NVSH1"

def generate_master_key() -> bytes:
    """Generate a random 32-byte master key for AES-256."""
    return os.urandom(32)

def derive_key(secret: bytes, salt: bytes) -> bytes:
    """Derive a key using PBKDF2-HMAC-SHA256 with 100,000 iterations."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return kdf.derive(secret)

def encrypt_payload(plaintext: bytes, master_key: bytes) -> bytes:
    """Encrypt payload using AES-256-GCM with envelope layout."""
    salt = os.urandom(16)
    nonce = os.urandom(12)
    
    # Derive encryption key from master key and salt
    encryption_key = derive_key(master_key, salt)
    
    aesgcm = AESGCM(encryption_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=MAGIC_HEADER)
    
    # Envelope: MAGIC_HEADER (5) + salt (16) + nonce (12) + ciphertext
    return MAGIC_HEADER + salt + nonce + ciphertext

def decrypt_payload(envelope: bytes, master_key: bytes) -> bytes:
    """Decrypt payload using AES-256-GCM envelope."""
    if len(envelope) < 5 + 16 + 12:
        raise ValueError("Invalid payload: too short")
        
    header = envelope[:5]
    if header != MAGIC_HEADER:
        raise ValueError("Invalid payload: wrong header")
        
    salt = envelope[5:21]
    nonce = envelope[21:33]
    ciphertext = envelope[33:]
    
    encryption_key = derive_key(master_key, salt)
    aesgcm = AESGCM(encryption_key)
    
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=MAGIC_HEADER)
        return plaintext
    except InvalidTag:
        raise ValueError("Invalid payload: wrong key or tampered ciphertext")

def secure_wipe(key_bytes: bytearray) -> None:
    """Zero out key bytes in memory. (Note: standard Python 'bytes' are immutable,
    so this works on mutable structures like bytearrays. We do a best-effort clear)."""
    if isinstance(key_bytes, bytearray):
        for i in range(len(key_bytes)):
            key_bytes[i] = 0
