"""Advanced options panel endpoints — development/testing only"""

from dataclasses import asdict

from flask import Blueprint, jsonify, request

bp = Blueprint("debug", __name__, url_prefix="/api/debug")


def init_routes(app, require_session_func):
    """hook up debug routes"""
    bp.app = app  # type: ignore[attr-defined]
    bp.require_session = require_session_func  # type: ignore[attr-defined]


@bp.route("/config", methods=["GET"])
def debug_config():
    """Return available products and providers for the advanced options dropdowns"""
    from chatbot.loader import load_product_config
    from chatbot.providers.factory import PROVIDERS

    products = load_product_config()["products"]
    return jsonify(
        {
            "products": [
                {"id": k, "strategy": v["strategy"], "label": v.get("context", k)} for k, v in products.items()
            ],
            "providers": list(PROVIDERS.keys()),
        }
    )


@bp.route("/prompt", methods=["GET"])
def debug_prompt():
    """Return the current system prompt exactly as the LLM will receive it"""
    bot, err = bp.require_session()  # type: ignore
    if err:
        return err
    return jsonify(
        {
            "prompt": bot.flow_engine.get_current_prompt(user_message=""),
            "stage": str(bot.flow_engine.current_stage),
            "strategy": str(bot.flow_engine.flow_type),
        }
    )


@bp.route("/stage", methods=["POST"])
def debug_stage():
    """Jump FSM to a specific stage, bypassing advancement rules"""
    bot, err = bp.require_session()  # type: ignore
    if err:
        return err
    data = request.json or {}
    stage = data.get("stage")
    stages = bot.flow_engine.flow_config["stages"]
    if not stage or stage not in stages:
        return jsonify({"error": f"Invalid stage. Available: {stages}"}), 400

    bot.flow_engine.advance(target_stage=stage)

    # Extract bot state
    from chatbot.utils import Strategy

    stage_str = "----" if bot.flow_engine.flow_type == Strategy.INTENT else bot.flow_engine.current_stage.upper()
    strategy_str = bot.flow_engine.flow_type.upper()

    return jsonify({"success": True, "stage": stage_str, "strategy": strategy_str})


@bp.route("/analyse", methods=["POST"])
def debug_analyse():
    """Analyse a message against FSM signals without sending it to the LLM

    Shows intent state, which signal categories match, and whether the
    current stage's advancement rule would fire
    """
    bot, err = bp.require_session()  # type: ignore
    if err:
        return err
    data = request.json or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message required"}), 400

    from chatbot.analysis import analyse_state, user_demands_directness
    from chatbot.content import SIGNALS
    from chatbot.flow import ADVANCEMENT_RULES
    from chatbot.utils import contains_nonnegated_keyword

    history = bot.flow_engine.conversation_history
    state = analyse_state(history, message, signal_keywords=SIGNALS)

    signal_keys = [
        "high_intent",
        "low_intent",
        "commitment",
        "objection",
        "walking",
        "impatience",
        "direct_info_requests",
        "user_consultativeSIGNALS",
        "user_transactionalSIGNALS",
    ]
    msg_lower = message.lower()
    signal_hits = {k: contains_nonnegated_keyword(msg_lower, SIGNALS.get(k, [])) for k in signal_keys}
    signal_hits["demands_directness"] = user_demands_directness(history, message)

    transition = bot.flow_engine.flow_config["transitions"].get(bot.flow_engine.current_stage)
    rule_name = transition.get("advance_on") if transition else None
    would_advance = None
    if rule_name and rule_name in ADVANCEMENT_RULES:
        would_advance = bool(ADVANCEMENT_RULES[rule_name](history, message, bot.flow_engine.stage_turn_count))

    return jsonify(
        {
            "state": asdict(state),
            "signal_hits": signal_hits,
            "advancement": {
                "rule": rule_name,
                "would_advance": would_advance,
                "stage_turns": bot.flow_engine.stage_turn_count,
            },
        }
    )
