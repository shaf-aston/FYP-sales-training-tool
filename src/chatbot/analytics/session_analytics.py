"""Conversation-level analytics — stage transitions, intent classification, objection types.

Tracks metrics that directly support FYP evaluation chapter:
- Stage transitions per session (did users reach pitch/objection?)
- Intent classification distribution (how often is high/medium/low detected?)
- Objection type frequency (which patterns appear most?)
- Strategy switches (initial vs detected strategy, did it change?)
- A/B variant assignment (for prompt testing evaluation)

Complements performance.py (per-turn latency) with conversation-level insights.
"""

import os
import logging
from datetime import datetime
from ..constants import MAX_ANALYTICS_LINES, ANALYTICS_KEEP_AFTER_ROTATION
from .jsonl_store import JSONLWriter

logger = logging.getLogger(__name__)

ANALYTICS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'analytics.jsonl')

_writer = JSONLWriter(ANALYTICS_FILE, MAX_ANALYTICS_LINES, ANALYTICS_KEEP_AFTER_ROTATION)


class SessionAnalytics:
    """Record conversation-level events for evaluation metrics."""

    @staticmethod
    def record_stage_transition(session_id, from_stage, to_stage, strategy, user_turns_in_stage):
        _writer.append({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "stage_transition",
            "from_stage": from_stage,
            "to_stage": to_stage,
            "strategy": strategy,
            "user_turns_in_stage": user_turns_in_stage,
        })

    @staticmethod
    def record_intent_classification(session_id, intent_level, user_turn_count):
        _writer.append({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "intent_classification",
            "intent_level": intent_level,
            "user_turn": user_turn_count,
        })

    @staticmethod
    def record_objection_classified(session_id, objection_type, strategy, user_turn_count):
        _writer.append({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "objection_classified",
            "objection_type": objection_type,
            "strategy": strategy,
            "user_turn": user_turn_count,
        })

    @staticmethod
    def record_strategy_switch(session_id, from_strategy, to_strategy, reason, user_turn_count):
        _writer.append({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "strategy_switch",
            "from_strategy": from_strategy,
            "to_strategy": to_strategy,
            "reason": reason,
            "user_turn": user_turn_count,
        })

    @staticmethod
    def record_session_start(session_id, product_type, initial_strategy, ab_variant=None):
        _writer.append({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "session_start",
            "product_type": product_type,
            "initial_strategy": initial_strategy,
            "ab_variant": ab_variant,
        })

    @staticmethod
    def record_session_end(session_id, final_stage, final_strategy, user_turn_count, bot_turn_count):
        _writer.append({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "session_end",
            "final_stage": final_stage,
            "final_strategy": final_strategy,
            "user_turn_count": user_turn_count,
            "bot_turn_count": bot_turn_count,
        })

    @staticmethod
    def record_web_search(session_id: str, query: str, result_count: int, cached: bool) -> None:
        _writer.append({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "web_search",
            "query": query,
            "result_count": result_count,
            "cached": cached,
        })

    @staticmethod
    def get_session_analytics(session_id):
        """Retrieve all analytics events for a specific session."""
        return _writer.read_filtered("session_id", session_id)

    @staticmethod
    def get_evaluation_summary():
        """Aggregate analytics for evaluation chapter."""
        summary = {
            "stage_reach": {},
            "intent_distribution": {"low": 0, "medium": 0, "high": 0},
            "objection_types": {},
            "initial_strategy": {},
            "strategy_switches": 0,
            "ab_variants": {},
            "total_sessions": 0,
            "sessions_reached_pitch": 0,
            "sessions_reached_objection": 0,
        }

        sessions: dict = {}
        for event in _writer.read_all():
            session_id = event.get("session_id")
            event_type = event.get("event_type")

            if session_id not in sessions:
                sessions[session_id] = {"stages": set()}

            if event_type == "session_start":
                summary["total_sessions"] += 1
                strat = event.get("initial_strategy", "unknown")
                summary["initial_strategy"][strat] = summary["initial_strategy"].get(strat, 0) + 1
                variant = event.get("ab_variant")
                if variant:
                    summary["ab_variants"][variant] = summary["ab_variants"].get(variant, 0) + 1

            elif event_type == "stage_transition":
                to_stage = event.get("to_stage")
                sessions[session_id]["stages"].add(to_stage)
                summary["stage_reach"][to_stage] = summary["stage_reach"].get(to_stage, 0) + 1

            elif event_type == "intent_classification":
                intent = event.get("intent_level", "unknown")
                if intent in summary["intent_distribution"]:
                    summary["intent_distribution"][intent] += 1

            elif event_type == "objection_classified":
                obj_type = event.get("objection_type", "unknown")
                summary["objection_types"][obj_type] = summary["objection_types"].get(obj_type, 0) + 1

            elif event_type == "strategy_switch":
                summary["strategy_switches"] += 1

        for s in sessions.values():
            if "pitch" in s["stages"]:
                summary["sessions_reached_pitch"] += 1
            if "objection" in s["stages"]:
                summary["sessions_reached_objection"] += 1

        return summary
