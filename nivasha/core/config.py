import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet

class Settings(BaseSettings):
    app_name: str = "Nivasha Zero Trust Exam Engine"
    database_url: str = "sqlite:///./nivasha.db"
    
    # In a real app, this MUST be a securely managed secret, not generated on the fly or hardcoded like this.
    # We generate one if it doesn't exist for the MVP to run smoothly.
    encryption_key: str = os.getenv("NIVASHA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
