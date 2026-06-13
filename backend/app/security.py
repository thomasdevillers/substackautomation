"""Cookie encryption at rest and the dashboard password gate."""
from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Header, HTTPException, status

from .config import get_settings

settings = get_settings()


def _fernet() -> Fernet:
    # Derive a stable 32-byte Fernet key from SECRET_KEY.
    digest = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_cookie(raw: str) -> str:
    return _fernet().encrypt(raw.encode()).decode()


def decrypt_cookie(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:  # SECRET_KEY changed or data corrupted
        raise ValueError(
            "Stored cookie could not be decrypted. Re-enter it in Settings "
            "(this usually means SECRET_KEY changed)."
        ) from exc


def require_auth(authorization: Optional[str] = Header(default=None)) -> None:
    """FastAPI dependency enforcing the shared app password (HTTP Basic).

    No-op when APP_PASSWORD is unset (localhost dev only).
    """
    expected = settings.app_password
    if not expected:
        return

    if not authorization or not authorization.lower().startswith("basic "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    try:
        decoded = base64.b64decode(authorization.split(" ", 1)[1]).decode()
        _, _, password = decoded.partition(":")
    except Exception:
        password = ""

    if not secrets.compare_digest(password, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
