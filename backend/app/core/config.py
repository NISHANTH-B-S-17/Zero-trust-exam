import os

class Settings:
    PROJECT_NAME: str = "Nivasha Security Engine"
    API_V1_STR: str = "/api/v1"
    
    # In-memory ephemeral encryption key for SQLite TDE
    SQLITE_TDE_KEY: bytes = os.urandom(32)
    
    # Use /tmp for serverless (Vercel) writable environment if needed
    _base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    _is_vercel = os.environ.get("VERCEL") == "1"
    
    DB_PATH: str = "/tmp/nivasha.db" if _is_vercel else os.path.join(_base_dir, "data", "nivasha.db")
    ADMIN_TOKEN_FILE: str = "/tmp/admin_token.txt" if _is_vercel else os.path.join(_base_dir, "admin_token.txt")
    
    @property
    def ADMIN_TOKEN(self) -> str:
        if os.environ.get("ADMIN_TOKEN"):
            return os.environ["ADMIN_TOKEN"]
        if not os.path.exists(self.ADMIN_TOKEN_FILE):
            token = "admin-" + os.urandom(16).hex()
            os.makedirs(os.path.dirname(self.ADMIN_TOKEN_FILE), exist_ok=True)
            with open(self.ADMIN_TOKEN_FILE, "w") as f:
                f.write(token)
            return token
        with open(self.ADMIN_TOKEN_FILE, "r") as f:
            return f.read().strip()

settings = Settings()