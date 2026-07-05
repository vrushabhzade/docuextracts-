import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: str = "local"
    ALLOWED_ORIGIN: str = "http://localhost:5173"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    
    # LLM Provider Configuration ("gemini" or "ollama")
    LLM_PROVIDER: str = "gemini"
    OLLAMA_API_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"
    
    AWS_REGION: str = "us-east-1"
    DYNAMODB_TABLE: str = "docuextract-records"
    S3_BUCKET: str = "docuextract-images-bucket-name"
    
    # AWS Credentials overrides for local development or explicit credentials
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    
    # Optional endpoint overrides for local mocking / LocalStack / local DynamoDB container
    AWS_ENDPOINT_URL: Optional[str] = None
    DYNAMODB_ENDPOINT_URL: Optional[str] = None

    model_config = SettingsConfigDict(
        # Search for .env first in current working directory, then in parent
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

class SettingsProxy:
    def __init__(self):
        self._cached_prod_settings = None

    def __getattr__(self, name):
        # In production, cache the Settings object to avoid reading the file repeatedly
        if os.getenv("ENVIRONMENT") == "production":
            if self._cached_prod_settings is None:
                self._cached_prod_settings = Settings()
            return getattr(self._cached_prod_settings, name)
        
        # In local development, always load the latest settings from the .env file
        return getattr(Settings(), name)

settings = SettingsProxy()
