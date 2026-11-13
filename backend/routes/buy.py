"""Buy mode endpoints (/api/buy): the learner is the customer, the AI (SellerBot) sells.

Session start and end, chat, edit, the coach's Q&A and the stage/move quiz.
"""

import logging

from flask import Blueprint, current_app, jsonify, request

from core.buy_mode.coach import COACH_STYLES, DEFAULT_STYLE
from core.infra.constants import MAX_MESSAGE_LENGTH, MAX_SELLER_SESSIONS
from core.infra import embedder as meaning_model
from core.infra.loader import CONFIG_DIR
from core.training.quiz import get_quiz_question
from core.buy_mode.seller_bot import SellerBot
from core.buy_mode.script_engine import rep_words
from core.buy_mode.script_engine.seller import method_for, products as script_products, resolve_product
from core.calls.errors import CallError
from core.calls.reader import read_call
from core.sop.spoken import as_question
from core.infra.utils import new_session_id

from ..messages import (
    COACH_FAILED,
    EDIT_NOT_ALLOWED, EDIT_FAILED,
    FIELD_REQUIRED,
    GENERIC_ERROR,
    INVALID_INDEX,
    INVALID_STEP,
    LABEL_TOO_LONG,
    MISSING_INDEX,
    QUESTION_REQUIRED,
    QUESTION_TOO_LONG,
    REP_WORDS_INVALID,
    REP_WORDS_SOURCE,
    REWIND_FAILED,
    SELLER_INIT_FAILED,
    SERVER_FULL,
)
from ..security import InputValidator, require_rate_limit
from .calls import call_error
from .sop import stages_from
from ._utils import (
    history_json,
    json_body,
    safe_latency_ms,
    stage_fields,
    text_field,
    validate_message,
    validate_provider,
    with_session,
)

logger = logging.getLogger(__name__)

bp = Blueprint("buy", __name__, url_prefix="/api/buy")


# --- session start and end ---


@bp.route("/products", methods=["GET"])
def products():
    """What the rep can sell: pass an `id` as `product_type` to /init to start a call selling it."""
    return jsonify({"success": True, "products": script_products()})


@bp.route("/init", methods=["POST"])
@require_rate_limit("buy_init")
def init():
    """Start a session (the seller is built now, so the first message doesn't wait), or reattach to a live one."""
    data = json_body()
    existing_id = data.get("session_id")
    sellers = current_app.extensions["sessions"].seller

    # Restore existing session only if it is still in memory on this process. Otherwise start a new one from the
    # product, words and label sent with the id (the client sends this tab's choice, for a call the server forgot).
    if existing_id:
        session_error = InputValidator.validate_session_id(existing_id)
        if session_error:
            return session_error
        seller = sellers.get(existing_id)
        if seller:
            history = history_json(seller.call.conversation_history)
            current_app.logger.info(f"Restored session: {existing_id} ({len(history)} messages)")
            return jsonify(
                {
                    "success": True,
                    "session_id": existing_id,
                    "message": None,
                    "product_type": seller.product_type,
                    "words": seller.words or {},
                    "words_label": getattr(seller, "words_label", ""),
                    "probes": getattr(seller, "probes", {}),
                    **stage_fields(seller),
                    "history": history,
                    "training": seller.coach_notes(),   # the coach's notes come back with the call after a reload
                }
            )

    if not sellers.can_create():
        current_app.logger.warning(f"Session cap ({MAX_SELLER_SESSIONS}) reached - rejecting new init")
        return jsonify({"error": SERVER_FULL}), 503

    session_id = new_session_id()
    product_type = data.get("product_type")  # unlisted or missing: script/engine.yaml default_product
    if not isinstance(product_type, str):
        product_type = None
    provider, provider_error = validate_provider(data)
    if provider_error:
        return provider_error

    words = data.get("words")   # {step id: question}: the rep says a top rep's or an SOP's words (see /words)
    try:
        seller = SellerBot(provider_type=provider, product_type=product_type, session_id=session_id, words=words or None,
                           probes=data.get("probes") or None)   # {step: question}: those steps asked again in their words
        seller.words_label = rep_words.clean_label(data.get("label")) if seller.words else ""   # whose words, for the card
        sellers.set(session_id, seller)
        current_app.logger.info(
            f"New session: {session_id} (product={seller.product_type}, provider={seller.provider_name})"
        )
    except rep_words.RepWordsError:
        return jsonify({"error": REP_WORDS_INVALID, "code": "REP_WORDS_INVALID"}), 400
    except Exception as init_error:
        current_app.logger.exception(f"Seller init failed: {init_error}")
        return jsonify({"error": SELLER_INIT_FAILED}), 500

    opening = seller.script_opening()
    seller.open_with(opening)

    return jsonify(
        {
            "success": True,
            "session_id": session_id,
            "message": opening,
            "product_type": seller.product_type,
            "words": seller.words or {},   # the questions said in someone else's words, by step
            "words_label": seller.words_label,   # whose they are ("Maya", "your SOP"), as the client named them
            "probes": seller.probes,   # the same steps asked again in their words
            **stage_fields(seller),
            "history": [],
            "training": seller.coach_notes(),  # the web app reads coach notes under this key
        }
    )


# The samples behind "Try a sample" in the Rep's words tool (in config/): a top rep's call and an SOP for this offer.
WORDS_SAMPLES = {"call": "rep_words_sample_call.txt", "sop": "rep_words_sample_sop.md"}


@bp.route("/words/sample", methods=["GET"])
def words_sample():
    """A sample source for the rep's words: `?source=call` (a top rep's discovery call) or `sop`."""
    name = WORDS_SAMPLES.get(request.args.get("source", "call"), WORDS_SAMPLES["call"])
    return jsonify({"success": True, "text": (CONFIG_DIR / name).read_text("utf-8"), "filename": name})


@bp.route("/words", methods=["POST"])
@require_rate_limit("calls")
def words():
    """Which of the script's questions the rep can ask in someone else's words: a top rep's, from a real call
    (`call`: {text, rep?}, as /api/calls/read), or an SOP's (`stages`, from /api/sop/read). Stateless; pass the
    chosen ones to /init as `words` ({step: theirs})."""
    data = json_body()
    product = resolve_product(data.get("product_type"))
    call, stages, rep = data.get("call"), data.get("stages"), None
    if isinstance(call, dict) and isinstance(call.get("text"), str) and call["text"].strip():
        named = call.get("rep")
        try:
            reading = read_call(call["text"], named if isinstance(named, str) and named.strip() else None)
        except CallError as e:
            return call_error(e)
        rep = reading.roles.rep
        lines = [h["content"] for h in reading.history() if h["role"] == "user"]
    elif (outline := stages_from(stages)) is not None:
        lines = [as_question(step) or step for stage in outline for step in stage.steps]   # "Ask what ..." -> "What ...?"
    else:
        return jsonify({"error": REP_WORDS_SOURCE, "code": "REP_WORDS_SOURCE"}), 400
    questions = rep_words.questions_in(lines)
    method = method_for(product)
    matches = rep_words.match(method, questions, meaning_model.shared_embedder().embed)   # looked up per call: tests swap it
    return jsonify({
        "success": True,
        "product_type": product,
        "rep": rep,
        "questions": len(questions),
        "steps": len(rep_words.askable(method)),
        "matches": [m.__dict__ for m in matches],
    })


@bp.route("/reset", methods=["POST"])
@with_session("seller")
def reset(seller):
    """Delete the current session"""
    # Telemetry must never be the reason a learner cannot end their session.
    try:
        seller.record_session_end()
    except Exception:
        logger.exception("Could not record the end of this session")
    current_app.extensions["sessions"].seller.delete(request.headers.get("X-Session-ID"))
    return jsonify({"success": True})


# --- the conversation ---


@bp.route("/chat", methods=["POST"])
@require_rate_limit("buy_chat")
@with_session("seller")
def chat(seller):
    """The learner's message; the AI seller answers."""
    data = request.get_json(silent=True) or {}
    user_message, error = validate_message(data.get("message", ""))
    if error:
        return error

    try:
        response = seller.chat(user_message)
        return jsonify(
            {
                "success": True,
                "message": response.content,
                **stage_fields(seller),
                "latency_ms": safe_latency_ms(response.latency_ms),
                "provider": response.provider,
                "model": response.model,
                "training": seller.coach_notes(),
            }
        )
    except Exception as e:
        current_app.logger.exception(f"Chat error: {e}")
        return jsonify({"error": GENERIC_ERROR}), 500


@bp.route("/steps", methods=["GET"])
@with_session("seller")
def steps(seller):
    """The script steps a learner can jump to (to test one step)."""
    return jsonify({"success": True, "steps": seller.seller.steps()})


@bp.route("/stage-starts", methods=["GET"])
@with_session("seller")
def stages(seller):
    """Where a jump to each stage lands, with the answers taken as given before it (the recap card)."""
    return jsonify({"success": True, "stages": seller.stage_starts()})


def _jump_slots(raw, allowed):
    """The recap card's answers: only the slots the card offered, as short plain strings."""
    if not isinstance(raw, dict):
        return {}
    return {k: str(v).strip()[:200] for k, v in raw.items() if k in allowed and isinstance(v, str) and v.strip()}


@bp.route("/jump", methods=["POST"])
@require_rate_limit("buy_chat")
@with_session("seller")
def jump(seller):
    """Start the call again at one script step: a fresh call. `slots` (optional): the answers taken as given
    before it, so the seller's first line builds on them."""
    data = request.get_json(silent=True) or {}
    step = str(data.get("step") or "")
    allowed = {r["slot"] for st in seller.stage_starts() if st["step"] == step for r in st["recap"]}
    try:
        message = seller.jump_to(step, _jump_slots(data.get("slots"), allowed))
    except ValueError:
        return jsonify({"error": INVALID_STEP}), 400
    except Exception:
        current_app.logger.exception("Jump failed")
        return jsonify({"error": GENERIC_ERROR}), 500
    return jsonify({"success": True, "message": message, "history": history_json(seller.call.conversation_history),
                    **stage_fields(seller), "training": seller.coach_notes()})


@bp.route("/edit", methods=["POST"])
@require_rate_limit("buy_chat")
@with_session("seller")
def edit(seller):
    """Edit a learner message and replay the call from there."""
    data = json_body()
    message_index = data.get("index")
    new_message, error = validate_message(data.get("message", ""))
    if error:
        return error

    if message_index is None:
        return jsonify({"error": MISSING_INDEX}), 400
    try:
        message_index = int(message_index)
    except (TypeError, ValueError, OverflowError):   # 1e400 is a float too big for int
        return jsonify({"error": INVALID_INDEX}), 400

    try:
        response = seller.edit_turn(message_index, new_message)
        if response is None:
            return jsonify({"error": REWIND_FAILED}), 500
        return jsonify(
            {
                "success": True,
                "message": response.content,
                "history": history_json(seller.call.conversation_history),
                **stage_fields(seller),
                "latency_ms": safe_latency_ms(response.latency_ms),
                "provider": response.provider,
                "model": response.model,
                "training": seller.coach_notes(),
            }
        )
    except ValueError as e:
        current_app.logger.info(f"Edit refused: {e}")
        return jsonify({"error": EDIT_NOT_ALLOWED}), 400
    except Exception as e:
        current_app.logger.exception(f"Edit error: {e}")
        return jsonify({"error": EDIT_FAILED}), 500


@bp.route("/coach", methods=["POST"])
@require_rate_limit("buy_chat")
@with_session("seller")
def coach(seller):
    """Answer the learner's question about the call and sales technique."""
    data = json_body()
    question = text_field(data, "question")
    style = text_field(data, "style").lower() or DEFAULT_STYLE
    if style not in COACH_STYLES:
        style = DEFAULT_STYLE
    if not question:
        return jsonify({"error": QUESTION_REQUIRED}), 400
    if len(question) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": QUESTION_TOO_LONG}), 400

    try:
        return jsonify({"success": True, **seller.answer_coach_question(question, style=style)})
    except Exception as e:
        current_app.logger.exception(f"Coach answer error: {e}")
        return jsonify({"error": COACH_FAILED}), 500


# --- quiz: where is the AI seller in its script, and what should it do next ---


@bp.route("/quiz/question", methods=["GET"])
@with_session("seller")
def quiz_question(seller):
    """A random question for the quiz type in ?type= (stage, next-move, direction)."""
    quiz_type = request.args.get("type", "stage")
    return jsonify(
        {
            "success": True,
            "question": get_quiz_question(quiz_type),
            "type": quiz_type,
            **stage_fields(seller),
        }
    )


def _required_text(field: str, label: str):
    """A stripped required text field from the JSON body, or an error response."""
    value = text_field(json_body(), field)
    if not value:
        return None, (jsonify({"error": FIELD_REQUIRED.format(label=label)}), 400)
    if len(value) > MAX_MESSAGE_LENGTH:
        return None, (jsonify({"error": LABEL_TOO_LONG.format(label=label)}), 400)
    return value, None


@bp.route("/quiz/stage", methods=["POST"])
@with_session("seller")
def quiz_stage(seller):
    """Stage identification quiz (scored by rule)."""
    answer, error = _required_text("answer", "Answer")
    if error:
        return error
    return jsonify({"success": True, **seller.score_stage_answer(answer), **stage_fields(seller)})


@bp.route("/quiz/next-move", methods=["POST"])
@with_session("seller")
def quiz_next_move(seller):
    """Next move quiz (rules score it, the AI may add wording)."""
    response, error = _required_text("response", "Response")
    if error:
        return error
    return jsonify({"success": True, **seller.score_next_move(response), **stage_fields(seller)})


@bp.route("/quiz/direction", methods=["POST"])
@with_session("seller")
def quiz_direction(seller):
    """Direction quiz (rules score it, the AI may add wording)."""
    explanation, error = _required_text("explanation", "Explanation")
    if error:
        return error
    return jsonify({"success": True, **seller.score_direction(explanation), **stage_fields(seller)})
