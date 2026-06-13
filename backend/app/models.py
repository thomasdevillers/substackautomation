"""SQLAlchemy ORM models for notes and settings."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# Note lifecycle:
#   draft     -> imported / created, not yet approved
#   scheduled -> approved with a scheduled_at; the scheduler will post it
#   posted    -> successfully posted to Substack
#   failed    -> a post attempt errored (see `error`)
class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    substack_note_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        def iso(dt: Optional[datetime]) -> Optional[str]:
            # Stored naive in UTC; tag as UTC on the way out.
            return dt.replace(tzinfo=timezone.utc).isoformat() if dt else None

        return {
            "id": self.id,
            "body": self.body,
            "status": self.status,
            "scheduled_at": iso(self.scheduled_at),
            "posted_at": iso(self.posted_at),
            "substack_note_url": self.substack_note_url,
            "error": self.error,
            "order_index": self.order_index,
            "created_at": iso(self.created_at),
        }


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Fernet-encrypted Substack session cookie string. Never returned to client.
    session_cookie_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Africa/Johannesburg")
    default_post_time: Mapped[str] = mapped_column(String(5), nullable=False, default="09:00")
    default_cadence_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Comma-separated daily times (HH:MM) used to auto-schedule imported notes.
    slot_times: Mapped[str] = mapped_column(String(128), nullable=False, default="09:00,15:00")
    publication_url: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    def slot_list(self) -> list[str]:
        return [t.strip() for t in self.slot_times.split(",") if t.strip()]

    def to_public_dict(self) -> dict:
        """Settings safe to expose to the client (no raw cookie)."""
        return {
            "has_cookie": bool(self.session_cookie_enc),
            "timezone": self.timezone,
            "default_post_time": self.default_post_time,
            "default_cadence_days": self.default_cadence_days,
            "slot_times": self.slot_times,
            "publication_url": self.publication_url,
        }
