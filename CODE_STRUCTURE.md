# Single Character Chatbot Code Structure

## Main Components

### Character Profile
```python
CHARACTER_PROFILE = {
    "name": "Mary",
    "age": 68,
    "status": "senior",
    "occupation": "retired teacher",
    "goals": ["lose weight", "improve mobility", "manage arthritis"],
    "health_issues": ["arthritis in knees", "mild hypertension", "occasional back pain"],
    "background": "Retired elementary school teacher who has been mostly sedentary for the past decade. Enjoys gardening and reading but struggles with consistent exercise.",
    "personality": "Kind, curious, slightly anxious about new fitness routines, determined to improve health."
}
```

### Quick Response Patterns
```python
def get_quick_patterns() -> dict:
    """Get Mary-specific quick response patterns"""
    
    patterns = {
        # Basic greeting patterns
        "^(hello|hi|hey)$|^(hello|hi|hey) there": f"Hi there! I'm Mary. It's so nice to meet you!",
        "how are you|how do you feel": f"I'm doing well, thank you for asking! A bit nervous but excited to get started.",
        # ... more patterns ...
    }
    
    return patterns
```

### Initial Greeting
```python
def get_initial_greeting() -> str:
    """Return Mary's initial greeting"""
    return "Hello! I'm Mary, a 68-year-old retired teacher. I'm looking to get more active and manage my arthritis. I've been mostly sedentary for years and need guidance on where to start. Can you help me with a fitness plan that's appropriate for my age and condition?"
```

### Prompt Building
```python
def build_mary_prompt(message: str, contexts: list, topic: str = "general") -> str:
    """Build prompt for Mary's character"""
    
    # Base character description
    character_description = (
        "You are roleplaying as Mary, a 68-year-old retired elementary school teacher seeking fitness advice. "
        # ... more description ...
    )
    
    # ... more components ...
    
    # Assemble the full prompt
    full_prompt = (
        f"{character_description}\n\n"
        f"{personality_guidance}\n\n"
        f"{topic_context}\n\n"
        f"{conversation_history}\n"
        f"User: {message}\n"
        f"Mary:"
    )
    
    return full_prompt
```

### Chat Function
```python
def chat_with_mary(message: str, user_id: str = "default") -> str:
    """Chat function with context memory and 3-tier speed optimization"""
    start_time = time.time()
    response_type = "unknown"
    
    try:
        # ... 
        # 3-tier response system:
        # 1. Quick patterns
        # 2. Cache lookup
        # 3. AI generation
        # ...
        
        return response
        
    except Exception as e:
        # Error handling
        return get_fallback_response()
```

### API Endpoints
```python
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page that renders the chat.html template with Mary's greeting"""
    return templates.TemplateResponse(
        "chat.html", 
        {
            "request": request, 
            "initial_greeting": get_initial_greeting(),
            "character_name": CHARACTER_PROFILE["name"]
        }
    )

@app.post("/api/chat")
async def api_chat(payload: dict):
    """API endpoint for React frontend"""
    message = payload.get("message", "")
    user_id = payload.get("user_id", "default")
    
    response = chat_with_mary(message, user_id)
    session_key = f"{user_id}_mary"
    
    return {
        "response": response, 
        "status": "success",
        "user_id": user_id,
        "character": {
            "name": CHARACTER_PROFILE["name"],
            "age": CHARACTER_PROFILE["age"],
            "status": CHARACTER_PROFILE["status"],
            "description": f"{CHARACTER_PROFILE['name']}, {CHARACTER_PROFILE['age']}-year-old {CHARACTER_PROFILE['status']}"
        },
        "context_size": len(conversation_contexts.get(session_key, []))
    }
```

### Helper Functions
```python
def classify_message_topic(message: str) -> str:
    """Classify message topic for better context management"""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["exercise", "workout", "training", "movement"]):
        return "exercise"
    # ... more topic classifications ...
    else:
        return "general"

def post_process_response(response: str, message_hash: int) -> str:
    """Post-process Mary's response for consistency and character voice"""
    # ... processing logic ...
    return response

def get_fallback_response() -> str:
    """Get a fallback response for Mary when errors occur"""
    fallbacks = [
        "Oh dear, I seem to have lost my train of thought. Could you repeat that please?",
        # ... more fallbacks ...
    ]
    return random.choice(fallbacks)
```