"""Drama 3 delivery cues: performed by Fish, never shown on screen.

Mave's text can contain plain-language directions like ``[softly, amused]`` or
``[small laugh]``. The TTS path keeps them; the caption path strips them.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterable

# A cue is a short bracketed span on one line. Longer spans are left alone so real
# bracketed text (rare in speech) is not eaten.
_MAX_CUE = 80
CUE_RE = re.compile(r"\s?\[[^\[\]\n]{1," + str(_MAX_CUE) + r"}\]")


def strip_cues(text: str) -> str:
    out = CUE_RE.sub("", text)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.lstrip() if text[:1] == "[" else out


async def strip_cues_stream(chunks: AsyncIterable[str]) -> AsyncIterable[str]:
    """Streaming version: holds back text only while a ``[`` is still open."""
    buf = ""
    started = False
    async for chunk in chunks:
        buf += str(chunk)
        open_at = buf.rfind("[")
        if open_at != -1 and "]" not in buf[open_at:] and len(buf) - open_at <= _MAX_CUE:
            ready, buf = buf[:open_at], buf[open_at:]
        else:
            ready, buf = buf, ""
        if ready:
            cleaned = strip_cues(ready)
            if not started:
                cleaned = cleaned.lstrip()
            if cleaned:
                started = True
                yield cleaned
    if buf:
        cleaned = strip_cues(buf)
        if cleaned:
            yield cleaned if started else cleaned.lstrip()
