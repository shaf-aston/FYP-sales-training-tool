"""SOP file bytes -> blocks: each heading or line of text, with its heading level (0 = not a heading).

Plain text and Markdown are read line by line; DOCX with the standard library (a DOCX is a zip of XML); PDF with
pypdf (text only). Headings come from Markdown "#", Word heading styles or outline levels (any language), or, for
lines with no styles, `heading_level`: numbered sections ("2. Discovery", "Step 3: Close"), ALL-CAPS lines and
"Heading:" lines. A plain short line is never guessed to be a heading, so a list of steps is never lost as stages.
Every reader is bounded (unzipped size, pages, characters). To read another format, add a reader to READERS.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from xml.etree import ElementTree

from core.infra.constants import SOP_LIMITS
from core.infra.loader import load_yaml
from core.infra.utils import file_ext

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
# Bullets, "1.", "1.1", "a)" in front of a line: list marks, not part of the step.
_LIST_MARK = re.compile(r"^\s*(?:[-*•▪◦–]|\d+(?:\.\d+)*[.)]?|[a-z][.)])\s+", re.IGNORECASE)
_SECTION = re.compile(r"^(?:(?:step|stage|part|section|phase)\s+\d+\s*[:.\-–]?\s*|\d+[.)]\s+)(\S.*)$", re.IGNORECASE)
_SUBSECTION = re.compile(r"^\d+\.\d+")


class DocumentError(ValueError):
    """`code`: unsupported (no reader for the file type), too_big (unpacks past the limit) or unreadable."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Block:
    text: str
    level: int = 0   # 1-6 for a heading, 0 for body text


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _LIST_MARK.sub("", text)).strip()


def heading_level(line: str) -> int:
    """1 for a line with no styling that reads as a section heading, else 0. Conservative: a step that happens to
    be short stays a step."""
    text = line.strip().rstrip(":").strip()
    words = text.split()
    if not words or len(words) > 8 or text.endswith((".", "?", "!", ",")) or _SUBSECTION.match(text):
        return 0
    section = _SECTION.match(text)
    if section and len(section.group(1).split()) <= 5:
        return 1
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 3 and all(c.isupper() for c in letters):
        return 1
    return 1 if line.strip().endswith(":") and len(words) <= 5 else 0


def _heading_text(line: str) -> str:
    """"2. Discovery" -> "Discovery", "STEP 3: CLOSE" -> "STEP 3: CLOSE" kept as written (minus a trailing colon)."""
    text = line.strip().rstrip(":").strip()
    section = _SECTION.match(text)
    return section.group(1).strip() if section and not text.lower().startswith(("step", "stage", "part", "section", "phase")) else text


def _from_lines(lines: list[str]) -> list[Block]:
    blocks = []
    for raw in lines:
        line = raw.replace("**", "").strip()
        if m := _MD_HEADING.match(line):
            blocks.append(Block(_clean(m.group(2)), len(m.group(1))))
        elif level := heading_level(line):
            blocks.append(Block(_heading_text(line), level))
        elif text := _clean(line):
            blocks.append(Block(text))
    return blocks


def _from_text(data: bytes) -> list[Block]:
    return _from_lines(data.decode("utf-8-sig", errors="replace").splitlines())


def _docx_part(z: zipfile.ZipFile, name: str) -> bytes | None:
    """One XML part, refused before it is read when it would unpack past the limit (a zip bomb)."""
    try:
        info = z.getinfo(name)
    except KeyError:
        return None
    if info.file_size > SOP_LIMITS["max_unzipped_bytes"]:
        raise DocumentError("too_big")
    return z.read(name)


def _style_levels(styles_xml: bytes | None) -> dict[str, int]:
    """Style id -> heading level, from each style's outline level (works whatever language the style names are in)."""
    if not styles_xml:
        return {}
    levels = {}
    for style in ElementTree.fromstring(styles_xml).iter(f"{_W}style"):
        outline = style.find(f"{_W}pPr/{_W}outlineLvl")
        if outline is not None:
            levels[style.get(f"{_W}styleId") or ""] = int(outline.get(f"{_W}val") or 0) + 1
    return levels


def _from_docx(data: bytes) -> list[Block]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        document = _docx_part(z, "word/document.xml")
        styles = _style_levels(_docx_part(z, "word/styles.xml"))
    if document is None:
        raise DocumentError("unreadable")
    blocks = []
    for p in ElementTree.fromstring(document).iter(f"{_W}p"):
        text = _clean("".join(t.text or "" for t in p.iter(f"{_W}t")))
        if not text:
            continue
        style = p.find(f"{_W}pPr/{_W}pStyle")
        name = (style.get(f"{_W}val") or "") if style is not None else ""
        own = p.find(f"{_W}pPr/{_W}outlineLvl")
        level = (int(own.get(f"{_W}val") or 0) + 1 if own is not None else 0) or styles.get(name, 0)
        if not level and (named := re.match(r"(?i)heading\s*(\d)|title", name)):
            level = int(named.group(1) or 1)
        runs = list(p.iter(f"{_W}r"))
        bold = runs and all(r.find(f"{_W}rPr/{_W}b") is not None for r in runs if "".join(t.text or "" for t in r.iter(f"{_W}t")).strip())
        if not level and bold and len(text.split()) <= 8 and not text.endswith((".", "?", "!")):
            level = 2   # a short all-bold paragraph: the heading style many SOPs use instead of Word's
        blocks.append(Block(text, level) if level else (_from_lines([text]) or [Block(text)])[0])
    return blocks


def _from_pdf(data: bytes) -> list[Block]:
    from pypdf import PdfReader   # only when a PDF arrives

    reader = PdfReader(io.BytesIO(data))
    lines, size = [], 0
    for page in reader.pages[: SOP_LIMITS["max_pdf_pages"]]:
        for line in (page.extract_text() or "").splitlines():
            size += len(line)
            if size > SOP_LIMITS["max_text_chars"]:
                return _from_lines(lines)
            lines.append(line)
    return _from_lines(lines)


READERS: dict[str, Callable[[bytes], list[Block]]] = {
    "txt": _from_text, "md": _from_text, "markdown": _from_text, "docx": _from_docx, "pdf": _from_pdf,
}


def read_document(data: bytes, filename: str) -> list[Block]:
    """The file's blocks, without lines that are only document furniture (sop.yaml `skip_lines`: version, owner,
    page numbers). Raises DocumentError("unsupported" / "too_big" / "unreadable")."""
    reader = READERS.get(file_ext(filename) or "txt")
    if reader is None:
        raise DocumentError("unsupported")
    try:
        blocks = reader(data)
    except DocumentError:
        raise
    except Exception as e:   # noqa: BLE001 - a broken file of any kind is the same answer
        raise DocumentError("unreadable") from e
    skip = [re.compile(p, re.IGNORECASE) for p in load_yaml("sop.yaml")["skip_lines"]]
    blocks = [b for b in blocks if not any(p.search(b.text) for p in skip)]
    if not blocks:
        raise DocumentError("unreadable")
    return blocks
