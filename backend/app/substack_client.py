"""Thin client over Substack's private web API for posting Notes.

Substack has no official API. We authenticate with the user's browser session
cookie and call the same private endpoint the web app uses to publish a Note:

    POST https://substack.com/api/v1/comment/feed

The whole reverse-engineered surface is isolated in this file so that if
Substack changes it, this is the only place to fix.
"""
from __future__ import annotations

from http.cookies import SimpleCookie

import requests

SUBSTACK_BASE = "https://substack.com"
NOTE_ENDPOINT = f"{SUBSTACK_BASE}/api/v1/comment/feed"
# Authenticated-only JSON endpoint: 200 when signed in, 401 "Please sign in"
# when the session cookie is anonymous/expired. Used as the connection check.
PROFILE_ENDPOINT = f"{SUBSTACK_BASE}/api/v1/subscriptions"

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": SUBSTACK_BASE,
    "Referer": f"{SUBSTACK_BASE}/notes",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}


class SubstackError(Exception):
    """Raised when a Substack request fails (auth, network, or API error)."""


def _parse_cookie_string(cookie_string: str) -> dict:
    """Parse a 'k=v; k2=v2' cookie header into a dict.

    Accepts either a raw Cookie header copied from the browser or a single
    `connect.sid=...` value.
    """
    jar = SimpleCookie()
    jar.load(cookie_string.strip())
    cookies = {key: morsel.value for key, morsel in jar.items()}
    if not cookies:
        raise SubstackError("Could not parse any cookies from the provided string.")
    return cookies


def _build_session(cookie_string: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(_HEADERS)
    session.cookies.update(_parse_cookie_string(cookie_string))
    return session


def _body_json(text: str) -> dict:
    """Convert plain note text into Substack's tiptap-style doc.

    Each line within the note becomes its own paragraph; blank lines yield
    empty paragraphs (preserving spacing the user typed inside one note).
    """
    content = []
    for line in text.split("\n"):
        line = line.rstrip()
        if line:
            content.append(
                {"type": "paragraph", "content": [{"type": "text", "text": line}]}
            )
        else:
            content.append({"type": "paragraph"})
    if not content:
        content.append({"type": "paragraph"})
    return {"type": "doc", "attrs": {"schemaVersion": "v1"}, "content": content}


def verify_cookie(cookie_string: str) -> bool:
    """Return True if the cookie authenticates against Substack."""
    try:
        session = _build_session(cookie_string)
        resp = session.get(PROFILE_ENDPOINT, timeout=20)
    except requests.RequestException as exc:
        raise SubstackError(f"Network error contacting Substack: {exc}") from exc
    if resp.status_code == 200:
        return True
    if resp.status_code in (401, 403):
        return False
    raise SubstackError(
        f"Unexpected response verifying cookie: HTTP {resp.status_code}"
    )


def post_note(cookie_string: str, text: str) -> str:
    """Publish a Note and return its URL.

    Raises SubstackError on any failure (caller records it on the note).
    """
    payload = {
        "bodyJson": _body_json(text),
        "tabId": "for-you",
        "surface": "feed",
        "replyMinimumRole": "everyone",
    }
    try:
        session = _build_session(cookie_string)
        resp = session.post(NOTE_ENDPOINT, json=payload, timeout=30)
    except requests.RequestException as exc:
        raise SubstackError(f"Network error posting note: {exc}") from exc

    if resp.status_code in (401, 403):
        raise SubstackError(
            "Substack rejected the session cookie (expired or invalid). "
            "Re-enter your cookie in Settings."
        )
    if resp.status_code not in (200, 201):
        raise SubstackError(
            f"Substack returned HTTP {resp.status_code}: {resp.text[:300]}"
        )

    try:
        data = resp.json()
    except ValueError:
        data = {}
    return _extract_note_url(data)


def _extract_note_url(data: dict) -> str:
    """Best-effort extraction of the published note's URL from the response."""
    # Response shapes vary; try the common locations.
    comment_id = (
        data.get("id")
        or data.get("comment", {}).get("id")
        or data.get("item", {}).get("comment", {}).get("id")
    )
    handle = (
        data.get("user", {}).get("handle")
        or data.get("comment", {}).get("user", {}).get("handle")
    )
    if handle and comment_id:
        return f"{SUBSTACK_BASE}/@{handle}/note/c-{comment_id}"
    if comment_id:
        return f"{SUBSTACK_BASE}/note/c-{comment_id}"
    return f"{SUBSTACK_BASE}/notes"  # posted, but URL not parseable
