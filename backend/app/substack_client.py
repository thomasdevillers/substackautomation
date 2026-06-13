"""Thin client over Substack's private web API for posting Notes.

Substack has no official API. We authenticate with the user's browser session
cookie and call the same private endpoint the web app uses to publish a Note:

    POST {publication}/api/v1/comment/feed

Important: Substack sessions are scoped per-domain. A `connect.sid` grabbed
while logged in to a custom-domain publication (e.g. https://www.tomdev.blog)
authenticates against THAT host, not substack.com. So every request goes to the
configured publication base URL. All reverse-engineered surface lives here, so
if Substack changes it this is the only file to fix.
"""
from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Optional, Tuple

import requests

SUBSTACK_BASE = "https://substack.com"  # only used to build public note links

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Safari/605.1.15"
    ),
}


class SubstackError(Exception):
    """Raised when a Substack request fails (auth, network, or API error)."""


def normalize_base(url: Optional[str]) -> str:
    if not url or not url.strip():
        raise SubstackError(
            "No publication URL configured. Set it in Settings "
            "(e.g. https://www.yourblog.com or https://yourname.substack.com)."
        )
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _parse_cookie_string(cookie_string: str) -> dict:
    jar = SimpleCookie()
    jar.load(cookie_string.strip())
    cookies = {key: morsel.value for key, morsel in jar.items()}
    if not cookies:
        raise SubstackError("Could not parse any cookies from the provided string.")
    if "connect.sid" not in cookies:
        raise SubstackError(
            "Cookie is missing 'connect.sid' (the Substack session). Copy the full "
            "Cookie header from a logged-in request to your publication."
        )
    return cookies


def _build_session(cookie_string: str, base_url: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(_HEADERS)
    session.headers["Origin"] = base_url
    session.headers["Referer"] = base_url + "/home"
    session.cookies.update(_parse_cookie_string(cookie_string))
    return session


def _identify(session: requests.Session, base_url: str) -> Tuple[bool, Optional[str]]:
    """GET the logged-in profile. Returns (authenticated, handle).

    This doubles as a Cloudflare warm-up: any fresh `__cf_bm` cookie returned is
    captured by the session and reused by the subsequent POST, so scheduled
    posts keep working after the originally-pasted cf cookie has expired.
    """
    try:
        resp = session.get(f"{base_url}/api/v1/user/profile/self", timeout=20)
    except requests.RequestException as exc:
        raise SubstackError(f"Network error contacting Substack: {exc}") from exc
    if resp.status_code in (401, 403):
        return False, None
    if resp.status_code != 200:
        raise SubstackError(f"Unexpected response from Substack: HTTP {resp.status_code}")
    try:
        return True, resp.json().get("handle")
    except ValueError:
        return True, None


def verify_cookie(cookie_string: str, base_url: str) -> bool:
    """Return True if the cookie authenticates against the publication."""
    base = normalize_base(base_url)
    session = _build_session(cookie_string, base)
    authed, _ = _identify(session, base)
    return authed


def _body_json(text: str) -> dict:
    """Convert plain note text into Substack's tiptap-style doc.

    Each line becomes its own paragraph (blank lines -> empty paragraphs).
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


def post_note(cookie_string: str, base_url: str, text: str) -> str:
    """Publish a Note and return its public URL. Raises SubstackError on failure."""
    base = normalize_base(base_url)
    session = _build_session(cookie_string, base)

    authed, handle = _identify(session, base)
    if not authed:
        raise SubstackError(
            "Substack rejected the session cookie (expired or not logged in). "
            "Re-paste your cookie in Settings."
        )

    payload = {
        "bodyJson": _body_json(text),
        "tabId": "for-you",
        "surface": "feed",
        "replyMinimumRole": "everyone",
    }
    try:
        resp = session.post(f"{base}/api/v1/comment/feed", json=payload, timeout=30)
    except requests.RequestException as exc:
        raise SubstackError(f"Network error posting note: {exc}") from exc

    if resp.status_code in (401, 403):
        raise SubstackError(
            "Substack rejected the note request (auth/Cloudflare). Re-paste your cookie."
        )
    if resp.status_code not in (200, 201):
        raise SubstackError(
            f"Substack returned HTTP {resp.status_code}: {resp.text[:300]}"
        )

    try:
        comment_id = resp.json().get("id")
    except ValueError:
        comment_id = None
    return _note_url(handle, comment_id)


def _note_url(handle: Optional[str], comment_id) -> str:
    if handle and comment_id:
        return f"{SUBSTACK_BASE}/@{handle}/note/c-{comment_id}"
    if comment_id:
        return f"{SUBSTACK_BASE}/note/c-{comment_id}"
    return f"{SUBSTACK_BASE}/notes"
