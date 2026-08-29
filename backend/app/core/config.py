import os
import tempfile

class Settings:
    PROJECT_NAME: str = "Nivasha Security Engine"
    API_V1_STR: str = "/api/v1"
    
    # In-memory ephemeral encryption key for SQLite TDE
    SQLITE_TDE_KEY: bytes = os.urandom(32)
    
    # Use /tmp on Vercel or read-only/serverless environments, local data folder otherwise
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        DB_PATH: str = os.path.join(tempfile.gettempdir(), "nivasha.db")
        ADMIN_TOKEN_FILE: str = os.path.join(tempfile.gettempdir(), "admin_token.txt")
    else:
        DB_PATH: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "nivasha.db")
        ADMIN_TOKEN_FILE: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "admin_token.txt")
    
    @property
    def ADMIN_TOKEN(self) -> str:
        env_token = os.environ.get("ADMIN_TOKEN")
        if env_token:
            return env_token
            
        if not os.path.exists(self.ADMIN_TOKEN_FILE):
            token = "admin-" + os.urandom(16).hex()
            os.makedirs(os.path.dirname(self.ADMIN_TOKEN_FILE), exist_ok=True)
            with open(self.ADMIN_TOKEN_FILE, "w") as f:
                f.write(token)
            return token
        with open(self.ADMIN_TOKEN_FILE, "r") as f:
            return f.read().strip()

settings = Settings()