from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from chatbot import SalesChatbot
import secrets
from dotenv import load_dotenv

load_dotenv()

# Disable .pyc file generation
sys.dont_write_bytecode = True

app = Flask(__name__)
# Use environment-provided secret when available; fallback to a generated key for dev
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(32))
CORS(app)

# Simple favicon handler to avoid browser 404s requesting /favicon.ico
@app.route('/favicon.ico')
def favicon():
    return ('', 204)

# Store chatbot instances per session
chatbots = {}

@app.route('/')
def home():
    """Serve the chat interface"""
    return render_template('index.html')

@app.route('/api/init', methods=['POST'])
def api_init():
    """Initialize session and return chat history if exists"""
    
    if not os.environ.get("GROQ_API_KEY"):
        return jsonify({"error": "API key not configured in .env file"}), 500
    
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(16)
    
    session_id = session['session_id']
    history = []
    
    # Return history if bot exists
    if session_id in chatbots:
        history = [{"role": msg["role"], "content": msg["content"]} for msg in chatbots[session_id].history]
    
    return jsonify({
        "success": True,
        "message": "Hey, what's up? How can I help you out?",
        "stage": "intent",
        "strategy": "consultative",
        "history": history
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({"error": "Message required"}), 400
    
    if len(user_message) > 1000:
        return jsonify({"error": "Message too long (max 1000 characters)"}), 400
    
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({"error": "Session not initialized"}), 400
    
    # Lazy init: create bot on first message
    if session_id not in chatbots:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return jsonify({"error": "API key not configured"}), 500
        
        # Get product type from request or env (default: "general")
        product_type = data.get('product_type', os.environ.get("PRODUCT_TYPE", "general"))
        chatbots[session_id] = SalesChatbot(api_key, product_type=product_type)
    
    bot = chatbots[session_id]
    
    try:
        response = bot.chat(user_message)
        
        return jsonify({
            "success": True,
            "message": response,
            "stage": bot.stage,
            "strategy": bot.strategy_name,
            "extracted": bot.extracted
        })
    
    except Exception as e:
        return jsonify({"error": f"Chat error: {str(e)}"}), 500

@app.route('/api/summary', methods=['GET'])
def get_summary():
    """Get conversation summary"""
    session_id = session.get('session_id')
    
    if not session_id or session_id not in chatbots:
        return jsonify({"error": "Chatbot not initialized"}), 400
    
    bot = chatbots[session_id]
    
    return jsonify({
        "success": True,
        "summary": bot.get_conversation_summary()
    })

@app.route('/api/reset', methods=['POST'])
def reset():
    """Reset the conversation"""
    session_id = session.get('session_id')
    
    if session_id and session_id in chatbots:
        del chatbots[session_id]
    
    return jsonify({"success": True})

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    app.run(debug=True, port=5000)
