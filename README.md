# Sales Roleplay Chatbot

An AI-powered sales assistant designed to simulate realistic sales conversations using the IMPACT framework and dynamic strategy switching.

### Prerequisites
- Python 3.10+
- A Groq API key (obtain from [console.groq.com](https://console.groq.com))

### Setup Instructions

1. **Clone and navigate to the project:**
   ```bash
   cd "Sales roleplay chatbot"
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file in the project root and add:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   ```

4. **Run the Flask application:**
   ```bash
   python src/web/app.py
   ```

5. **Access the Chatbot:**
   Open your browser and navigate to `http://localhost:5000`.

## Project Structure

This project is organized into several key directories, each with a specific role in the application's functionality.

```
.
├── .env                      # Environment variables (e.g., API keys)
├── requirements.txt          # Python dependencies
├── src/                      # Source code for the application
│   ├── chatbot/              # Core chatbot logic and AI components
│   │   ├── analysis.py       # Natural Language Understanding (NLU) logic
│   │   ├── chatbot.py        # Main chatbot class, orchestrates interactions
│   │   ├── config.py         # Chatbot-specific configuration settings
│   │   ├── content.py        # Manages response templates and dynamic content
│   │   ├── flow.py           # Implements the Finite State Machine (FSM) logic
│   │   ├── performance.py    # Tracks and reports performance metrics
│   │   └── providers/        # Integrations with various LLM providers
│   │       ├── __init__.py   # Initializes the providers package
│   │       ├── base.py       # Base class for LLM providers
│   │       ├── factory.py    # Factory for creating LLM provider instances
│   │       ├── groq_provider.py # Groq API integration
│   │       └── ollama_provider.py # Ollama (local LLM) integration
│   └── web/                  # Web interface and server-side components
│       ├── app.py            # Flask application entry point, API routes
│       ├── static/           # Static assets (CSS, JS, images)
│       │   └── speech.js     # Frontend JavaScript for speech functionalities
│       └── templates/        # HTML templates for the web interface
│           └── index.html    # Main HTML file for the chat interface
├── tests/                    # Unit and integration tests
│   ├── conftest.py           # Pytest configuration and fixtures
│   ├── test_all.py           # Runs all tests
│   ├── test_groq_provider.py # Tests for Groq API integration
│   ├── test_human_flow.py    # Tests for human-like conversational flow
│   ├── test_performance_tracker.py # Tests for performance tracking
│   ├── test_priority_fixes.py # Tests for specific bug fixes/priorities
│   ├── test_status.py        # Tests for application status/health checks
│   ├── test_transactional.py # Tests for the transactional sales strategy
│   └── test_web_app.py       # Tests for the Flask web application
└── Project-doc.md            # Comprehensive project documentation/report
```

## Technology Stack

*   **Backend:** Python 3.10+, Flask 3.0+
*   **Frontend:** HTML5, CSS3, JavaScript (ES6)
*   **AI/LLM:** Groq API (supports Llama-3.3-70b-versatile and other models)
*   **LLM Fallback:** Optional Ollama integration for local LLM support
*   **Architecture:** Finite State Machine (FSM) with modular NLU and content handling

## Key Features

*   **Modular Design:** The codebase is refactored into distinct modules for clarity and maintainability:
    *   `analysis.py`: Handles Natural Language Understanding (NLU) logic including intent detection, tone analysis, and preference extraction.
    *   `content.py`: Manages response templates, sales stage definitions, and signal keywords.
    *   `flow.py`: Implements the core Finite State Machine (FSM) logic for conversation flow management.
    *   `chatbot.py`: Orchestrates interactions between providers, flow engine, and performance tracking.
*   **Dynamic Strategy Switching:** The chatbot can dynamically switch between two sales strategies based on product configuration:
    *   **Consultative (IMPACT):** A detailed, deep-probing approach with stages: Intent → Logical → Emotional → Pitch → Objection.
    *   **Transactional:** A faster, more direct sales pitch with stages: Intent → Pitch → Objection.
*   **Small-Talk Control:** Seamlessly bridges casual conversation back to the main sales dialogue.
*   **API Resilience:** Thread-safe round-robin failover mechanism across multiple Groq API keys if provided.
*   **Prompt Engineering:** Stage-specific, externalized prompt templates for maximum flexibility and easy tuning.
*   **Performance Tracking:** Real-time metrics collection for latency, provider usage, and strategy effectiveness.

## Testing

The project includes comprehensive unit and integration tests covering all core modules.

*   **Run the full test suite:**
    ```bash
    python -m pytest tests/test_all.py -v
    ```

*   **Run specific test modules:**
    ```bash
    python -m pytest tests/test_transactional.py -v    # Transactional strategy
    python -m pytest tests/test_groq_provider.py -v    # Groq API integration
    python -m pytest tests/test_human_flow.py -v       # Conversational flow
    python -m pytest tests/test_performance_tracker.py # Performance metrics
    python -m pytest tests/test_web_app.py -v          # Flask web app
    ```

## Comprehensive Documentation

For a detailed project report, including in-depth evaluation, architecture decisions, and academic foundations, please refer to [Project-doc.md](Project-doc.md).
