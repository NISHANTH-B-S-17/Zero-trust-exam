import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from cryptography.exceptions import InvalidTag
import crypto

def test_encryption_decryption_roundtrip():
    plaintext = b"Zero Trust Test Data"
    password = "strong-master-secret"
    
    encrypted = crypto.encrypt_payload(plaintext, password)
    
    assert isinstance(encrypted, bytes)
    assert encrypted.startswith(crypto.MAGIC_HEADER)
    
    decrypted = crypto.decrypt_payload(encrypted, password)
    assert decrypted == plaintext

def test_key_derivation_determinism():
    password = "deterministic-secret"
    salt1 = os.urandom(16)
    salt2 = os.urandom(16)
    
    key1 = crypto.derive_key(password, salt1)
    key2 = crypto.derive_key(password, salt1)
    key3 = crypto.derive_key(password, salt2)
    
    assert key1 == key2
    assert key1 != key3

def test_secure_wipe():
    key_material = bytearray(b"0123456789abcdef0123456789abcdef")
    crypto.secure_wipe(key_material)
    
    for b in key_material:
        assert b == 0

def test_tamper_handling():
    plaintext = b"Zero Trust Test Data"
    password = "strong-master-secret"
    encrypted = crypto.encrypt_payload(plaintext, password)
    
    # 1. Truncated payload
    with pytest.raises((ValueError, InvalidTag)):
        crypto.decrypt_payload(encrypted[:10], password)
        
    # 2. Wrong magic header
    tampered_header = b"WRONG" + encrypted[5:]
    with pytest.raises(ValueError, match="Invalid magic header"):
        crypto.decrypt_payload(tampered_header, password)
        
    # 3. Corrupted ciphertext/tag
    tampered_ciphertext = bytearray(encrypted)
    tampered_ciphertext[-1] ^= 0x01
    with pytest.raises((ValueError, InvalidTag)):
        crypto.decrypt_payload(bytes(tampered_ciphertext), password)
