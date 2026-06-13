"""Database engine, session factory, and schema initialisation."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import get_settings
from .models import Base, Setting

settings = get_settings()

# Ensure the directory for the SQLite file exists.
db_dir = os.path.dirname(os.path.abspath(settings.db_path))
os.makedirs(db_dir, exist_ok=True)

engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},  # shared across scheduler thread
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _ensure_columns() -> None:
    """Lightweight SQLite migration: add columns introduced after first run."""
    with engine.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(settings)")}
        if "slot_times" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE settings ADD COLUMN slot_times "
                "VARCHAR(128) NOT NULL DEFAULT '09:00,15:00'"
            )


def init_db() -> None:
    """Create tables and ensure the single settings row exists."""
    Base.metadata.create_all(engine)
    _ensure_columns()
    with SessionLocal() as session:
        if session.get(Setting, 1) is None:
            session.add(Setting(id=1))
            session.commit()


def get_db():
    """FastAPI dependency yielding a session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
