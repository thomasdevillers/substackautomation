"""JSON API routes for settings, import, notes, and posting."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select

from .db import get_db
from .importer import parse_notes
from .models import Note, Setting, utcnow
from .scheduler import auto_spread, next_available_slots
from .security import decrypt_cookie, encrypt_cookie, require_auth
from .substack_client import SubstackError, post_note, verify_cookie

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


# ----------------------------- helpers -------------------------------------
def _to_naive_utc(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt  # assume already UTC
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _normalize_slot_times(raw: str) -> str:
    """Validate/clean a comma-separated 'HH:MM,HH:MM' string."""
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        h, _, m = part.partition(":")
        out.append(f"{int(h):02d}:{int(m):02d}")  # raises ValueError if invalid
    return ",".join(out)


# ----------------------------- settings ------------------------------------
class SettingsUpdate(BaseModel):
    session_cookie: Optional[str] = None  # raw cookie; write-only
    timezone: Optional[str] = None
    default_post_time: Optional[str] = None
    default_cadence_days: Optional[int] = None
    slot_times: Optional[str] = None  # comma-separated HH:MM
    publication_url: Optional[str] = None


def _check_connection(setting: Setting) -> bool:
    if not setting.session_cookie_enc or not setting.publication_url:
        return False
    try:
        return verify_cookie(decrypt_cookie(setting.session_cookie_enc), setting.publication_url)
    except (SubstackError, ValueError):
        return False


@router.get("/settings")
def get_settings_route(db=Depends(get_db)):
    setting = db.get(Setting, 1)
    return {**setting.to_public_dict(), "connected": _check_connection(setting)}


@router.put("/settings")
def update_settings_route(payload: SettingsUpdate, db=Depends(get_db)):
    setting = db.get(Setting, 1)
    if payload.session_cookie is not None:
        cookie = payload.session_cookie.strip()
        if cookie:
            setting.session_cookie_enc = encrypt_cookie(cookie)
        else:
            setting.session_cookie_enc = None
    if payload.timezone is not None:
        setting.timezone = payload.timezone
    if payload.default_post_time is not None:
        setting.default_post_time = payload.default_post_time
    if payload.default_cadence_days is not None:
        setting.default_cadence_days = max(1, payload.default_cadence_days)
    if payload.slot_times is not None:
        cleaned = _normalize_slot_times(payload.slot_times)
        if cleaned:
            setting.slot_times = cleaned
    if payload.publication_url is not None:
        setting.publication_url = payload.publication_url.strip() or None
    db.commit()
    return {**setting.to_public_dict(), "connected": _check_connection(setting)}


# ------------------------------ import -------------------------------------
@router.post("/import")
async def import_notes_route(file: UploadFile = File(...), db=Depends(get_db)):
    raw = (await file.read()).decode("utf-8", errors="replace")
    bodies = parse_notes(raw)
    if not bodies:
        raise HTTPException(status_code=400, detail="No notes found in file.")

    setting = db.get(Setting, 1)
    # Reserve the next free daily slots, continuing after anything already
    # scheduled, so imported notes are auto-scheduled (no manual approval).
    slots = next_available_slots(len(bodies), setting.slot_list(), setting.timezone)

    max_order = db.scalar(select(func.coalesce(func.max(Note.order_index), 0)))
    created = []
    for i, (body, slot) in enumerate(zip(bodies, slots), start=1):
        note = Note(
            body=body,
            status="scheduled",
            scheduled_at=slot,
            order_index=max_order + i,
        )
        db.add(note)
        created.append(note)
    db.commit()
    return {
        "imported": len(created),
        "timezone": setting.timezone,
        "slot_times": setting.slot_times,
        "notes": [n.to_dict() for n in created],
    }


# ------------------------------- notes -------------------------------------
class NoteUpdate(BaseModel):
    body: Optional[str] = None
    scheduled_at: Optional[str] = None  # ISO string, or null to clear


class NoteCreate(BaseModel):
    body: str


class ApprovePayload(BaseModel):
    note_ids: List[int]


class AutoSpreadPayload(BaseModel):
    note_ids: List[int]
    start_date: str   # YYYY-MM-DD
    time_of_day: str  # HH:MM
    cadence_days: int = 1
    timezone: str = "UTC"


@router.get("/notes")
def list_notes_route(status: Optional[str] = None, db=Depends(get_db)):
    stmt = select(Note)
    if status:
        stmt = stmt.where(Note.status == status)
    stmt = stmt.order_by(Note.scheduled_at.is_(None), Note.scheduled_at, Note.order_index)
    return [n.to_dict() for n in db.scalars(stmt)]


@router.post("/notes")
def create_note_route(payload: NoteCreate, db=Depends(get_db)):
    max_order = db.scalar(select(func.coalesce(func.max(Note.order_index), 0)))
    note = Note(body=payload.body, status="draft", order_index=max_order + 1)
    db.add(note)
    db.commit()
    return note.to_dict()


@router.patch("/notes/{note_id}")
def update_note_route(note_id: int, payload: NoteUpdate, db=Depends(get_db)):
    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    if payload.body is not None:
        note.body = payload.body
    # `scheduled_at` present in the payload (even null) means "set it".
    fields = payload.model_dump(exclude_unset=True)
    if "scheduled_at" in fields:
        note.scheduled_at = _to_naive_utc(payload.scheduled_at)
    db.commit()
    return note.to_dict()


@router.post("/notes/approve")
def approve_notes_route(payload: ApprovePayload, db=Depends(get_db)):
    missing_time = []
    approved = 0
    for note_id in payload.note_ids:
        note = db.get(Note, note_id)
        if note is None or note.status not in ("draft", "failed"):
            continue
        if note.scheduled_at is None:
            missing_time.append(note_id)
            continue
        note.status = "scheduled"
        note.error = None
        approved += 1
    db.commit()
    if missing_time:
        raise HTTPException(
            status_code=400,
            detail=f"These notes need a scheduled time first: {missing_time}",
        )
    return {"approved": approved}


@router.post("/notes/auto-spread")
def auto_spread_route(payload: AutoSpreadPayload, db=Depends(get_db)):
    auto_spread(
        payload.note_ids,
        payload.start_date,
        payload.time_of_day,
        payload.cadence_days,
        payload.timezone,
    )
    notes = [db.get(Note, nid).to_dict() for nid in payload.note_ids if db.get(Note, nid)]
    return {"updated": len(notes), "notes": notes}


@router.post("/notes/{note_id}/post-now")
def post_now_route(note_id: int, db=Depends(get_db)):
    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    setting = db.get(Setting, 1)
    if not setting or not setting.session_cookie_enc:
        raise HTTPException(status_code=400, detail="No Substack cookie configured.")
    if not setting.publication_url:
        raise HTTPException(status_code=400, detail="No publication URL configured (see Settings).")
    try:
        cookie = decrypt_cookie(setting.session_cookie_enc)
        url = post_note(cookie, setting.publication_url, note.body)
    except (SubstackError, ValueError) as exc:
        note.status = "failed"
        note.error = str(exc)
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc))
    note.status = "posted"
    note.posted_at = utcnow().replace(tzinfo=None)
    note.substack_note_url = url
    note.error = None
    db.commit()
    return note.to_dict()


@router.delete("/notes/{note_id}")
def delete_note_route(note_id: int, db=Depends(get_db)):
    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()
    return {"deleted": note_id}
