"""Configurações do backend (variáveis de ambiente / arquivo .env)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SAMPLE_DIR = BASE_DIR / "data" / "sample"

DEV_SECRET = "dev-only-secret-change-me"

DEFAULT_MARKERS = ["N/A", "NA", "n/a", "NULL", "null", "None", "nan", "#N/A", "s/d", "?"]

# Colunas com este percentual (ou mais) de ausências têm severidade crítica.
CRITICAL_MISSING_PCT = 50.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DATACHECK_", extra="ignore")

    secret_key: str = DEV_SECRET
    environment: str = "development"
    cookie_secure: bool = False  # True em produção (HTTPS)
    cookie_samesite: str = "lax"
    session_days: int = 7
    database_url: str = "postgresql+psycopg://datacheck:datacheck@localhost:5432/datacheck"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_mb: float = 10
    temp_dir: str = str(Path(tempfile.gettempdir()) / "datacheck_uploads")
    upload_ttl_minutes: int = 60
    max_stored_issues: int = 100_000
    # Armazenamento privado das bases tratadas e relatórios (metadados ficam no PostgreSQL)
    data_dir: str = str(BASE_DIR / "data" / "storage")
    data_retention_days: int = 30
    max_versions: int = 50

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    return Settings()  # lido a cada chamada: barato e facilita testes
