BASE_MODEL = "default_model"

# LangChain configuration for backward compatibility
LANGCHAIN_CONFIG = {
    "max_new_tokens": 200,
    "temperature": 0.85,
    "repetition_penalty": 1.15,
    "memory_window": 10,
    "fallback_message": "I'm sorry, I'm having trouble responding right now. Could you try asking again?",
}