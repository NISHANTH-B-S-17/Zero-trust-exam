import os
import tempfile

class Settings:
    PROJECT_NAME: str = "Nivasha Security Engine"
    API_V1_STR: str = "/api/v1"
    
    _base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    _is_vercel = os.environ.get("VERCEL") == "1" or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None
    
    # In-memory ephemeral encryption key for local air-gapped sessions or stable serverless key
    @property
    def SQLITE_TDE_KEY(self) -> bytes:
        if os.environ.get("SQLITE_TDE_KEY"):
            return os.environ["SQLITE_TDE_KEY"].encode("utf-8").zfill(32)[:32]
        if self._is_vercel:
            # Deterministic stable key for serverless process cold starts
            return b"NVSH_SERVERLESS_STABLE_KEY_256!"
        if not hasattr(self, "_ephemeral_key"):
            self._ephemeral_key = os.urandom(32)
        return self._ephemeral_key
    
    DB_PATH: str = os.path.join(tempfile.gettempdir(), "nivasha.db") if _is_vercel else os.path.join(_base_dir, "data", "nivasha.db")
    ADMIN_TOKEN_FILE: str = os.path.join(tempfile.gettempdir(), "admin_token.txt") if _is_vercel else os.path.join(_base_dir, "admin_token.txt")
    
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
