"""Background scheduler that posts due notes, plus scheduling helpers.

Substack has no server-side scheduling, so this in-process scheduler is what
actually fires notes at their chosen time. A catch-up pass runs on startup so a
restart/redeploy never silently drops an overdue note.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from typing import List

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from .db import SessionLocal
from .models import Note, Setting, utcnow
from .security import decrypt_cookie
from .substack_client import SubstackError, post_note

log = logging.getLogger("scheduler")

scheduler = BackgroundScheduler(timezone="UTC")


def _post_due_notes() -> None:
    """Post every scheduled note whose time has arrived."""
    with SessionLocal() as db:
        setting = db.get(Setting, 1)
        due = list(
            db.scalars(
                select(Note)
                .where(Note.status == "scheduled")
                .where(Note.scheduled_at <= utcnow().replace(tzinfo=None))
                .order_by(Note.scheduled_at)
            )
        )
        if not due:
            return

        if not setting or not setting.session_cookie_enc or not setting.publication_url:
            for note in due:
                note.status = "failed"
                note.error = "Substack not configured: set the session cookie and publication URL in Settings."
            db.commit()
            log.warning("%d notes due but Substack not configured", len(due))
            return

        try:
            cookie = decrypt_cookie(setting.session_cookie_enc)
        except ValueError as exc:
            for note in due:
                note.status = "failed"
                note.error = str(exc)
            db.commit()
            return

        for note in due:
            try:
                url = post_note(cookie, setting.publication_url, note.body)
                note.status = "posted"
                note.posted_at = utcnow().replace(tzinfo=None)
                note.substack_note_url = url
                note.error = None
                log.info("Posted note %s -> %s", note.id, url)
            except SubstackError as exc:
                # Mark failed; do not retry automatically. Surfaced in the UI.
                note.status = "failed"
                note.error = str(exc)
                log.error("Failed to post note %s: %s", note.id, exc)
            db.commit()


def run_catch_up() -> None:
    """Called once at startup to immediately post anything overdue."""
    log.info("Running startup catch-up pass")
    _post_due_notes()


def start_scheduler() -> None:
    scheduler.add_job(
        _post_due_notes,
        trigger="interval",
        seconds=60,
        id="post_due_notes",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info("Scheduler started (60s interval)")


def next_available_slots(count: int, slot_times: List[str], tz_name: str) -> List[datetime]:
    """Return the next `count` free posting slots as naive-UTC datetimes.

    Slots are the given daily times (e.g. 09:00, 15:00) in tz_name. A slot is
    skipped if it is already in the past or already occupied by a scheduled
    note, so repeated imports keep flowing into the next free days.
    """
    tz = pytz.timezone(tz_name)
    now_local = datetime.now(tz)

    times = sorted(
        (int(h), int(m)) for h, m in (t.split(":") for t in slot_times)
    )
    if not times:
        times = [(9, 0), (15, 0)]

    with SessionLocal() as db:
        occupied = {
            dt for dt in db.scalars(
                select(Note.scheduled_at)
                .where(Note.status == "scheduled")
                .where(Note.scheduled_at.is_not(None))
            )
        }

    slots: List[datetime] = []
    day = now_local.date()
    guard = 0
    while len(slots) < count and guard < 3650:  # cap ~10 years
        guard += 1
        for hour, minute in times:
            local_dt = tz.localize(datetime.combine(day, time(hour, minute)))
            if local_dt <= now_local:
                continue
            utc_naive = local_dt.astimezone(timezone.utc).replace(tzinfo=None)
            if utc_naive in occupied:
                continue
            slots.append(utc_naive)
            occupied.add(utc_naive)
            if len(slots) >= count:
                break
        day += timedelta(days=1)
    return slots


def auto_spread(
    note_ids: List[int],
    start_date: str,
    time_of_day: str,
    cadence_days: int,
    tz_name: str,
) -> None:
    """Assign scheduled_at (stored naive UTC) across days for the given notes.

    start_date: 'YYYY-MM-DD', time_of_day: 'HH:MM', both in tz_name.
    Notes are scheduled in the order their ids are given.
    """
    tz = pytz.timezone(tz_name)
    base_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    hour, minute = (int(x) for x in time_of_day.split(":"))
    cadence = max(1, cadence_days)

    with SessionLocal() as db:
        for offset, note_id in enumerate(note_ids):
            note = db.get(Note, note_id)
            if note is None:
                continue
            local_dt = tz.localize(
                datetime.combine(
                    base_date + timedelta(days=offset * cadence),
                    time(hour, minute),
                )
            )
            note.scheduled_at = local_dt.astimezone(timezone.utc).replace(tzinfo=None)
        db.commit()
