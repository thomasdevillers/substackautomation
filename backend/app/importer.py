"""Parse an uploaded .txt file into individual note bodies.

Notes are separated by a blank line (one or more empty/whitespace-only lines).
A note may itself span multiple lines.
"""
from __future__ import annotations

import re
from typing import List

# One or more blank lines (possibly containing whitespace) separates notes.
_SEPARATOR = re.compile(r"\n[ \t]*\n+")


def parse_notes(text: str) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = _SEPARATOR.split(text)
    return [block.strip() for block in blocks if block.strip()]
