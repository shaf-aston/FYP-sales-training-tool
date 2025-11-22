TECHNOLOGIES, TOOLS, FRAMEWORKS, AND LIBRARIES USED IN SALES ROLEPLAY CHATBOT
=================================================================================

BACKEND FRAMEWORK & API
-----------------------
- **FastAPI**: High-performance async framework for building RESTful APIs with automatic OpenAPI documentation.
  - *Reason*: Simplifies API development with built-in validation and async support.
- **Pydantic v2**: Data validation and serialization library.
  - *Reason*: Ensures type safety and automatic validation for API requests/responses.
- **Uvicorn**: ASGI server for running FastAPI applications.
  - *Reason*: Provides fast and lightweight server capabilities with hot-reload.

AI/ML & LANGUAGE MODELS
-----------------------
- **Transformers (Hugging Face)**: Library for loading and running Qwen2.5-0.5B-Instruct model.
  - *Reason*: Simplifies integration of state-of-the-art language models.
- **Torch (PyTorch)**: Deep learning framework for model inference.
  - *Reason*: Provides efficient neural network execution.
- **TensorFlow**: Alternative deep learning framework.
  - *Reason*: Offers flexibility for model inference.
- **Flax**: Lightweight neural network framework.
  - *Reason*: Provides efficient execution for specific use cases.
- **Optimum**: Model optimization library.
  - *Reason*: Enhances inference speed with BetterTransformer.
- **LangChain**: Framework for managing conversation chains and memory.
  - *Reason*: Maintains chat context across turns.
- **SentencePiece**: Tokenizer backend.
  - *Reason*: Handles subword segmentation for Qwen model.

VOICE & AUDIO PROCESSING
------------------------
- **Google Cloud STT/TTS**: Cloud-based services for speech-to-text and text-to-speech.
  - *Reason*: Provides high accuracy and natural-sounding voices.
- **Faster Whisper**: Primary STT backend for offline transcription.
  - *Reason*: High-accuracy local speech recognition with GPU acceleration support.
- **SpeechRecognition**: Secondary STT fallback service.
  - *Reason*: Provides additional STT options when primary service unavailable.
- **Librosa**: Audio analysis library.
  - *Reason*: Preprocesses audio for noise filtering and feature extraction.
- **Coqui-TTS**: Neural TTS engine with persona-specific voices.
  - *Reason*: Generates natural-sounding, customizable persona voices with emotion support.
- **PYTTSX3**: Lightweight TTS fallback engine.
  - *Reason*: Provides basic text-to-speech when advanced engines unavailable.
- **Pydub**: Audio manipulation library.
  - *Reason*: Converts and processes audio formats, handles pre-processing.
- **Soundfile**: Audio file I/O library.
  - *Reason*: Reads/writes WAV and other formats with format validation.

DATABASE & STORAGE
------------------
- **Psycopg2-binary**: PostgreSQL adapter.
  - *Reason*: Manages session data and conversation history.
- **Alembic**: Database migration tool.
  - *Reason*: Tracks schema changes and version control.
- **JSON Files**: Lightweight storage for personas.
  - *Reason*: Simplifies default and custom persona management.

FRONTEND FRAMEWORK & UI
-----------------------
- **React**: JavaScript library for building the chat interface.
  - *Reason*: Enables dynamic and interactive UI development.
- **Axios**: HTTP client for API requests.
  - *Reason*: Simplifies communication between frontend and backend.
- **Bootstrap**: CSS framework.
  - *Reason*: Provides responsive layouts and pre-built components.

SECURITY & AUTHENTICATION
--------------------------
- **Python-JOSE**: JWT implementation.
  - *Reason*: Secures user authentication and session management.
- **Passlib**: Password hashing library.
  - *Reason*: Ensures secure credential storage.

UTILITIES & HELPERS
-------------------
- **Python-dotenv**: Loads environment variables.
  - *Reason*: Manages API keys and configuration securely.
- **Requests**: HTTP library.
  - *Reason*: Handles external API calls.
- **Numpy**: Numerical computing library.
  - *Reason*: Supports array operations in audio processing.

DEVELOPMENT & TESTING
---------------------
- **Pytest**: Testing framework.
  - *Reason*: Simplifies unit and integration testing.
- **Httpx**: Async HTTP client.
  - *Reason*: Tests FastAPI routes efficiently.

LOGGING & MONITORING
--------------------
- **Custom Logger**: Centralized logging configuration.
  - *Reason*: Tracks performance and debugging with clear markers.

DEVELOPMENT TOOLS
-----------------
- **FFmpeg**: Multimedia framework.
  - *Reason*: Supports audio codec requirements.
- **Git**: Version control system.
  - *Reason*: Manages source code and collaboration.

PROJECT-SPECIFIC SERVICES
-------------------------
- **PersonaService**: Manages persona definitions.
  - *Reason*: Centralizes persona CRUD operations.
- **ChatService**: Orchestrates conversation logic.
  - *Reason*: Handles response generation and timing logs.
- **ModelService**: Manages AI model loading.
  - *Reason*: Optimizes model initialization and inference.
- **VoiceService**: Coordinates STT and TTS pipelines.
  - *Reason*: Streamlines audio processing workflows.

API ROUTE MODULES
-----------------
- **chat_routes.py**: Core chat endpoints (/api/chat, /api/greeting, /api/personas) with Pydantic validation.
- **persona_chat_routes.py**: V2 persona-specific endpoints (/api/v2/personas) for enhanced persona interactions.
- **sessions_routes.py**: Session management endpoints (/api/sessions/start, /api/sessions/end) with automatic validation.
- **team_routes.py**: Team/multi-user management endpoints for collaborative roleplay scenarios.
- **external_routes.py**: Integration endpoints for external service webhooks and third-party API callbacks.
- **dashboard_routes.py**: Analytics and reporting endpoints for performance metrics and conversation insights.
- **system_routes.py**: Health checks, system status, and administrative endpoints.

DATA MODELS
-----------
- **Pydantic Request Models** (src/models/request_models.py): ChatRequest, SessionStartRequest, PersonaCreateRequest with field validators.
- **Pydantic Response Models** (src/models/request_models.py): ChatResponse, SessionEndRequest, HealthCheckResponse for type-safe API responses.
- **Persona Dataclass** (src/models/persona.py): Structured persona definition with 15+ fields including background, goals, objections.
- **Character Profiles** (src/models/character_profiles.py): Legacy persona storage being migrated to JSON-based PersonaService.

CONFIGURATION & SETTINGS
------------------------
- **settings.py** (config/settings.py): Application configuration with environment-specific settings (dev/prod).
- **paths.py** (utils/paths.py): Centralized path resolution for model cache, data directories, and log files.
- **db.py** (utils/db.py): Database connection pooling and session management utilities.
- **env.py** (utils/env.py): Environment variable loading and validation helpers.

MIGRATION SCRIPTS
-----------------
- **001_create_personas_table.sql**: PostgreSQL schema migration for personas table with indexes.
- **download_model.py**: Script for pre-downloading Qwen model and tokenizer to local cache.
- **run_chatbot.py**: Application entry point script for starting FastAPI server.
- **run_migrations.py**: Database migration runner using alembic for schema updates.

ARCHIVED/BACKUP MODULES
-----------------------
- **fallback_responses.py.backup**: Backup of previous fallback response logic before optimization.
- **settings_backup.py**: Configuration backup before refactoring to environment-based settings.
- **dashboard_fixes_summary.py**: Legacy dashboard debugging utilities.

BUILD ARTIFACTS
---------------
- **frontend/build/**: Production-optimized React bundle with minified JS/CSS and asset manifest.
- **model_cache/**: Local storage for downloaded Qwen model weights, tokenizers, and pipeline configs.
- **logs/conversation_backup.json**: JSON-formatted conversation history for debugging and analysis.



DEVELOPMENT & TESTING NOTES
----------------------------

**Package Management:**
All core dependencies are defined in `requirements.txt` with version pinning for stability. Key packages include:
- **PyTorch** (torch>=2.0.0): Deep learning framework for model inference - INSTALLED
- **Transformers** (>=4.30.0): Hugging Face library for language models - INSTALLED
- **FastAPI** (>=0.103.1): High-performance web framework - INSTALLED
- **Coqui-TTS** (>=0.27.2): Neural TTS engine - INSTALLED
- **Flax** (>=0.6.0): Lightweight neural network framework - INSTALLED

**Installation:**
Run `pip install -r requirements.txt` to install all dependencies. The project uses version ranges to balance stability and compatibility.

**Code Quality:**
- Pydantic v2 is used for all API models with automatic validation
- No namespace conflicts exist in current Pydantic models (all use standard field names)
- Type hints and validation decorators ensure data integrity throughout the application



**PROPTYPES**
Type-checking utility for React components. Used to validate the shape and type of props passed to UI components (e.g., Header, Dashboard) in the frontend. Ensures that dynamic persona data and other props are correctly structured, preventing runtime errors and improving maintainability. PropTypes provides clear developer warnings and helps keep the UI robust as the data model evolves.

**MagicMock**
Advanced mock object from Python's unittest.mock library. Used in backend unit tests to simulate external dependencies (database, model service, voice service) and control their behavior. MagicMock supports mocking magic methods and complex objects, enabling isolated, reliable, and fast tests for API endpoints and service logic. It is essential for achieving high test coverage and safe refactoring in the backend codebase.

VOICE PROCESSING ANALYSIS & IMPROVEMENTS
========================================

STT (SPEECH-TO-TEXT) PERFORMANCE
--------------------------------
**Current Implementation:**
- Tiered approach: Faster Whisper → SpeechRecognition → Google Cloud STT
- Confidence scoring and caching implemented
- Processing time tracking and performance metrics

**Identified Issues:**
- No Word Error Rate (WER) measurement for accuracy assessment
- Fixed confidence scores (0.9 for Google STT, estimated for Whisper)
- Limited audio validation (size only, not format/corruption)
- No streaming support for long audio inputs
- Broad exception handling masks specific error types

**Recommended Improvements:**
- Implement WER evaluation using jiwer library with ground truth datasets
- Add robust audio pre-processing (noise reduction, format validation)
- Implement streaming STT for improved latency on long inputs
- Add real-time resource monitoring (CPU/GPU/memory usage)
- Enhance error handling with specific exception types

TTS (TEXT-TO-SPEECH) PERFORMANCE
--------------------------------
**Current Implementation:**
- Coqui-TTS for high-quality persona-specific voices
- PYTTSX3 as lightweight fallback
- Emotion and speaker voice customization
- Caching and performance tracking

**Identified Issues:**
- No objective pronunciation accuracy evaluation
- Fixed WAV output format only
- Limited voice customization beyond available models
- No handling of very long text inputs (sentence splitting)
- TTS_AVAILABLE flag currently disabled

**Recommended Improvements:**
- Implement Mean Opinion Score (MOS) evaluation framework
- Add support for multiple output formats (MP3, OGG)
- Implement text chunking for long inputs to reduce latency
- Create fallback voice profiles for TTS failures
- Enable dynamic voice model loading based on persona requirements

TECHNICAL LIMITATIONS & CONSTRAINTS
-----------------------------------
**Language Support:**
- Current default: English only (['en'])
- Backend capabilities may support additional languages
- Need dynamic language detection and capability reporting

**Audio Format Compatibility:**
- STT expects pre-processed bytes and sample rate
- TTS outputs WAV format only
- Limited support for diverse input formats without pre-processing

**Resource Requirements:**
- Faster Whisper and Coqui-TTS are GPU-intensive
- No real-time resource monitoring or adaptive quality scaling
- Potential memory issues with long audio/text inputs

USER EXPERIENCE IMPROVEMENTS
----------------------------
**Confidence-Based Feedback:**
- Implement low-confidence prompts for STT clarification
- Provide user-facing confidence indicators

**Graceful Error Handling:**
- Clear user messages for STT/TTS failures
- Automatic fallback to simpler, reliable services

**Conversational Speech Support:**
- Post-processing for disfluencies and informal language
- Better handling of overlapping speech and interruptions

IMPLEMENTATION PRIORITY
----------------------
1. **High Priority:** WER evaluation, audio pre-processing, error handling
2. **Medium Priority:** Streaming STT, resource monitoring, format support
3. **Low Priority:** Advanced voice customization, multi-language expansion