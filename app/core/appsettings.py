from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path

# Get the project root directory (where .env is located)
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")

# Function to resolve paths relative to project root
def resolve_path(path_str):
    """Resolve a path that might be relative to project root"""
    if path_str.startswith('./') or path_str.startswith('../'):
        # It's a relative path, make it relative to PROJECT_ROOT
        return os.path.normpath(os.path.join(PROJECT_ROOT, path_str))
    return path_str

class PostgresSettings(BaseSettings):
    host: str
    port: int
    db: str
    user: str
    password: str

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_prefix="POSTGRES_",
        extra="ignore"
    )


class GoogleSettings(BaseSettings):
    application_credentials: str
    cloud_project: str

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_prefix="GOOGLE_",
        extra="ignore"
    )
    
    @property
    def credentials_path(self):
        """Return the absolute path to the credentials file"""
        return resolve_path(self.application_credentials)
    
    @property
    def project(self):
        """Return the Google Cloud project ID"""
        return self.cloud_project

class JinaSettings(BaseSettings):
    api_key: str

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_prefix="JINA_",
        extra="ignore"
    )

class CohereSettings(BaseSettings):
    api_key: str

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_prefix="COHERE_",
        extra="ignore"
    )

class AppSettings(BaseSettings):
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    google: GoogleSettings = Field(default_factory=GoogleSettings)
    jina: JinaSettings = Field(default_factory=JinaSettings)
    cohere: CohereSettings = Field(default_factory=CohereSettings)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        extra="ignore"
    )

# Create a global settings instance
app_settings = AppSettings()


