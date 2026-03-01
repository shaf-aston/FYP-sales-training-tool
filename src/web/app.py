from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import sys
import secrets
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from chatbot.chatbot import SalesChatbot
from chatbot.providers import get_available_providers
from chatbot.performance import PerformanceTracker
from chatbot.knowledge import (
    load_custom_knowledge, save_custom_knowledge,
    get_custom_knowledge_text, clear_custom_knowledge,
)

# Disable .pyc file generation
sys.dont_write_bytecode = True

app = Flask(__name__)
CORS(app)

# Application configuration
APP_CONFIG = {
    "MAX_MESSAGE_LENGTH": 1000,
    "SESSION_IDLE_MINUTES": 60
}

# Session storage: {session_id: {"bot": SalesChatbot, "ts": datetime}}
sessions = {}


def cleanup_expired_sessions():
    """Remove sessions idle > SESSION_IDLE_MINUTES. Called lazily on requests."""
    now = datetime.now()
    max_idle = timedelta(minutes=APP_CONFIG["SESSION_IDLE_MINUTES"])
    expired = [sid for sid, s in sessions.items() if now - s["ts"] > max_idle]
    for sid in expired:
        del sessions[sid]
    if expired:
        app.logger.info(f"Cleaned up {len(expired)} idle sessions")


def get_session(session_id):
    """Get chatbot, updating timestamp."""
    entry = sessions.get(session_id)
    if entry:
        entry["ts"] = datetime.now()
        return entry["bot"]
    return None


def set_session(session_id, chatbot):
    """Store chatbot."""
    sessions[session_id] = {"bot": chatbot, "ts": datetime.now()}


def delete_session(session_id):
    """Remove session."""
    sessions.pop(session_id, None)


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
        return None, (jsonify({"error": "Session not found"}), 400)
    return bot, None


# Simple favicon handler to avoid browser 404s requesting /favicon.ico
@app.route('/favicon.ico')
def favicon():
    return ('', 204)

@app.route('/')
def home():
    """Serve the chat interface"""
    return render_template('index.html')

@app.route('/api/init', methods=['POST'])
def api_init():
    """Initialize or restore session. Creates bot eagerly to avoid first-message latency."""
    data = request.json or {}
    existing_id = data.get('session_id')

    # Restore existing session if still alive on server
    if existing_id:
        bot = get_session(existing_id)
        if bot:
            history = [{"role": m["role"], "content": m["content"]}
                       for m in bot.flow_engine.conversation_history]
            app.logger.info(f"Restored session: {existing_id} ({len(history)} messages)")
            return jsonify({
                "success": True,
                "session_id": existing_id,
                "message": None,
                "stage": bot.flow_engine.current_stage,
                "strategy": bot.flow_engine.flow_type,
                "history": history
            })

    # Create new session with eager bot initialization
    session_id = secrets.token_hex(16)
    product_type = data.get('product_type', os.environ.get("PRODUCT_TYPE", "general"))
    provider = data.get('provider', os.environ.get("PROVIDER", "groq"))
    
    try:
        bot = SalesChatbot(provider_type=provider, product_type=product_type, session_id=session_id)
        set_session(session_id, bot)
        app.logger.info(f"New session: {session_id} (product={product_type}, provider={provider})")
    except Exception as init_error:
        app.logger.exception(f"Bot init failed: {init_error}")
        return jsonify({"error": f"Init failed: {str(init_error)}"}), 500
    
    return jsonify({
        "success": True,
        "session_id": session_id,
        "message": "Hey, what's up? How can I help you out?",
        "stage": "intent",
        "strategy": None,
        "history": []
    })

@app.route('/api/restore', methods=['POST'])
def api_restore():
    """Rebuild bot from client-side history after server session loss.
    
    Accepts full conversation history from localStorage, replays into fresh bot
    to reconstruct FSM state without any LLM calls.
    """
    data = request.json or {}
    history = data.get('history', [])  # [{role, content}, ...]
    product_type = data.get('product_type', os.environ.get("PRODUCT_TYPE", "general"))
    provider = data.get('provider', os.environ.get("PROVIDER", "groq"))
    
    session_id = secrets.token_hex(16)
    
    try:
        bot = SalesChatbot(provider_type=provider, product_type=product_type, session_id=session_id)
        
        # Replay history directly into FSM — no LLM calls, just state reconstruction
        if history:
            for i in range(0, len(history), 2):
                if i + 1 >= len(history):
                    break  # Malformed history (odd length) — skip incomplete pair
                
                if (history[i].get('role') == 'user' and 
                    history[i + 1].get('role') == 'assistant'):
                    
                    user_msg = history[i]['content']
                    bot_msg = history[i + 1]['content']
                    bot.flow_engine.add_turn(user_msg, bot_msg)
                    
                    # Re-calculate state transitions based on replayed history
                    advancement = bot.flow_engine.should_advance(user_msg)
                    if advancement:
                        if isinstance(advancement, str):
                            bot.flow_engine.advance(target_stage=advancement)
                        else:
                            bot.flow_engine.advance()
        
        set_session(session_id, bot)
        app.logger.info(f"Restored session: {session_id} ({len(history)} messages replayed)")
        
    except Exception as e:
        app.logger.exception(f"Restore failed: {e}")
        return jsonify({"error": f"Restore failed: {str(e)}"}), 500
    
    return jsonify({
        "success": True,
        "session_id": session_id,
        "stage": bot.flow_engine.current_stage,
        "strategy": bot.flow_engine.flow_type,
    })

@app.route('/api/health', methods=['GET'])
def api_health():
    """Health check: provider availability and performance stats"""
    cleanup_expired_sessions()  # Lazy cleanup
    session_id = request.headers.get('X-Session-ID')
    
    # Get active provider info
    active_provider = None
    active_model = None
    if session_id:
        bot = get_session(session_id)
        if bot:
            active_provider = type(bot.provider).__name__.replace('Provider', '').lower()
            active_model = bot.provider.get_model_name()
    
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

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages. Bot must be initialized via /api/init first."""
    cleanup_expired_sessions()  # Lazy cleanup
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({"error": "Message required"}), 400
    
    if len(user_message) > APP_CONFIG["MAX_MESSAGE_LENGTH"]:
        return jsonify({"error": f"Message too long (max {APP_CONFIG['MAX_MESSAGE_LENGTH']} characters)"}), 400
    
    session_id = request.headers.get('X-Session-ID')
    if not session_id:
        return jsonify({"error": "Session ID required in X-Session-ID header"}), 400
    
    # Bot must exist (created in /api/init)
    bot = get_session(session_id)
    if not bot:
        return jsonify({"error": "No active session. Call /api/init first."}), 400
    
    try:
        response = bot.chat(user_message)
        
        # Extract content and metrics from ChatResponse
        return jsonify({
            "success": True,
            "message": response.content,
            "stage": bot.flow_engine.current_stage,
            "strategy": bot.flow_engine.flow_type,
            "latency_ms": round(response.latency_ms, 1),
            "provider": response.provider,
            "model": response.model,
            "metrics": {
                "input_length": response.input_len,
                "output_length": response.output_len
            }
        })
    
    except Exception as e:
        app.logger.exception(f"Chat error: {e}")
        return jsonify({"error": f"Chat error: {str(e)}"}), 500

@app.route('/api/summary', methods=['GET'])
def get_summary():
    """Get conversation summary"""
    bot, err = require_session()
    if err: return err
    
    return jsonify({
        "success": True,
        "summary": bot.get_conversation_summary()
    })

@app.route('/api/edit', methods=['POST'])
def edit_message():
    """Edit user message and regenerate from that point"""
    data = request.json
    msg_index = data.get('index')
    new_message = data.get('message', '').strip()
    
    bot, err = require_session()
    if err: return err
    
    # Validate inputs
    if msg_index is None:
        return jsonify({"error": "Missing message index"}), 400
    
    if not new_message:
        return jsonify({"error": "Message cannot be empty"}), 400
    
    if len(new_message) > APP_CONFIG["MAX_MESSAGE_LENGTH"]:
        return jsonify({"error": f"Message too long (max {APP_CONFIG['MAX_MESSAGE_LENGTH']} characters)"}), 400

    try:
        msg_index = int(msg_index)
        
        # Validate index is within bounds
        max_index = len(bot.flow_engine.conversation_history) - 1
        if msg_index < 0 or msg_index > max_index:
            return jsonify({"error": f"Invalid index. Valid range: 0-{max_index}"}), 400

        # Rewind to turn BEFORE the edit, then replay with new message
        turn_index = msg_index // 2  # Convert message index to turn index
        if not bot.rewind_to_turn(turn_index):
            return jsonify({"error": "Rewind failed"}), 500
        
        # Now chat with the new message
        response = bot.chat(new_message)
        
        return jsonify({
            "success": True,
            "message": response.content,
            "history": [{"role": m["role"], "content": m["content"]} for m in bot.flow_engine.conversation_history],
            "stage": bot.flow_engine.current_stage,
            "strategy": bot.flow_engine.flow_type,
            "latency_ms": round(response.latency_ms, 1),
            "provider": response.provider,
            "model": response.model
        })
    except ValueError:
        return jsonify({"error": "Invalid index format"}), 400
    except Exception as e:
        return jsonify({"error": f"Edit error: {str(e)}"}), 500

@app.route('/api/reset', methods=['POST'])
def reset():
    """Reset the conversation"""
    session_id = request.headers.get('X-Session-ID')
    
    if session_id:
        delete_session(session_id)
    
    return jsonify({"success": True})

@app.route('/api/switch-provider', methods=['POST'])
def switch_provider():
    """Switch LLM provider mid-conversation.
    
    Request Body:
        {"provider": "groq"|"ollama", "model": "optional-model-name"}
    
    Returns:
        {"success": bool, "from": str, "to": str, "model": str}
    """
    bot, err = require_session()
    if err: return err
    
    data = request.json
    provider_type = data.get('provider')
    if not provider_type:
        return jsonify({"error": "Provider type required"}), 400
    
    result = bot.switch_provider(
        provider_type=provider_type,
        model=data.get('model')
    )
    
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


# ─── Knowledge Base Routes ──────────────────────────────────────────

@app.route('/knowledge')
def knowledge_page():
    """Serve the knowledge base management page."""
    return render_template('knowledge.html')


@app.route('/api/knowledge', methods=['GET'])
def get_knowledge():
    """Retrieve current custom knowledge."""
    return jsonify({"success": True, "data": load_custom_knowledge()})


@app.route('/api/knowledge', methods=['POST'])
def save_knowledge_route():
    """Save custom knowledge data with field-level validation."""
    from chatbot.knowledge import ALLOWED_FIELDS, MAX_FIELD_LENGTH

    data = request.json
    if not data or not isinstance(data, dict):
        return jsonify({"error": "No data provided"}), 400

    # Reject unknown fields early (knowledge.py also whitelists, this is defense-in-depth)
    unknown = set(data.keys()) - ALLOWED_FIELDS
    if unknown:
        return jsonify({"error": f"Unknown fields: {', '.join(unknown)}"}), 400

    # Reject oversized values before they reach the storage layer
    for key, value in data.items():
        if not isinstance(value, str):
            return jsonify({"error": f"Field '{key}' must be a string"}), 400
        if len(value) > MAX_FIELD_LENGTH:
            return jsonify({"error": f"Field '{key}' exceeds {MAX_FIELD_LENGTH} chars"}), 400

    success = save_custom_knowledge(data)
    return jsonify({"success": success})


@app.route('/api/knowledge', methods=['DELETE'])
def clear_knowledge_route():
    """Clear all custom knowledge."""
    success = clear_custom_knowledge()
    return jsonify({"success": success})


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


if __name__ == '__main__':
    app.run(debug=True, port=5000)


