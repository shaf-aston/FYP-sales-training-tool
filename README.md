# Fitness Chatbot - Full Stack Application

A modern fitness chatbot application with FastAPI backend and React.js frontend, featuring AI-powered conversations with Mary, a 65-year-old fitness client simulation.

## 🚀 Quick Start

### Option 1: Full Stack (Recommended)
```bash
# Windows
start_full_stack.bat

# This will start both:
# - FastAPI backend on http://localhost:8000  
# - React frontend on http://localhost:3000
```

### Option 2: Backend Only
```bash
# Windows
start_chatbot.bat

# Or manually
python scripts/run_chatbot.py

# Access at: http://localhost:8000
```

### Option 3: Manual Setup
```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Download model (first time only)
python scripts/download_model.py

# 3. Start backend
python src/fitness_chatbot.py

# 4. In another terminal, start React frontend
cd frontend
npm install
npm start
```

## 🏗️ Architecture

### Backend (FastAPI + Transformers)
- **Model**: Qwen/Qwen2.5-0.5B-Instruct with optimizations
- **Optimizations**: 4-bit quantization, accelerate, BetterTransformer
- **API Endpoints**:
  - `GET /` - Template-based chat interface
  - `POST /api/chat` - React-friendly chat endpoint
  - `GET /api/greeting` - Initial greeting
  - `GET /health` - Health check

### Frontend (React.js)
- Modern, responsive UI with smooth animations
- Real-time chat with typing indicators
- Mobile-friendly design
- Auto-scrolling message history

### Performance Optimizations
- **Accelerate**: Multi-device support and CPU fallback
- **Bitsandbytes**: 4-bit quantization for memory efficiency
- **Optimum**: BetterTransformer for faster inference
- **Offline-first**: All models cached locally, no API keys needed

## Project Structure

```
Sales roleplay chatbot/
├── src/                # Core application code
│   └── fitness_chatbot.py  # Main FastAPI application
├── scripts/            # Helper scripts
│   ├── run_chatbot.py  # Application launcher with dependency checks
│   └── download_model.py   # Model downloader for offline use
├── frontend/           # React.js frontend application
│   ├── src/            # React components
│   ├── public/         # Static assets
│   └── package.json    # NPM dependencies
├── docker/             # Docker configuration
│   ├── Dockerfile      # Container definition
│   └── docker-compose.yml  # Container orchestration
├── logs/               # Application log files
├── model_cache/        # Downloaded model files (Qwen2.5-0.5B-Instruct)
├── static/             # Static web assets (CSS, JS, images)
├── templates/          # Jinja2 HTML templates
├── utils/              # Utility functions (paths, env setup)
├── start_chatbot.bat   # Windows backend startup script
├── start_full_stack.bat # Windows full-stack startup script
└── requirements.txt    # Python dependencies
```

## Requirements

- **Python 3.8+** (tested with Python 3.12.8)
- **Node.js 16+** (for React frontend)
- Virtual environment (recommended)
- Approximately **1GB of disk space** for the Qwen2.5-0.5B-Instruct model
- **Windows**: Batch scripts provided for easy startup
- **Optional**: GPU support (CUDA) for faster inference

## Quick Start

### Windows

1. Run the setup script to create a virtual environment and install dependencies:
   ```
   python setup.py
   ```

2. Start the chatbot (includes automatic model download):
   ```
   start_chatbot.bat
   ```

### Linux/Mac

1. Run the setup script:
   ```
   python setup.py
   ```

2. Start the chatbot:
   ```
   python scripts/run_chatbot.py
   ```

The chatbot will be available at http://localhost:8000 in your web browser.

## Manual Model Download

If you want to download the model manually:

```
python scripts/download_model.py
```

This downloads the model files to the `model_cache` directory for offline use.

## Docker Support

You can also run the application using Docker:

```
docker-compose -f docker/docker-compose.yml up -d
```

## API Usage

The chatbot exposes the following API endpoints:

### Chat Endpoints
- `GET /` - Template-based chat interface (HTML)
- `POST /api/chat` - React-friendly chat endpoint
- `POST /chat` - Legacy chat endpoint for template frontend
- `GET /api/greeting` - Get initial greeting message
- `GET /health` - Health check endpoint

### Static Files
- `/static/*` - Static assets (CSS, JS, images)

Example API call:

```python
import requests

# For React frontend
response = requests.post(
    "http://localhost:8000/api/chat",
    json={"message": "What exercises are good for beginners?"}
)
print(response.json())  # Returns: {"response": "...", "status": "success"}

# For template frontend
response = requests.post(
    "http://localhost:8000/chat",
    json={"message": "What exercises are good for beginners?"}
)
print(response.json())  # Returns: {"response": "..."}
```

## Performance Optimizations

This chatbot includes several performance optimizations:

1. **Offline Model Usage**: After initial download, the model runs completely offline
2. **Optional Performance Libraries**: 
   - **Accelerate**: Multi-device support and CPU fallback
   - **Bitsandbytes**: 4-bit quantization for memory efficiency (CPU only)
   - **Optimum**: BetterTransformer for faster inference
3. **Graceful Degradation**: Falls back to standard transformers if optimization libraries aren't available
4. **Model Caching**: Local model storage in `model_cache/` directory

## Character

Mary is a 65-year-old recently retired woman who:
- Wants to lose weight and gain strength
- Has mild knee arthritis and occasional lower back pain
- Needs joint-friendly exercises
- Used to walk regularly but hasn't done structured exercise in years
- Is looking for safe fitness guidance

## Troubleshooting

- If the web UI doesn't load, manually navigate to http://localhost:8000
- If you encounter memory errors, try closing other applications
- For detailed logs, check `logs/chatbot.log` and `logs/chatbot_launcher.log`

### Common Issues

- **Model Not Found**: If you get errors about the model not being found locally, run:
  ```
  python scripts/download_model.py
  ```

- **Authentication Errors**: The application is configured to use models offline. Make sure you've downloaded the model first.

- **ModuleNotFoundError**: Ensure you've run the setup script and activated the virtual environment:
  ```
  python setup.py
  venv\Scripts\activate
  ```

- **Missing Dependencies**: If you still face issues with dependencies, try manually installing them:
  ```
  pip install -r requirements.txt
  ```

## Clean Up

To free disk space by removing unused models:

```
python utils/cleanup_models.py
```

Add the `--dry-run` flag to see what would be deleted without actually removing anything.
