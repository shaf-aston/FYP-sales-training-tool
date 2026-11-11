"""core/sop and /api/sop: read an SOP (text, Markdown, DOCX, PDF), check it covers a good call, check a call against it."""
import io
import zipfile

import pytest

from core.infra.loader import CONFIG_DIR, load_yaml
from core.sop.adherence import check_call
from core.sop.checklist import check_elements
from core.sop.document import DocumentError, read_document
from core.sop.outline import Stage, build_outline

CFG = load_yaml("sop.yaml")

SOP_MD = b"""# Discovery call SOP
Intro line before the first stage.

## Open
- Introduce yourself and set the agenda for the next 30 minutes

## Discover
1. Ask the prospect what their main goal is this year
2. Find out what's stopping them and how long it has been a problem
3. Ask who else signs off on the purchase

## Pitch and close
- Present the 12-week programme linked to the goals they gave
- If they say it's too expensive, acknowledge it and reframe around ROI
- Ask them directly if they want to go ahead
- If they're not ready, book a follow-up in the calendar before hanging up
- Update the CRM
"""


def docx(paragraphs: list[tuple[str, str | None]]) -> bytes:
    """A minimal real .docx: (text, style) paragraphs."""
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = "".join(
        f"<w:p>{f'<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>' if style else ''}<w:r><w:t>{text}</w:t></w:r></w:p>"
        for text, style in paragraphs
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f"<w:document {w}><w:body>{body}</w:body></w:document>")
    return buf.getvalue()


def pdf(lines: list[str]) -> bytes:
    """A minimal real one-page PDF with these lines of text."""
    text = " ".join(f"({line}) Tj 0 -20 Td" for line in lines)
    stream = f"BT /F1 12 Tf 50 750 Td {text} ET".encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
               b"<< /Length %d >>stream\n" % len(stream) + stream + b"\nendstream",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offsets))
    out.write(b"trailer << /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objects) + 1, xref))
    return out.getvalue()


def test_markdown_headings_are_stages_and_lines_are_steps():
    stages = build_outline(read_document(SOP_MD, "sop.md"), CFG["untitled_stage"])
    assert [s.title for s in stages] == [CFG["untitled_stage"], "Open", "Discover", "Pitch and close"]
    assert stages[2].steps[0] == "Ask the prospect what their main goal is this year"   # list marks dropped


def test_docx_headings_come_from_paragraph_styles():
    blocks = read_document(docx([("Sales SOP", "Title"), ("Open", "Heading1"), ("Set the agenda", None),
                                 ("Close", "Heading1"), ("Ask for the sale", None)]), "sop.docx")
    stages = build_outline(blocks, "-")
    assert [(s.title, s.steps) for s in stages] == [("Open", ["Set the agenda"]), ("Close", ["Ask for the sale"])]


def test_pdf_text_is_read_and_short_capitalised_lines_become_headings():
    stages = build_outline(read_document(pdf(["Open", "Set the agenda for the call.", "Close", "Ask for the sale today."]), "sop.pdf"), "-")
    assert [(s.title, s.steps) for s in stages] == [("Open", ["Set the agenda for the call."]), ("Close", ["Ask for the sale today."])]


@pytest.mark.parametrize("data, name, code", [
    (b"x", "sop.pptx", "unsupported"),
    (b"not a zip", "sop.docx", "unreadable"),
    (b"   \n\n", "sop.txt", "unreadable"),
])
def test_unusable_files_say_why(data, name, code):
    with pytest.raises(DocumentError) as caught:
        read_document(data, name)
    assert caught.value.code == code


def test_a_long_paragraph_becomes_one_step_per_sentence(monkeypatch):
    monkeypatch.setitem(__import__("core.infra.constants", fromlist=["SOP_LIMITS"]).SOP_LIMITS, "max_step_chars", 40)
    stages = build_outline(read_document(b"Ask about their goals first. Then ask about their budget.", "a.txt"), "Steps")
    assert stages[0].steps == ["Ask about their goals first.", "Then ask about their budget."]


def test_the_checklist_reads_cues_and_names_what_is_missing(fake_embedder):
    stages = build_outline(read_document(SOP_MD, "sop.md"), CFG["untitled_stage"])
    results = {r.id: r for r in check_elements(stages, CFG, fake_embedder.embed)}
    assert {k for k, r in results.items() if r.covered} == \
        {"opening", "discovery", "pain", "decision", "pitch", "objections", "close", "follow_up"}
    assert not results["urgency"].covered and results["urgency"].why
    assert results["decision"].step == "Ask who else signs off on the purchase"


def test_a_step_with_no_cue_covers_nothing_by_default(fake_embedder):
    results = check_elements([Stage("Admin", ["Update the CRM", "Log the call notes"])], CFG, fake_embedder.embed)
    assert not any(r.covered for r in results)


def topic_embed(texts):
    """A controlled embedder: one dimension per topic word; the query prefix is ignored."""
    topics = ["agenda", "goal", "budget", "start", "weather"]
    return [[1.0 if t in text.lower() else 0.0 for t in topics] + [0.01] for text in texts]


def test_adherence_marks_each_step_with_the_line_that_did_it():
    stages = [Stage("Open", ["Set the agenda"]), Stage("Discover", ["Ask about their goal", "Ask about their budget"]),
              Stage("Close", ["Ask them to start today"])]
    lines = ["Here's the agenda for today.", "What's your main goal?", "Shall we start today?"]
    result = check_call(stages, lines, CFG, topic_embed)
    assert [(s.step, s.done, s.turn) for s in result.steps] == [
        ("Set the agenda", True, 1), ("Ask about their goal", True, 2), ("Ask about their budget", False, None),
        ("Ask them to start today", True, 3)]
    assert result.score == 75 and result.in_order


def test_adherence_notices_steps_done_out_of_order():
    stages = [Stage("Open", ["Set the agenda"]), Stage("Close", ["Ask them to start"])]
    result = check_call(stages, ["Shall we start?", "Quick agenda first."], CFG, topic_embed)
    assert result.score == 100 and not result.in_order


# --- routes (the offline bag-of-words embedder stands in for the model) ---

def test_read_an_sop_file_or_text(client):
    by_file = client.post("/api/sop/read", data={"file": (io.BytesIO(SOP_MD), "sop.md")}, content_type="multipart/form-data")
    by_text = client.post("/api/sop/read", json={"text": SOP_MD.decode()})
    for response in (by_file, by_text):
        body = response.get_json()
        assert response.status_code == 200 and body["coverage"] == round(100 * 8 / 9)
        assert [e["id"] for e in body["elements"]][0] == "opening"


@pytest.mark.parametrize("payload, code", [({"text": ""}, "SOP_UNREADABLE"), ({}, "SOP_UNREADABLE")])
def test_read_errors(client, payload, code):
    response = client.post("/api/sop/read", json=payload)
    assert response.status_code == 400 and response.get_json()["code"] in (code, "SOP_EMPTY")


def test_check_a_call_against_the_outline(client):
    stages = client.post("/api/sop/read", json={"text": SOP_MD.decode()}).get_json()["stages"]
    call = (CONFIG_DIR / "calls_sample.txt").read_text("utf-8")
    body = client.post("/api/sop/check", json={"stages": stages, "call": {"text": call}}).get_json()
    assert body["rep"] == "Sarah Khan" and 0 <= body["score"] <= 100
    assert len(body["steps"]) == sum(len(s["steps"]) for s in stages)


@pytest.mark.parametrize("stages", [None, [], [{"title": "x", "steps": "nope"}], [{"title": "x", "steps": [""]}]])
def test_check_needs_a_valid_outline(client, stages):
    response = client.post("/api/sop/check", json={"stages": stages, "call": {"text": "A: hi"}})
    assert response.status_code == 400 and response.get_json()["code"] == "SOP_OUTLINE_INVALID"
