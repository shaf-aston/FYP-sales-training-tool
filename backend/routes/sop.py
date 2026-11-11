"""SOP endpoints (/api/sop): read a team's sales SOP and check it covers a good call, and check a real call against it.

Stateless: the SOP comes with the first request and its outline with the second; nothing is stored. Meaning is matched
with buy mode's shared local embedding model, handed to core/sop as a function so core never imports a mode.
"""

from flask import Blueprint, jsonify, request

from core.calls.errors import CallError
from core.calls.reader import read_call
from core.infra.constants import MAX_REQUEST_BYTES, SOP_LIMITS
from core.infra.loader import CONFIG_DIR, load_yaml
from core.sop.adherence import check_call
from core.sop.checklist import check_elements
from core.sop.document import DocumentError, read_document
from core.sop.outline import Stage, build_outline

from ..messages import SOP_EMPTY, SOP_OUTLINE_INVALID, SOP_UNREADABLE, SOP_UNSUPPORTED
from ..security import require_rate_limit
from ._utils import json_body
from .calls import call_error

bp = Blueprint("sop", __name__, url_prefix="/api/sop")

SAMPLE_FILE = "sop_sample.md"   # in config/: the SOP behind "Try a sample SOP"


def _embed(texts: list[str]) -> list[list[float]]:
    from core.buy_mode.script_engine import seller   # looked up per call: tests swap in a fake embedder

    return seller.shared_embedder().embed(texts)


def _outline_json(stages: list[Stage]) -> list[dict]:
    return [{"title": s.title, "steps": s.steps} for s in stages]


def _stages_from(data) -> list[Stage] | None:
    """The outline the web sends back (from /read, maybe edited), checked; None when it is the wrong shape."""
    if not isinstance(data, list) or not 0 < len(data) <= SOP_LIMITS["max_stages"]:
        return None
    stages = []
    for item in data:
        steps = item.get("steps") if isinstance(item, dict) else None
        title = item.get("title") if isinstance(item, dict) else None
        if not isinstance(title, str) or not isinstance(steps, list) or len(steps) > SOP_LIMITS["max_steps_per_stage"] \
                or not all(isinstance(s, str) and 0 < len(s.strip()) <= SOP_LIMITS["max_step_chars"] for s in steps):
            return None
        stages.append(Stage(title.strip()[:SOP_LIMITS["max_step_chars"]], [s.strip() for s in steps]))
    return stages if any(s.steps for s in stages) else None


@bp.route("/sample", methods=["GET"])
def sample():
    """A realistic SOP to try the review without one of your own."""
    return jsonify({"success": True, "text": (CONFIG_DIR / SAMPLE_FILE).read_text("utf-8"), "filename": SAMPLE_FILE})


@bp.route("/read", methods=["POST"])
@require_rate_limit("sop")
def read():
    """An SOP (multipart `file`, or JSON `text`) -> its stages and steps, and which elements of a good call it covers."""
    request.max_content_length = SOP_LIMITS["max_bytes"] + MAX_REQUEST_BYTES
    upload = request.files.get("file")
    try:
        if upload is not None and upload.filename:
            blocks = read_document(upload.read(), upload.filename)
        else:
            text = json_body().get("text")
            blocks = read_document(text.encode("utf-8"), "sop.txt") if isinstance(text, str) and text.strip() else []
    except DocumentError as e:
        return jsonify({"error": SOP_UNSUPPORTED if e.code == "unsupported" else SOP_UNREADABLE, "code": f"SOP_{e.code.upper()}"}), 400
    cfg = load_yaml("sop.yaml")
    stages = build_outline(blocks, cfg["untitled_stage"])
    if not stages:
        return jsonify({"error": SOP_EMPTY, "code": "SOP_EMPTY"}), 400
    elements = check_elements(stages, cfg, _embed)
    return jsonify({
        "success": True,
        "stages": _outline_json(stages),
        "elements": [e.__dict__ for e in elements],
        "coverage": round(100 * sum(e.covered for e in elements) / len(elements)),
    })


@bp.route("/check", methods=["POST"])
@require_rate_limit("sop")
def check():
    """A call (`call`: {text, rep?}, like /api/calls/read) against an SOP outline (`stages`, from /read): which steps
    the rep carried out, where, and whether in order."""
    data = json_body()
    stages = _stages_from(data.get("stages"))
    if stages is None:
        return jsonify({"error": SOP_OUTLINE_INVALID, "code": "SOP_OUTLINE_INVALID"}), 400
    call = data.get("call") if isinstance(data.get("call"), dict) else {}
    text, rep = call.get("text"), call.get("rep")
    try:
        reading = read_call(text if isinstance(text, str) else "", rep if isinstance(rep, str) and rep.strip() else None)
    except CallError as e:
        return call_error(e)
    rep_lines = [h["content"] for h in reading.history() if h["role"] == "user"]
    return jsonify({"success": True, "rep": reading.roles.rep, **check_call(stages, rep_lines, load_yaml("sop.yaml"), _embed).to_json()})
