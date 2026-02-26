"""
Configuration settings for Callisto project.
Path: config/settings.py
Copyright BINGO Collaboration
Last Modified: 2026-02-24
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    postgres_url: str = Field(
        default="postgresql://user:pass@localhost:5432/callisto",
        description="PostgreSQL connection URL",
    )
    pool_size: int = Field(default=20, ge=1, le=100)
    echo: bool = Field(default=False)

    model_config = {"env_prefix": "CALLISTO_DB_"}


class CallistoSettings(BaseSettings):
    """e-Callisto receiver configuration."""

    config_path: str = Field(
        default="config/callisto.cfg",
        description="Path to e-Callisto configuration file",
    )
    scheduler_config_path: str = Field(
        default="config/scheduler.cfg",
        description="Path to scheduler configuration",
    )
    data_directory: str = Field(
        default="/var/callisto/data",
        description="Directory for spectrometer data",
    )

    model_config = {"env_prefix": "CALLISTO_"}


class APISettings(BaseSettings):
    """API configuration."""

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = Field(default=False)

    model_config = {"env_prefix": "CALLISTO_API_"}


class Settings(BaseSettings):
    """Main settings container."""

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    callisto: CallistoSettings = Field(default_factory=CallistoSettings)
    api: APISettings = Field(default_factory=APISettings)

    model_config = {
        "env_file": ".env",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
    }


# Singleton instance
settings = Settings()
