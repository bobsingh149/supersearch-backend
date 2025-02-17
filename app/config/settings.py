from typing import Dict, Any
from dataclasses import dataclass
import yaml
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv(Path(__file__).parent / ".env")

@dataclass
class PostgresSettings:
    host: str
    port: int
    database: str
    user: str
    password: str

    def dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
        }


class Settings:
    def __init__(self):
        # Load config.yaml
        config_path = Path(__file__).parent / "config.yaml"
        with open(config_path, "r") as f:
            raw_config = f.read()
            # Replace ${VAR} with environment variables
            processed_config = os.path.expandvars(raw_config)
            config = yaml.safe_load(processed_config)
        
        # Now config includes env var substitutions
        self.postgres = PostgresSettings(**config["postgres"])



# Create a global settings instance
settings = Settings()
