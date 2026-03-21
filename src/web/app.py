from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import sys
import secrets
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from chatbot.chatbot import SalesChatbot
from chatbot.providers import get_available_providers
from chatbot.performance import PerformanceTracker
from chatbot.session_analytics import SessionAnalytics
from chatbot.content import generate_init_greeting
from chatbot.loader import QuickMatcher
from chatbot.knowledge import (
    load_custom_knowledge, save_custom_knowledge,
    clear_custom_knowledge, ALLOWED_FIELDS, MAX_FIELD_LENGTH,
)

# Security module (centralized security controls)
from web.security import (
    SecurityConfig,
    RateLimiter,
    PromptInjectionValidator,
    SecurityHeadersMiddleware,
    InputValidator,
    SessionSecurityManager,
    ClientIPExtractor,
    initialize_security,
    require_rate_limit,
)

# Disable .pyc file generation
sys.dont_write_bytecode = True

# Initialize Flask app
app = Flask(__name__)

# CORS: restrict to configured origins (default: Render deployment + localhost dev).
# Override via ALLOWED_ORIGINS env var (comma-separated) for other deployments.
_allowed_origins = [
    o.strip() for o in
    os.environ.get('ALLOWED_ORIGINS', 'https://fyp-sales-training-tool.onrender.com,http://localhost:5000').split(',')
    if o.strip()
]
CORS(app, origins=_allowed_origins)

# ─── Security Initialization ─────────────────────────────────────────────────

# Initialize security components (from security module)
rate_limiter, session_manager, injection_validator = initialize_security(
    app_logger=app.logger
)

# Wire security middleware
app.after_request(SecurityHeadersMiddleware.apply)
session_manager.start_background_cleanup()


# ─── Prospect Session Management ───────────────────────────────────────────────
# Use a second SessionSecurityManager instance for prospect sessions (eliminates code duplication)
prospect_session_manager = SessionSecurityManager(
    max_sessions=100,  # Lower limit than main chat sessions
    idle_minutes=30,
    cleanup_interval=SecurityConfig.CLEANUP_INTERVAL_SECONDS,
)
prospect_session_manager.start_background_cleanup()


# ─── Request helpers ─────────────────────────────────────────────────────────

def _validate_message(text: str):
    """Validate and sanitize message text. Returns (clean_text, error_response)."""
    return InputValidator.validate_message(
        text.strip(),
        injection_validator=injection_validator,
        max_length=SecurityConfig.MAX_MESSAGE_LENGTH
    )


def _bot_state(bot: SalesChatbot) -> dict:
    """Extract common bot state fields for JSON responses.

    Returns:
        dict: {"stage": str, "strategy": str}
    """
    # In discovery mode (intent strategy), stage is unset since real flow isn't determined yet
    # Once switched to consultative/transactional, show actual stage
    stage = "----" if bot.flow_engine.flow_type == "intent" else bot.flow_engine.current_stage.upper()
    strategy = bot.flow_engine.flow_type.upper()

    return {
        "stage": stage,
        "strategy": strategy
    }


# ─── Session helpers ─────────────────────────────────────────────────────────

def cleanup_expired_sessions():
    """Remove sessions idle > SESSION_IDLE_MINUTES. Called lazily by HTTP requests."""
    session_manager.cleanup_expired()


def get_session(session_id):
    """Get chatbot, updating timestamp. Returns bot or None."""
    return session_manager.get(session_id)


def set_session(session_id, chatbot):
    """Store chatbot in memory."""
    session_manager.set(session_id, chatbot)


def delete_session(session_id):
    """Remove session from memory."""
    session_manager.delete(session_id)


def require_session():
    """Validate session header and return (bot, error_response).

    Returns:
        (bot, None) if valid session exists
        (None, error_response) if missing or invalid
    """
    session_id = request.headers.get('X-Session-ID')
    if not session_id:
        return None, (jsonify({"error": "Session ID required"}), 400)
    bot = get_session(session_id)
    if not bot:
        return None, (jsonify({"error": "Session not found", "code": "SESSION_EXPIRED"}), 400)
    return bot, None


# ─── App startup ─────────────────────────────────────────────────────────────

# Page routes

@app.route('/favicon.ico')
def favicon():
    return ('', 204)


@app.route('/')
def home():
    """Serve the chat interface"""
    return render_template('index.html')


@app.route('/knowledge')
def knowledge_page():
    """Serve the knowledge base management page."""
    return render_template('knowledge.html')


# ─── Session lifecycle API ───────────────────────────────────────────────────

@app.route('/api/init', methods=['POST'])
@require_rate_limit('init')
def api_init():
    """Initialize or restore session. Creates bot eagerly to avoid first-message latency."""
    data = request.json or {}
    existing_id = data.get('session_id')

    # Restore existing session if still alive on server
    if existing_id:
        bot = get_session(existing_id)
        if not bot:
            # Try loading from disk if not in memory
            bot = SalesChatbot.load_session(existing_id)
            if bot:
                set_session(existing_id, bot)
                app.logger.info(f"Restored session from disk: {existing_id}")
        if bot:
            history = [{"role": m["role"], "content": m["content"]}
                       for m in bot.flow_engine.conversation_history]
            app.logger.info(f"Restored session: {existing_id} ({len(history)} messages)")
            return jsonify({
                "success": True,
                "session_id": existing_id,
                "message": None,
                **_bot_state(bot),
                "history": history
            })

    # Session count ceiling: reject new sessions when server is full
    if not session_manager.can_create():
        app.logger.warning(
            f"Session cap ({SecurityConfig.MAX_SESSIONS}) reached — rejecting new init"
        )
        return jsonify({"error": "Server at capacity. Please try again later."}), 503

    # Create new session with eager bot initialistion
    session_id = secrets.token_hex(16)
    product_type = data.get('product_type')  # None → generic default → intent-first discovery
    user_message = data.get('user_message', '')
    provider = data.get('provider', "groq")

    # Auto-detect product from user message if not explicitly provided
    if (not product_type or product_type == 'default') and user_message:
        detected_product, confidence = QuickMatcher.match_product(user_message)
        if detected_product and confidence >= 0.7:
            product_type = detected_product
            app.logger.info(f"Auto-detected product: {product_type} (confidence: {confidence:.2f})")

    try:
        bot = SalesChatbot(provider_type=provider, product_type=product_type, session_id=session_id)
        # Dev: override strategy, skipping intent-detection phase entirely
        force_strategy = data.get('force_strategy')
        if force_strategy in ("consultative", "transactional"):
            bot.flow_engine._initial_flow_type = force_strategy
            bot.flow_engine.switch_strategy(force_strategy)
        set_session(session_id, bot)
        app.logger.info(f"New session: {session_id} (product={product_type}, strategy={bot.flow_engine.flow_type}, provider={provider})")
    except Exception as init_error:
        app.logger.exception(f"Bot init failed: {init_error}")
        return jsonify({"error": f"Init failed: {str(init_error)}"}), 500

    # Generate greeting and training data from content.py — synced with STRATEGY_PROMPTS
    init_data = generate_init_greeting(bot.flow_engine.flow_type)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "message": init_data["message"],
        **_bot_state(bot),
        "history": [],
        "training": init_data["training"],
    })


@app.route('/api/restore', methods=['POST'])
def api_restore():
    """Rebuild bot from client-side history after server session loss.

    Accepts full conversation history from localStorage, replays into fresh bot
    to reconstruct FSM state without any LLM calls.
    """
    data = request.json or {}
    history = data.get('history', [])  # [{role, content}, ...]
    product_type = data.get('product_type')  # None → generic default → intent-first discovery
    provider = data.get('provider', "groq")

    session_id = secrets.token_hex(16)

    try:
        bot = SalesChatbot(provider_type=provider, product_type=product_type, session_id=session_id)

        # Replay history into bot — reconstructs FSM state and strategy switches
        if history:
            bot.replay(history)

        set_session(session_id, bot)
        app.logger.info(f"Restored session: {session_id} ({len(history)} messages replayed)")

    except Exception as e:
        app.logger.exception(f"Restore failed: {e}")
        return jsonify({"error": f"Restore failed: {str(e)}"}), 500

    return jsonify({
        "success": True,
        "session_id": session_id,
        **_bot_state(bot),
    })


@app.route('/api/health', methods=['GET'])
def api_health():
    """Health check: provider availability and performance stats"""
    session_id = request.headers.get('X-Session-ID')

    # Get active provider info
    active_provider = None
    active_model = None
    if session_id:
        bot = get_session(session_id)
        if bot:
            active_provider = bot._provider_name
            active_model = bot._model_name

    # Get available providers
    provider_status = get_available_providers()

    # Get aggregate performance stats
    perf_stats = PerformanceTracker.get_provider_stats()

    return jsonify({
        "ok": True,
        "active": {
            "provider": active_provider,
            "model": active_model
        },
        "available_providers": provider_status,
        "performance_stats": perf_stats
    })


@app.route('/api/config', methods=['GET'])
def api_config():
    """Expose system configuration metadata for frontend synchronization.

    Returns configuration limits, available products, and strategies
    so the frontend can validate input and guide users appropriately.
    """
    from chatbot.loader import load_product_config

    config = load_product_config()
    products = config.get('products', {})

    return jsonify({
        "ok": True,
        "limits": {
            "max_message_length": SecurityConfig.MAX_MESSAGE_LENGTH,
            "max_field_length": SecurityConfig.MAX_FIELD_LENGTH,
            "max_sessions": SecurityConfig.MAX_SESSIONS,
        },
        "rate_limits": {
            "init": {"requests": SecurityConfig.RATE_LIMITS["init"][0], "window_seconds": SecurityConfig.RATE_LIMITS["init"][1]},
            "chat": {"requests": SecurityConfig.RATE_LIMITS["chat"][0], "window_seconds": SecurityConfig.RATE_LIMITS["chat"][1]},
        },
        "products": {
            "available": list(products.keys()),
            "default": "default",
        },
        "strategies": ["consultative", "transactional", "intent"],
    })


@app.route('/api/reset', methods=['POST'])
def reset():
    """Delete the current session."""
    bot, err = require_session()
    if err: return err
    
    session_id = request.headers.get('X-Session-ID')
    delete_session(session_id)
    return jsonify({"success": True})


# ─── Conversation API ─────────────────────────────────────────────────────────

@app.route('/api/chat', methods=['POST'])
@require_rate_limit('chat')
def chat():
    """Handle chat messages. Bot must be initialized via /api/init first."""
    data = request.json
    user_message, err = _validate_message(data.get('message', ''))
    if err:
        return err

    bot, err = require_session()
    if err: return err

    try:
        response = bot.chat(user_message)
        training = bot.generate_training(user_message, response.content)

        # Extract content and metrics from ChatResponse
        return jsonify({
            "success": True,
            "message": response.content,
            **_bot_state(bot),
            "latency_ms": round(response.latency_ms, 1),
            "provider": response.provider,
            "model": response.model,
            "metrics": {
                "input_length": response.input_len,
                "output_length": response.output_len
            },
            "training": training,
        })

    except Exception as e:
        app.logger.exception(f"Chat error: {e}")
        return jsonify({"error": f"Chat error: {str(e)}"}), 500


@app.route('/api/edit', methods=['POST'])
def edit_message():
    """Edit user message and regenerate from that point"""
    data = request.json or {}
    msg_index = data.get('index')
    new_message, err = _validate_message(data.get('message', ''))

    bot, bot_err = require_session()
    if bot_err: return bot_err

    if err: return err

    # Validate inputs
    if msg_index is None:
        return jsonify({"error": "Missing message index"}), 400

    try:
        msg_index = int(msg_index)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid index format"}), 400

    # Validate index is within bounds
    max_index = len(bot.flow_engine.conversation_history) - 1
    if msg_index < 0 or msg_index > max_index:
        return jsonify({"error": f"Invalid index. Valid range: 0-{max_index}"}), 400

    try:
        # Rewind to turn BEFORE the edit, then replay with new message
        turn_index = msg_index // 2  # Convert message index to turn index
        if not bot.rewind_to_turn(turn_index):
            return jsonify({"error": "Rewind failed"}), 500

        response = bot.chat(new_message)
        training = bot.generate_training(new_message, response.content)

        return jsonify({
            "success": True,
            "message": response.content,
            "history": [{"role": m["role"], "content": m["content"]} for m in bot.flow_engine.conversation_history],
            **_bot_state(bot),
            "latency_ms": round(response.latency_ms, 1),
            "provider": response.provider,
            "model": response.model,
            "training": training,
        })
    except Exception as e:
        return jsonify({"error": f"Edit error: {str(e)}"}), 500


@app.route('/api/summary', methods=['GET'])
def get_summary():
    """Get conversation summary"""
    bot, err = require_session()
    if err: return err

    return jsonify({
        "success": True,
        "summary": bot.get_conversation_summary()
    })


# ─── Training API ─────────────────────────────────────────────────────────────

@app.route('/api/training/ask', methods=['POST'])
def training_ask():
    """Answer a trainee's question about the conversation and sales techniques."""
    bot, err = require_session()
    if err: return err

    data = request.json or {}
    question = (data.get('question') or '').strip()
    if not question:
        return jsonify({"error": "Question required"}), 400
    if len(question) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Question too long"}), 400

    try:
        result = bot.answer_training_question(question)
        return jsonify({"success": True, **result})
    except Exception as e:
        app.logger.exception(f"Training Q&A error: {e}")
        return jsonify({"error": "Failed to generate answer"}), 500


# ─── Quiz/Assessment API ─────────────────────────────────────────────────────

@app.route('/api/quiz/question', methods=['GET'])
def quiz_get_question():
    """Get a quiz question for the specified type."""
    bot, err = require_session()
    if err: return err

    quiz_type = request.args.get('type', 'stage')
    from chatbot.quiz import get_quiz_question
    question = get_quiz_question(quiz_type)

    return jsonify({
        "success": True,
        "question": question,
        "type": quiz_type,
        **_bot_state(bot),
    })


@app.route('/api/quiz/stage', methods=['POST'])
def quiz_stage():
    """Stage identification quiz (deterministic evaluation)."""
    bot, err = require_session()
    if err: return err

    data = request.json or {}
    answer = (data.get('answer') or '').strip()
    if not answer:
        return jsonify({"error": "Answer required"}), 400
    if len(answer) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Answer too long"}), 400

    from chatbot.quiz import evaluate_stage_quiz
    result = evaluate_stage_quiz(answer, bot)

    return jsonify({"success": True, **result, **_bot_state(bot)})


@app.route('/api/quiz/next-move', methods=['POST'])
def quiz_next_move():
    """Next move quiz (LLM-evaluated comparison)."""
    bot, err = require_session()
    if err: return err

    data = request.json or {}
    response = (data.get('response') or '').strip()
    if not response:
        return jsonify({"error": "Response required"}), 400
    if len(response) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Response too long"}), 400

    # Get last user message from history for context
    history = bot.flow_engine.conversation_history
    last_user_msg = ""
    for msg in reversed(history):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    from chatbot.quiz import evaluate_next_move_quiz
    result = evaluate_next_move_quiz(response, bot, last_user_msg)

    return jsonify({"success": True, **result, **_bot_state(bot)})


@app.route('/api/quiz/direction', methods=['POST'])
def quiz_direction():
    """Direction/strategy quiz (LLM-evaluated understanding check)."""
    bot, err = require_session()
    if err: return err

    data = request.json or {}
    explanation = (data.get('explanation') or '').strip()
    if not explanation:
        return jsonify({"error": "Explanation required"}), 400
    if len(explanation) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Explanation too long"}), 400

    from chatbot.quiz import evaluate_direction_quiz
    result = evaluate_direction_quiz(explanation, bot)

    return jsonify({"success": True, **result, **_bot_state(bot)})


# ─── Knowledge API ───────────────────────────────────────────────────────────

@app.route('/api/knowledge', methods=['GET'])
def get_knowledge():
    """Retrieve current custom knowledge."""
    return jsonify({"success": True, "data": load_custom_knowledge()})


@app.route('/api/knowledge', methods=['POST'])
def save_knowledge_route():
    """Save custom knowledge data with field-level validation."""
    data = request.json

    # Validate knowledge data (type checking, field whitelisting, length limits)
    error = InputValidator.validate_knowledge_data(
        data,
        allowed_fields=ALLOWED_FIELDS,
        max_field_length=MAX_FIELD_LENGTH
    )
    if error:
        return error

    success = save_custom_knowledge(data)
    return jsonify({"success": success})


@app.route('/api/knowledge', methods=['DELETE'])
def clear_knowledge_route():
    """Clear all custom knowledge."""
    success = clear_custom_knowledge()
    return jsonify({"success": success})


# ─── Dev/Debug API ───────────────────────────────────────────────────────────
# These endpoints exist for developer testing only.
# They expose internal FSM state and prompt content — do not expose in production.
# Guard: set ENABLE_DEBUG_PANEL=true in .env for local dev; leave unset on deployment.

_DEBUG_ENABLED = os.environ.get('ENABLE_DEBUG_PANEL', '').lower() == 'true'

@app.before_request
def _guard_debug_endpoints():
    if request.path.startswith('/api/debug/') and not _DEBUG_ENABLED:
        return jsonify({"error": "Debug endpoints disabled"}), 403


@app.route('/api/debug/config', methods=['GET'])
def debug_config():
    """Return available products and providers for the dev panel dropdowns."""
    from chatbot.providers.factory import PROVIDERS
    from chatbot.loader import load_product_config
    products = load_product_config()["products"]
    return jsonify({
        "products": [
            {"id": k, "strategy": v["strategy"], "label": v.get("context", k)}
            for k, v in products.items()
        ],
        "providers": list(PROVIDERS.keys()),
    })


@app.route('/api/debug/prompt', methods=['GET'])
def debug_prompt():
    """Return the current system prompt exactly as the LLM will receive it."""
    bot, err = require_session()
    if err: return err
    return jsonify({
        "prompt": bot.flow_engine.get_current_prompt(user_message=""),
        "stage": bot.flow_engine.current_stage,
        "strategy": bot.flow_engine.flow_type,
    })


@app.route('/api/debug/stage', methods=['POST'])
def debug_stage():
    """Jump FSM to a specific stage, bypassing advancement rules."""
    bot, err = require_session()
    if err: return err
    data = request.json or {}
    stage = data.get('stage')
    stages = bot.flow_engine.flow_config["stages"]
    if not stage or stage not in stages:
        return jsonify({"error": f"Invalid stage. Available: {stages}"}), 400
    bot.flow_engine.advance(target_stage=stage)
    return jsonify({"success": True, **_bot_state(bot)})


@app.route('/api/debug/analyse', methods=['POST'])
def debug_analyse():
    """Analyse a message against FSM signals without sending it to the LLM.

    Shows intent state, which signal categories match, and whether the
    current stage's advancement rule would fire.
    """
    bot, err = require_session()
    if err: return err
    data = request.json or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({"error": "message required"}), 400

    from chatbot.analysis import analyze_state, user_demands_directness, text_contains_any_keyword
    from chatbot.flow import ADVANCEMENT_RULES
    from chatbot.content import SIGNALS

    history = bot.flow_engine.conversation_history
    state = analyze_state(history, message, signal_keywords=SIGNALS)

    signal_keys = [
        'high_intent', 'low_intent', 'commitment', 'objection', 'walking',
        'impatience', 'direct_info_requests',
        'user_consultative_signals', 'user_transactional_signals',
    ]
    msg_lower = message.lower()
    signal_hits = {k: text_contains_any_keyword(msg_lower, SIGNALS.get(k, [])) for k in signal_keys}
    signal_hits['demands_directness'] = user_demands_directness(history, message)

    transition = bot.flow_engine.flow_config["transitions"].get(bot.flow_engine.current_stage)
    rule_name = transition.get("advance_on") if transition else None
    would_advance = None
    if rule_name and rule_name in ADVANCEMENT_RULES:
        would_advance = bool(ADVANCEMENT_RULES[rule_name](history, message, bot.flow_engine.stage_turn_count))

    return jsonify({
        "state": state,
        "signal_hits": signal_hits,
        "advancement": {
            "rule": rule_name,
            "would_advance": would_advance,
            "stage_turns": bot.flow_engine.stage_turn_count,
        },
    })


# ─── Prospect Mode API ──────────────────────────────────────────────────────

def require_prospect_session():
    """Validate prospect session. Returns (prospect_session, error_response)."""
    session_id = request.headers.get('X-Session-ID')
    if not session_id:
        return None, (jsonify({"error": "Session ID required"}), 400)
    ps = prospect_session_manager.get(session_id)
    if not ps:
        return None, (jsonify({"error": "Prospect session not found", "code": "SESSION_EXPIRED"}), 400)
    return ps, None


@app.route('/api/prospect/init', methods=['POST'])
@require_rate_limit('init')
def prospect_init():
    """Create a prospect session. Bot plays the buyer, user plays the salesperson."""
    if not prospect_session_manager.can_create():
        return jsonify({"error": "Prospect mode at capacity. Try again later."}), 503

    data = request.json or {}
    difficulty = data.get('difficulty', 'medium')
    product_type = data.get('product_type', 'default')
    provider = data.get('provider', 'groq')

    if difficulty not in ('easy', 'medium', 'hard'):
        return jsonify({"error": "Invalid difficulty. Choose: easy, medium, hard"}), 400

    session_id = secrets.token_hex(16)

    try:
        from chatbot.prospect import ProspectSession
        ps = ProspectSession(
            provider_type=provider,
            product_type=product_type,
            difficulty=difficulty,
            session_id=session_id,
        )
        opening = ps.get_opening_message()
        prospect_session_manager.set(session_id, ps)
        app.logger.info(f"Prospect session: {session_id} (difficulty={difficulty}, product={product_type})")

        return jsonify({
            "success": True,
            "session_id": session_id,
            "message": opening.content,
            "persona": {
                "name": ps.persona.get("name", "Unknown"),
                "background": ps.persona.get("background", ""),
                "personality": ps.persona.get("personality", ""),
            },
            "state": opening.state_snapshot,
            "difficulty": difficulty,
            "product_type": product_type,
            "latency_ms": opening.latency_ms,
            "provider": opening.provider,
            "model": opening.model,
        })
    except Exception as e:
        app.logger.exception(f"Prospect init failed: {e}")
        return jsonify({"error": f"Prospect init failed: {str(e)}"}), 500


@app.route('/api/prospect/chat', methods=['POST'])
@require_rate_limit('chat')
def prospect_chat():
    """User sends a sales message; prospect responds."""
    ps, err = require_prospect_session()
    if err:
        return err

    data = request.json or {}
    user_message, val_err = _validate_message(data.get('message', ''))
    if val_err:
        return val_err

    if ps.state.has_committed or ps.state.has_walked:
        return jsonify({"error": "Session has ended. Get evaluation or reset."}), 400

    show_hints = data.get('show_hints', False)

    try:
        response = ps.process_turn(user_message, show_hints=show_hints)
        result = {
            "success": True,
            "message": response.content,
            "state": response.state_snapshot,
            "latency_ms": response.latency_ms,
            "provider": response.provider,
            "model": response.model,
            "ended": ps.state.has_committed or ps.state.has_walked,
            "outcome": ps.state.status,
        }
        if response.coaching:
            result["coaching"] = response.coaching
        return jsonify(result)
    except Exception as e:
        app.logger.exception(f"Prospect chat error: {e}")
        return jsonify({"error": f"Prospect chat error: {str(e)}"}), 500


@app.route('/api/prospect/state', methods=['GET'])
def prospect_state():
    """Get current prospect session state."""
    ps, err = require_prospect_session()
    if err:
        return err
    return jsonify({"success": True, "state": ps.state.to_dict()})


@app.route('/api/prospect/evaluate', methods=['POST'])
def prospect_evaluate():
    """Generate final evaluation scorecard."""
    ps, err = require_prospect_session()
    if err:
        return err

    try:
        evaluation = ps.get_evaluation()
        return jsonify({"success": True, **evaluation})
    except Exception as e:
        app.logger.exception(f"Prospect evaluation error: {e}")
        return jsonify({"error": f"Evaluation failed: {str(e)}"}), 500


@app.route('/api/prospect/reset', methods=['POST'])
def prospect_reset():
    """End and remove a prospect session."""
    session_id = request.headers.get('X-Session-ID')
    if session_id:
        prospect_session_manager.delete(session_id)
    return jsonify({"success": True})


# ─── Evaluation Analytics APIs ───────────────────────────────────────────────────

@app.route('/api/analytics/session/<session_id>', methods=['GET'])
def get_session_analytics(session_id):
    """Get analytics events for a specific session (for evaluation study).

    Returns all recorded events: stage transitions, intent classifications,
    objection types, strategy switches.
    """
    events = SessionAnalytics.get_session_analytics(session_id)
    return jsonify({"success": True, "session_id": session_id, "events": events})


@app.route('/api/analytics/summary', methods=['GET'])
def get_analytics_summary():
    """Get aggregated analytics summary for evaluation chapter.

    Returns:
    - stage_reach_distribution: how many sessions reached each stage
    - intent_distribution: frequency of low/medium/high classifications
    - objection_type_distribution: which objection types appear most
    - initial_strategy_distribution: consultative vs transactional assigned
    - strategy_switch_frequency: how often strategies changed
    - ab_variant_distribution: distribution across A/B variants
    - sessions_reached_pitch: count of sessions reaching pitch stage
    - sessions_reached_objection: count of sessions reaching objection stage
    - total_sessions: total session count
    """
    summary = SessionAnalytics.get_evaluation_summary()
    return jsonify({"success": True, **summary})


# ─── Error handler ───────────────────────────────────────────────────────────

@app.errorhandler(Exception)
def handle_unexpected_error(e):
    """Catch-all for unhandled exceptions — prevents stack trace leakage.

    Re-raises HTTP exceptions (4xx, 5xx) so Flask handles them normally.
    Only catches truly unexpected errors (e.g., unhandled ValueError, TypeError).
    """
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e  # Let Flask handle 400, 404, etc. normally
    app.logger.exception("Unhandled error")
    return jsonify({"error": "Internal server error"}), 500


# ─── Application Startup ────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true', port=5000)
