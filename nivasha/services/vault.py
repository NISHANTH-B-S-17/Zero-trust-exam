from nivasha.core.config import settings
from cryptography.fernet import Fernet
import json

class VaultService:
    def __init__(self):
        self.cipher = Fernet(settings.encryption_key.encode())

    def encrypt(self, data: dict) -> str:
        """Encrypts dictionary data to a string."""
        json_data = json.dumps(data)
        encrypted_bytes = self.cipher.encrypt(json_data.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')

    def decrypt(self, encrypted_string: str) -> dict:
        """Decrypts a string back to dictionary data."""
        decrypted_bytes = self.cipher.decrypt(encrypted_string.encode('utf-8'))
        return json.loads(decrypted_bytes.decode('utf-8'))

vault = VaultService()
