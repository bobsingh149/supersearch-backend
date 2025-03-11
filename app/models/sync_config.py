from enum import StrEnum
from typing import Optional, Dict, Union, List, Literal
from pydantic import BaseModel, ConfigDict, model_validator
from abc import ABC, abstractmethod

class SyncSource(StrEnum):
    """Enum for sync source types"""
    MANUAL_FILE_UPLOAD = "MANUAL_FILE_UPLOAD"
    CRAWLER = "CRAWLER"
    SUPERSEARCH_API = "SUPERSEARCH_API"
    HOSTED_FILE = "HOSTED_FILE"
    SQL_DATABASE = "SQL_DATABASE"

class SyncStatus(StrEnum):
    """Enum for sync status types"""
    SUCCESS = "SUCCESS"
    PROCESSING = "PROCESSING"
    FAILED = "FAILED"

class SyncInterval(StrEnum):
    """Enum for sync interval types (renamed from SyncDuration)"""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"

class TriggerType(StrEnum):
    """Enum for workflow trigger types"""
    IMMEDIATE = "IMMEDIATE"
    SCHEDULED = "SCHEDULED"

class AuthType(StrEnum):
    """Enum for authentication types"""
    PUBLIC = "PUBLIC"
    BASIC_AUTH = "BASIC_AUTH"

class DatabaseType(StrEnum):
    """Enum for database types"""
    POSTGRESQL = "POSTGRESQL"
    MYSQL = "MYSQL"
    SQLITE = "SQLITE"
    MSSQL = "MSSQL"
    ORACLE = "ORACLE"

# Mapping from SyncSource to TriggerType
SYNC_SOURCE_TRIGGER_MAP: Dict[SyncSource, TriggerType] = {
    SyncSource.MANUAL_FILE_UPLOAD: TriggerType.IMMEDIATE,
    SyncSource.SUPERSEARCH_API: TriggerType.IMMEDIATE,
    SyncSource.CRAWLER: TriggerType.SCHEDULED,
    SyncSource.HOSTED_FILE: TriggerType.SCHEDULED,
    SyncSource.SQL_DATABASE: TriggerType.SCHEDULED,
}

class BaseSourceConfig(BaseModel, ABC):
    """Base class for all source configurations"""
    source: SyncSource
    auto_sync: bool = False
    sync_interval: Optional[SyncInterval] = None  # Renamed from sync_duration
    
    @abstractmethod
    @model_validator(mode='after')
    def validate_data(self) -> 'BaseSourceConfig':
        """Validate the configuration data"""
        return self

class ManualFileUploadConfig(BaseSourceConfig):
    """Configuration for manual file upload"""
    source: Literal[SyncSource.MANUAL_FILE_UPLOAD] = SyncSource.MANUAL_FILE_UPLOAD
    file_format: str
    
    @model_validator(mode='after')
    def validate_data(self) -> 'ManualFileUploadConfig':
        """Validate manual file upload configuration"""
        if self.file_format not in ["csv", "json"]:
            raise ValueError("File format must be either 'csv' or 'json'")
        return self

class CrawlerConfig(BaseSourceConfig):
    """Configuration for web crawler"""
    source: Literal[SyncSource.CRAWLER] = SyncSource.CRAWLER
    urls: List[str]
    max_depth: int = 1
    
    @model_validator(mode='after')
    def validate_data(self) -> 'CrawlerConfig':
        """Validate crawler configuration"""
        if not self.urls:
            raise ValueError("URLs list cannot be empty")
        if self.max_depth < 1:
            raise ValueError("Max depth must be at least 1")
        return self

class SupersearchApiConfig(BaseSourceConfig):
    """Configuration for Supersearch API"""
    source: Literal[SyncSource.SUPERSEARCH_API] = SyncSource.SUPERSEARCH_API

class HostedFileConfig(BaseSourceConfig):
    """Configuration for hosted file"""
    source: Literal[SyncSource.HOSTED_FILE] = SyncSource.HOSTED_FILE
    file_url: str
    file_format: str
    auth_type: AuthType = AuthType.PUBLIC
    username: Optional[str] = None
    password: Optional[str] = None
    
    @model_validator(mode='after')
    def validate_data(self) -> 'HostedFileConfig':
        """Validate hosted file configuration"""
        if not self.file_url:
            raise ValueError("File URL cannot be empty")
        if self.file_format not in ["csv", "json"]:
            raise ValueError("File format must be either 'csv' or 'json'")
        if self.auth_type == AuthType.BASIC_AUTH:
            if not self.username or not self.password:
                raise ValueError("Username and password are required for BASIC_AUTH")
        return self

class SqlDatabaseConfig(BaseSourceConfig):
    """Configuration for SQL database"""
    source: Literal[SyncSource.SQL_DATABASE] = SyncSource.SQL_DATABASE
    database_type: DatabaseType
    host: str
    port: int
    database: str
    username: str
    password: str
    table_name: str
    
    @model_validator(mode='after')
    def validate_data(self) -> 'SqlDatabaseConfig':
        """Validate SQL database configuration"""
        if not all([self.host, self.database, self.username, self.password, self.table_name]):
            raise ValueError("All database configuration fields are required")
        if self.port <= 0:
            raise ValueError("Port must be a positive number")
        return self
    
    @property
    def connection_string(self) -> str:
        """Generate SQLAlchemy connection string based on database type"""
        if self.database_type == DatabaseType.POSTGRESQL:
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.database_type == DatabaseType.MYSQL:
            return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.database_type == DatabaseType.SQLITE:
            return f"sqlite:///{self.database}"
        elif self.database_type == DatabaseType.MSSQL:
            return f"mssql+pymssql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.database_type == DatabaseType.ORACLE:
            return f"oracle://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")
    
    @property
    def query(self) -> str:
        """Generate default query to select all records from the table"""
        return f"SELECT * FROM {self.table_name}"

# Define the discriminated union for source configurations
SourceConfigType = Union[
    ManualFileUploadConfig, 
    CrawlerConfig, 
    SupersearchApiConfig, 
    HostedFileConfig, 
    SqlDatabaseConfig
] 