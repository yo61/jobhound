"""Shared HTML→text helper for extractors.

Turns an HTML fragment (a job-description body) into readable plain text,
converting block-level tags to line breaks so words aren't glued together
across boundaries (e.g. "need<br>Interview" must not become "needInterview").
"""

from __future__ import annotations

import html as html_lib
import re

# Tags that imply a line break in the rendered body.
_BLOCK_TAG_RE = re.compile(r"</?(?:br|p|div|li|ul|ol|h[1-6]|tr)\b[^>]*>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def clean_html_text(fragment: str) -> str:
    """Strip HTML to text, turning block tags into line breaks."""
    text = _BLOCK_TAG_RE.sub("\n", fragment)
    text = _TAG_RE.sub("", text)
    text = html_lib.unescape(text)
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    return _BLANK_LINES_RE.sub("\n\n", text).strip()
