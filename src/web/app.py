from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import sys
import time
import secrets
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from chatbot.chatbot import SalesChatbot
from chatbot.providers import get_available_providers
from chatbot.performance import PerformanceTracker

# Disable .pyc file generation
sys.dont_write_bytecode = True

app = Flask(__name__)
CORS(app)

# Configuration
CONFIG = {
    "MAX_MESSAGE_LENGTH": 1000,
    "SESSION_IDLE_MINUTES": 60
}

# Session storage with timestamps for cleanup
sessions = {}
session_timestamps = {}


def cleanup_expired_sessions():
    """Remove sessions idle > SESSION_IDLE_MINUTES. Called lazily on requests."""
    now = datetime.now()
    max_idle = timedelta(minutes=CONFIG["SESSION_IDLE_MINUTES"])
    expired = [sid for sid, ts in session_timestamps.items() if now - ts > max_idle]
    for sid in expired:
        del sessions[sid]
        del session_timestamps[sid]
    if expired:
        app.logger.info(f"Cleaned up {len(expired)} idle sessions")


def get_session(session_id):
    """Get chatbot, updating timestamp."""
    if session_id in sessions:
        session_timestamps[session_id] = datetime.now()
    return sessions.get(session_id)


def set_session(session_id, chatbot):
    """Store chatbot."""
    sessions[session_id] = chatbot
    session_timestamps[session_id] = datetime.now()


def delete_session(session_id):
    """Remove session."""
    if session_id in sessions:
        del sessions[session_id]
        del session_timestamps[session_id]


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
    """Initialize session and return session_id"""
    session_id = secrets.token_hex(16)
    app.logger.info(f"Session initialized: {session_id}")
    
    return jsonify({
        "success": True,
        "session_id": session_id,
        "message": "Hey, what's up? How can I help you out?",
        "stage": "intent",
        "strategy": None,
        "history": []
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
    """Handle chat messages"""
    cleanup_expired_sessions()  # Lazy cleanup
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({"error": "Message required"}), 400
    
    if len(user_message) > CONFIG["MAX_MESSAGE_LENGTH"]:
        return jsonify({"error": f"Message too long (max {CONFIG['MAX_MESSAGE_LENGTH']} characters)"}), 400
    
    session_id = request.headers.get('X-Session-ID')
    if not session_id:
        return jsonify({"error": "Session ID required in X-Session-ID header"}), 400
    
    # Lazy init: create bot on first message
    bot = get_session(session_id)
    if not bot:
        try:
            product_type = data.get('product_type', os.environ.get("PRODUCT_TYPE", "general"))
            
            # Force Groq as default (override .env if needed)
            provider = data.get('provider', "groq")
            
            bot = SalesChatbot(provider_type=provider, product_type=product_type, session_id=session_id)
            set_session(session_id, bot)
        except Exception as init_error:
            return jsonify({"error": f"Error initializing chatbot: {str(init_error)}"}), 500
    
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
    session_id = request.headers.get('X-Session-ID')
    
    if not session_id:
        return jsonify({"error": "Session ID required"}), 400
    
    bot = get_session(session_id)
    if not bot:
        return jsonify({"error": "Session not found"}), 400
    
    return jsonify({
        "success": True,
        "summary": bot.get_conversation_summary()
    })

@app.route('/api/edit', methods=['POST'])
def edit_message():
    """Edit user message and regenerate from that point"""
    data = request.json
    session_id = request.headers.get('X-Session-ID')
    msg_index = data.get('index')
    new_message = data.get('message', '').strip()

    # Validate session exists
    if not session_id:
        return jsonify({"error": "Session ID required"}), 400
    
    bot = get_session(session_id)
    if not bot:
        return jsonify({"error": "Session not found"}), 400
    
    # Validate inputs
    if msg_index is None:
        return jsonify({"error": "Missing message index"}), 400
    
    if not new_message:
        return jsonify({"error": "Message cannot be empty"}), 400
    
    if len(new_message) > CONFIG["MAX_MESSAGE_LENGTH"]:
        return jsonify({"error": f"Message too long (max {CONFIG['MAX_MESSAGE_LENGTH']} characters)"}), 400

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
    data = request.json
    session_id = request.headers.get('X-Session-ID')
    
    if not session_id:
        return jsonify({"error": "Session ID required"}), 400
    
    bot = get_session(session_id)
    if not bot:
        return jsonify({"error": "No active session"}), 400
    
    provider_type = data.get('provider')
    if not provider_type:
        return jsonify({"error": "Provider type required"}), 400
    
    result = bot.switch_provider(
        provider_type=provider_type,
        model=data.get('model')
    )
    
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

if __name__ == '__main__':
    app.run(debug=True, port=5000)


