"""Application configuration loaded from environment variables."""
import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        # Where the SQLite file lives. On Railway this should point at the
        # mounted persistent volume (e.g. /data/notes.db).
        self.db_path: str = os.environ.get("DB_PATH", "./data/notes.db")

        # Used to derive the Fernet key that encrypts the Substack session
        # cookie at rest. MUST be set to a stable value in production, otherwise
        # the stored cookie can no longer be decrypted after a restart.
        self.secret_key: str = os.environ.get("SECRET_KEY", "dev-insecure-change-me")

        # HTTP port (Railway injects PORT).
        self.port: int = int(os.environ.get("PORT", "8000"))

        # Single shared password protecting the whole dashboard. If unset, the
        # app runs without auth (fine for pure localhost dev only).
        self.app_password: str | None = os.environ.get("APP_PASSWORD") or None

        # Directory containing the built frontend (index.html + assets).
        self.static_dir: str = os.environ.get("STATIC_DIR", "./static")

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
