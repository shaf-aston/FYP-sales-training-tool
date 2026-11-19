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


def test_pdf_text_is_read_and_all_caps_or_numbered_lines_become_stages():
    stages = build_outline(read_document(pdf(["1. OPENING", "Set the agenda", "Ask about their budget", "2. Close",
                                              "Ask for the sale today"]), "sop.pdf"), "-")
    assert [(s.title, s.steps) for s in stages] == [("OPENING", ["Set the agenda", "Ask about their budget"]),
                                                     ("Close", ["Ask for the sale today"])]


def test_short_bullet_steps_without_full_stops_stay_steps():
    stages = build_outline(read_document(pdf(["Ask about their goals", "Ask about their budget", "Present the offer"]), "sop.pdf"), "Steps")
    assert stages[0].steps == ["Ask about their goals", "Ask about their budget", "Present the offer"]


@pytest.mark.parametrize("text, titles", [
    ("1. Opening\n1.1 Set the agenda\n1.2 Thank them\n2. Discovery\n2.1 Ask about goals", ["Opening", "Discovery"]),
    ("OPENING\nSet the agenda\nDISCOVERY\nAsk about goals", ["OPENING", "DISCOVERY"]),
    ("Step 1: Open\nSet the agenda\nStep 2: Discover\nAsk about goals", ["Step 1: Open", "Step 2: Discover"]),
    ("Sales SOP\nVersion 2.1\nLast updated March\nOpening:\nSet the agenda", ["Opening"]),
])
def test_common_plain_text_layouts_become_stages(text, titles):
    stages = build_outline(read_document(text.encode(), "sop.txt"), "Before")
    assert [s.title for s in stages if s.title != "Before"] == titles
    assert all(not s[:1].isdigit() for st in stages for s in st.steps)   # "1.1" is a list mark, not part of the step


def test_docx_bold_paragraphs_and_outline_levels_are_headings():
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = ('<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Opening</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Set the agenda for the call.</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="berschrift1"/></w:pPr><w:r><w:t>Abschluss</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Ask for the sale.</w:t></w:r></w:p>')
    styles = f'<w:styles {w}><w:style w:styleId="berschrift1"><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style></w:styles>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f"<w:document {w}><w:body>{body}</w:body></w:document>")
        z.writestr("word/styles.xml", styles)
    blocks = read_document(buf.getvalue(), "sop.docx")
    assert [(b.text, b.level > 0) for b in blocks] == [("Opening", True), ("Set the agenda for the call.", False),
                                                       ("Abschluss", True), ("Ask for the sale.", False)]


def test_a_docx_zip_bomb_is_refused_unread(monkeypatch):
    from core.infra import constants

    monkeypatch.setitem(constants.SOP_LIMITS, "max_unzipped_bytes", 1000)
    with pytest.raises(DocumentError) as caught:
        read_document(docx([("x" * 5000, None)]), "sop.docx")
    assert caught.value.code == "too_big"


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


def test_the_sample_sop_reads_and_covers_every_element(client):
    text = client.get("/api/sop/sample").get_json()["text"]
    body = client.post("/api/sop/read", json={"text": text}).get_json()
    assert [s["title"] for s in body["stages"]] == ["Open", "Discover", "Pitch", "Handle objections", "Close"]
    assert body["coverage"] == 100


@pytest.mark.parametrize("step", ["Never discuss pricing on the first call", "Do not take payment on the call",
                                  "Don't ask about budget until they ask", "Close the CRM ticket after the call",
                                  "Offer them a coffee", "Make sure the decision maker is present",
                                  "Reply within 5 minutes of the booking", "Recap their goals in their own words"])
def test_cue_false_positives_cover_nothing_they_should_not(step, fake_embedder):
    covered = {r.id for r in check_elements([Stage("x", [step])], CFG, fake_embedder.embed) if r.covered}
    assert covered <= {"decision", "discovery"}   # only what the words really say (decision maker / their goals)
    assert "pitch" not in covered and "close" not in covered and "opening" not in covered and "follow_up" not in covered


def test_the_sample_follow_up_evidence_is_the_follow_up_step(client):
    text = client.get("/api/sop/sample").get_json()["text"]
    elements = {e["id"]: e for e in client.post("/api/sop/read", json={"text": text}).get_json()["elements"]}
    assert elements["follow_up"]["step"] == "If they're not ready, book a follow-up call before hanging up"


def test_a_conditional_step_only_counts_when_it_happened():
    stages = [Stage("Close", ["Ask them to start today", "If they say it's too expensive, talk about the budget"])]
    result = check_call(stages, ["Shall we start today?"], CFG, topic_embed)
    assert [s.conditional for s in result.steps] == [False, True]
    assert result.score == 100            # the price objection never came up
    both = check_call(stages, ["Shall we start today?", "Let's look at the budget again."], CFG, topic_embed)
    assert both.steps[1].done and both.score == 100


def test_each_sentence_of_a_turn_is_matched_on_its_own():
    stages = [Stage("Open", ["Set the agenda", "Ask about their goal"])]
    result = check_call(stages, ["Thanks for coming. Here's the agenda. What's your goal?"], CFG, topic_embed)
    assert [(s.done, s.said) for s in result.steps] == [(True, "Here's the agenda."), (True, "What's your goal?")]


def test_an_acknowledgement_carries_no_step():
    """Found live: "Fair question." was the evidence that the rep asked them to go ahead."""
    stages = [Stage("Close", ["Ask them directly if they want to go ahead"])]
    result = check_call(stages, ["Fair question. What stopped the last one from working?"], CFG,
                        lambda texts: [[1.0, 0.0] for _ in texts])   # every sentence "means" the step
    assert result.steps[0].said == "What stopped the last one from working?"
