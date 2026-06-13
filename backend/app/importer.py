"""Parse an uploaded .txt file into individual note bodies.

Notes are separated by TWO blank lines. A single blank line is kept inside a
note (so a note can have paragraph breaks); only two (or more) consecutive
blank lines start a new note.
"""
from __future__ import annotations

import re
from typing import List

# A line break followed by two or more blank lines separates notes.
_SEPARATOR = re.compile(r"\n(?:[ \t]*\n){2,}")


def parse_notes(text: str) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = _SEPARATOR.split(text)
    return [block.strip() for block in blocks if block.strip()]
