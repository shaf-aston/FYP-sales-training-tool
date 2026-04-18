"""Shared stage-mutation helper — used by /api/stage and /api/debug/stage."""

from flask import jsonify


def advance_to_stage(bot, stage: str | None):
    """Validate + advance FSM stage. Returns (response, status_code)."""
    from chatbot.utils import Strategy

    stages = bot.flow_engine.flow_config.get("stages", [])
    if not stage or stage not in stages:
        return jsonify({"error": f"Invalid stage. Available: {stages}"}), 400

    bot.flow_engine.advance(target_stage=stage)

    stage_str = (
        "----"
        if bot.flow_engine.flow_type == Strategy.INTENT
        else bot.flow_engine.current_stage.upper()
    )
    strategy_str = bot.flow_engine.flow_type.upper()
    return jsonify({"success": True, "stage": stage_str, "strategy": strategy_str}), 200
