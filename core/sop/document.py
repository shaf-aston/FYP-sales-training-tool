"""SOP file bytes -> blocks: each heading or line of text, with its heading level (0 = not a heading).

Plain text and Markdown are read as they are; DOCX with the standard library (a DOCX is a zip of XML, its headings
are paragraph styles); PDF with pypdf (text only, so headings are guessed from short lines). To read another
format, add a reader to READERS.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from xml.etree import ElementTree

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_MARK = re.compile(r"^\s*(?:[-*•▪◦]|\d+[.)]|[a-z][.)])\s+", re.IGNORECASE)


class DocumentError(ValueError):
    """`code`: unsupported (no reader for the file type) or unreadable (the reader failed or found no text)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Block:
    text: str
    level: int = 0   # 1-6 for a heading, 0 for body text


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _LIST_MARK.sub("", text)).strip()


def _from_text(data: bytes) -> list[Block]:
    blocks = []
    for line in data.decode("utf-8-sig", errors="replace").splitlines():
        if m := _MD_HEADING.match(line.strip()):
            blocks.append(Block(_clean(m.group(2)), len(m.group(1))))
        elif text := _clean(line.replace("**", "")):
            blocks.append(Block(text))
    return blocks


def _from_docx(data: bytes) -> list[Block]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    blocks = []
    for p in root.iter(f"{_W}p"):
        text = _clean("".join(t.text or "" for t in p.iter(f"{_W}t")))
        if not text:
            continue
        style = p.find(f"{_W}pPr/{_W}pStyle")
        name = (style.get(f"{_W}val") or "") if style is not None else ""
        heading = re.match(r"(?i)heading\s*(\d)|title", name)
        blocks.append(Block(text, int(heading.group(1) or 1) if heading else 0))
    return blocks


def _from_pdf(data: bytes) -> list[Block]:
    from pypdf import PdfReader   # only when a PDF arrives

    blocks = []
    for page in PdfReader(io.BytesIO(data)).pages:
        for line in (page.extract_text() or "").splitlines():
            if text := _clean(line):
                # A PDF keeps no styles: a short line with no full stop that opens with a capital reads as a heading.
                looks_heading = len(text.split()) <= 6 and not text.endswith((".", ",", ";", "?")) and text[:1].isupper()
                blocks.append(Block(text, 2 if looks_heading else 0))
    return blocks


READERS: dict[str, Callable[[bytes], list[Block]]] = {
    "txt": _from_text, "md": _from_text, "markdown": _from_text, "docx": _from_docx, "pdf": _from_pdf,
}


def read_document(data: bytes, filename: str) -> list[Block]:
    """The file's blocks. Raises DocumentError("unsupported") or DocumentError("unreadable")."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    reader = READERS.get(ext)
    if reader is None:
        raise DocumentError("unsupported")
    try:
        blocks = reader(data)
    except Exception as e:   # noqa: BLE001 - a broken file of any kind is the same answer
        raise DocumentError("unreadable") from e
    if not blocks:
        raise DocumentError("unreadable")
    return blocks
