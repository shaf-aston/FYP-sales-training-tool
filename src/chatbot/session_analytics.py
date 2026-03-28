"""Conversation-level analytics — stage transitions, intent classification, objection types.

Tracks metrics that directly support FYP evaluation chapter:
- Stage transitions per session (did users reach pitch/objection?)
- Intent classification distribution (how often is high/medium/low detected?)
- Objection type frequency (which patterns appear most?)
- Strategy switches (initial vs detected strategy, did it change?)
- A/B variant assignment (for prompt testing evaluation)

Complements performance.py (per-turn latency) with conversation-level insights.
"""

import json
import os
import time
import logging
from datetime import datetime
from threading import Lock
from .constants import MAX_ANALYTICS_LINES, ANALYTICS_KEEP_AFTER_ROTATION

logger = logging.getLogger(__name__)

ANALYTICS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'analytics.jsonl')

# File-level lock for thread-safe writes
lock = Lock()

# In-memory line counter — avoids re-reading file on every write
_line_count: int = -1  # -1 = uninitialized, will scan on first write


def _get_line_count() -> int:
    """Get current line count, initializing from file if needed."""
    global _line_count
    if _line_count < 0:
        try:
            if os.path.exists(ANALYTICS_FILE):
                with open(ANALYTICS_FILE, 'r') as f:
                    _line_count = sum(1 for _ in f)
            else:
                _line_count = 0
        except Exception:
            _line_count = 0
    return _line_count


def _increment_line_count() -> None:
    """Increment line count after successful write."""
    global _line_count
    if _line_count >= 0:
        _line_count += 1


def _reset_line_count(new_count: int) -> None:
    """Reset line count after rotation."""
    global _line_count
    _line_count = new_count


class SessionAnalytics:
    """Record conversation-level events for evaluation metrics."""

    @staticmethod
    def record_stage_transition(session_id, from_stage, to_stage, strategy, user_turns_in_stage):
        """Record when FSM advances to a new stage."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "stage_transition",
            "from_stage": from_stage,
            "to_stage": to_stage,
            "strategy": strategy,
            "user_turns_in_stage": user_turns_in_stage
        }
        SessionAnalytics._write_analytics(event)

    @staticmethod
    def record_intent_classification(session_id, intent_level, user_turn_count):
        """Record intent classification on each user turn."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "intent_classification",
            "intent_level": intent_level,  # "low", "medium", "high"
            "user_turn": user_turn_count
        }
        SessionAnalytics._write_analytics(event)

    @staticmethod
    def record_objection_classified(session_id, objection_type, strategy, user_turn_count):
        """Record when an objection is classified at objection stage.

        objection_type: one of "smokescreen", "real", "unknown" from flow.py classify_objection()
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "objection_classified",
            "objection_type": objection_type,
            "strategy": strategy,
            "user_turn": user_turn_count
        }
        SessionAnalytics._write_analytics(event)

    @staticmethod
    def record_strategy_switch(session_id, from_strategy, to_strategy, reason, user_turn_count):
        """Record when FSM strategy changes mid-conversation.

        reason: "impatience_detected", "signal_mismatch", "user_directive", etc.
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "strategy_switch",
            "from_strategy": from_strategy,
            "to_strategy": to_strategy,
            "reason": reason,
            "user_turn": user_turn_count
        }
        SessionAnalytics._write_analytics(event)

    @staticmethod
    def record_session_start(session_id, product_type, initial_strategy, ab_variant=None):
        """Record session initialization with strategy and A/B variant."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "session_start",
            "product_type": product_type,
            "initial_strategy": initial_strategy,
            "ab_variant": ab_variant  # "variant_a", "variant_b", or None
        }
        SessionAnalytics._write_analytics(event)

    @staticmethod
    def record_session_end(session_id, final_stage, final_strategy, user_turn_count, bot_turn_count):
        """Record session completion with final state."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "session_end",
            "final_stage": final_stage,
            "final_strategy": final_strategy,
            "user_turn_count": user_turn_count,
            "bot_turn_count": bot_turn_count
        }
        SessionAnalytics._write_analytics(event)

    @staticmethod
    def record_web_search(session_id: str, query: str, result_count: int, cached: bool) -> None:
        """Record a web search enrichment event for evaluation analytics."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": "web_search",
            "query": query,
            "result_count": result_count,
            "cached": cached,
        }
        SessionAnalytics._write_analytics(event)

    @staticmethod
    def _write_analytics(event):
        """Append analytics event to file with rotation (uses in-memory line count)."""
        with lock:
            try:
                current_count = _get_line_count()

                # Rotate file if it reaches max lines
                if current_count >= MAX_ANALYTICS_LINES and os.path.exists(ANALYTICS_FILE):
                    with open(ANALYTICS_FILE, 'r') as f:
                        lines = f.readlines()
                    keep_lines = lines[-ANALYTICS_KEEP_AFTER_ROTATION:]
                    with open(ANALYTICS_FILE, 'w') as f:
                        f.writelines(keep_lines)
                    _reset_line_count(len(keep_lines))

                # Append event
                with open(ANALYTICS_FILE, 'a') as f:
                    f.write(json.dumps(event) + '\n')
                _increment_line_count()
            except Exception as e:
                logger.warning("Failed to record analytics event: %s", e)

    @staticmethod
    def get_session_analytics(session_id):
        """Retrieve all analytics events for a specific session."""
        events = []
        with lock:
            try:
                with open(ANALYTICS_FILE, 'r') as f:
                    for line in f:
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if event.get("session_id") == session_id:
                            events.append(event)
            except FileNotFoundError:
                pass
        return events

    @staticmethod
    def get_evaluation_summary():
        """Aggregate analytics for evaluation chapter.

        Returns summary statistics:
        - stage_reach_distribution: how many sessions reached each stage
        - intent_distribution: frequency of low/medium/high classifications
        - objection_type_distribution: which objection types appear most
        - strategy_distribution: initial strategy assignments
        - strategy_switch_frequency: how often strategies changed
        - ab_variant_count: distribution across variants (if used)
        """
        summary = {
            "stage_reach": {},
            "intent_distribution": {"low": 0, "medium": 0, "high": 0},
            "objection_types": {},
            "initial_strategy": {},
            "strategy_switches": 0,
            "ab_variants": {},
            "total_sessions": 0,
            "sessions_reached_pitch": 0,
            "sessions_reached_objection": 0
        }

        with lock:
            try:
                with open(ANALYTICS_FILE, 'r') as f:
                    sessions = {}
                    for line in f:
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        session_id = event.get("session_id")
                        event_type = event.get("event_type")

                        # Track session lifecycle
                        if session_id not in sessions:
                            sessions[session_id] = {"stages": set(), "variant": None}

                        if event_type == "session_start":
                            summary["total_sessions"] += 1
                            initial_strat = event.get("initial_strategy", "unknown")
                            summary["initial_strategy"][initial_strat] = summary["initial_strategy"].get(initial_strat, 0) + 1
                            variant = event.get("ab_variant")
                            if variant:
                                summary["ab_variants"][variant] = summary["ab_variants"].get(variant, 0) + 1
                            sessions[session_id]["variant"] = variant

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

                    # Count stage reach
                    for session_stages in sessions.values():
                        if "pitch" in session_stages["stages"]:
                            summary["sessions_reached_pitch"] += 1
                        if "objection" in session_stages["stages"]:
                            summary["sessions_reached_objection"] += 1

            except FileNotFoundError:
                pass

        return summary
