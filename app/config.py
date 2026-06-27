from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "My fintech wallet api"
    DEBUG: bool = False
    
    DATABASE_URL: str = Field(..., alias="DATABASE_URL")
    TEST_DATABASE_URL: Optional[str] = Field(None, alias="TEST_DATABASE_URL")
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()