import os
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64

MAGIC_HEADER = b"NVSH1"

def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return kdf.derive(password.encode())

def encrypt_payload(data: bytes, password: str) -> bytes:
    salt = os.urandom(16)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, data, None)
    secure_wipe(key)
    return MAGIC_HEADER + salt + nonce + ct

def decrypt_payload(token: bytes, password: str) -> bytes:
    if not token.startswith(MAGIC_HEADER):
        raise ValueError("Invalid magic header")
    token = token[len(MAGIC_HEADER):]
    salt = token[:16]
    nonce = token[16:28]
    ct = token[28:]
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    pt = aesgcm.decrypt(nonce, ct, None)
    secure_wipe(key)
    return pt

def secure_wipe(key):
    """Zeroize key material in memory after converting immutable inputs to mutable bytearray."""
    if isinstance(key, (bytes, bytearray, memoryview)):
        mutable_buf = bytearray(key) if not isinstance(key, bytearray) else key
        for i in range(len(mutable_buf)):
            mutable_buf[i] = 0
