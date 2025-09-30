# Fitness Chatbot

AI-powered fitness chatbot simulating conversations with Mary, a 65-year-old fitness client. Built with FastAPI backend and React frontend.

## 🚀 Quick Start

**Windows (Recommended):**
```bash
start_full_stack.bat  # Starts both backend (port 8000) and frontend (port 3000)
```

**Manual Setup:**
```bash
pip install -r requirements.txt
python scripts/download_model.py  # First time only
python src/fitness_chatbot.py     # Backend only
```

## Architecture

- **Backend**: FastAPI + Qwen2.5-0.5B-Instruct model with optimizations
- **Frontend**: React.js with responsive design
- **Features**: Offline AI model, real-time chat, performance optimizations

## Requirements

- Python 3.8+
- Node.js 16+ (for React frontend)
- ~1GB disk space for AI model
- Optional: GPU for faster inference

## Project Structure

```
├── src/fitness_chatbot.py    # Main FastAPI application
├── scripts/                  # Helper scripts
├── frontend/                 # React.js application  
├── model_cache/             # AI model files (~1GB)
├── templates/               # HTML templates
├── requirements.txt         # Dependencies
└── start_*.bat             # Windows startup scripts
```

## API Endpoints

- `POST /api/chat` - Main chat endpoint
- `GET /api/greeting` - Initial greeting
- `GET /health` - Health check
- `GET /` - Web interface

## Character Profile

**Mary** - 65-year-old retired teacher seeking fitness guidance:
- Goals: Lose weight, gain strength safely
- Health: Mild knee arthritis, lower back pain  
- Experience: Used to walk regularly, no structured exercise recently

## Troubleshooting

**Common Issues:**
- **Model not found**: Run `python scripts/download_model.py`
- **Dependencies**: Run `pip install -r requirements.txt` 
- **Web UI**: Navigate to http://localhost:8000
- **Logs**: Check `logs/chatbot.log` for errors

**Clean up models:**
```bash
python utils/cleanup_models.py  # Free disk space
```
