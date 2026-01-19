# Backend API Reference

**Document Purpose**: Technical reference for backend API endpoints showing available routes, HTTP methods, and purposes. Used for frontend integration and testing.

---

## Functional Endpoints

| **Endpoint**               | **Method** | **Purpose**                                   |
|----------------------------|------------|-----------------------------------------------|
| `/api/chat`                | `POST`     | Main chat endpoint for conversations.         |
| `/chat`                    | `POST`     | Legacy chat endpoint.                         |
| `/api/reset-conversation`  | `POST`     | Reset conversation history.                   |
| `/api/greeting`            | `GET`      | Fetch chatbot's initial greeting.             |
| `/api/character`           | `GET`      | Retrieve chatbot's character profile.         |
| `/api/conversation-stats`  | `GET`      | Get statistics about conversations.           |
| `/health`                  | `GET`      | Check system health and performance metrics.  |

## Key Backend Communication Details

- **Chat Logic**: The `/api/chat` endpoint uses the `chat_with_mary` function to process user messages and generate responses using the AI pipeline.
- **Session Management**: The `ContextTracker` class manages conversation history, emotional hooks, and session data.
- **Reset Functionality**: The `/api/reset-conversation` endpoint clears session data for a fresh start.
- **Character Details**: The `/api/character` and `/api/greeting` endpoints provide information about the chatbot's persona.
- **Health Check**: The `/health` endpoint ensures the backend is running and provides performance metrics.