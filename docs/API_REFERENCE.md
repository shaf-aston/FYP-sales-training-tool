# API Reference (Unified)

This project exposes a small, consistent set of endpoints under `/api` for the frontend and external clients. The legacy `/api/v2/*` endpoints remain available for backward compatibility but are considered deprecated.

## Sessions

- POST `/api/sessions/start`
  - Body: `{ "user_id": "demo_user_123", "persona_name": "Mary" }`
  - Returns: `{ "status": "session_started", "session_id": "...", "persona_name": "Mary" }`

- POST `/api/sessions/end`
  - Body: `{ "user_id": "demo_user_123", "session_id": "...", "persona_name": "Mary" }`
  - Returns: feedback summary with duration and optional `feedback_report`.

## Chat

- POST `/api/chat`
  - Body: `{ "message": "Hi", "user_id": "demo_user_123", "session_id": "...", "persona_name": "Mary" }`
  - Returns: `{ "response": "...", "session_id": "...", "persona_name": "Mary", ... }`

## Personas

- GET `/api/personas`
  - Returns: `{ "personas": [{ name, description, personality_traits, communication_style }, ...] }`

- GET `/api/personas/{persona_name}/context`
  - Returns: `{ "success": true, "persona_name": "Mary", "context": { persona_info, conversation_style } }`

## Progress (Dashboard)

- GET `/api/progress/initialize?user_id=demo_user_123`
- GET `/api/progress/{user_id}/dashboard`

## Migration Map (v2 → unified)

| Old (v2) | New (/api) |
|---|---|
| GET `/api/v2/personas` | GET `/api/personas` |
| GET `/api/v2/personas/{name}/context` | GET `/api/personas/{name}/context` |
| POST `/api/v2/personas/start-session` | POST `/api/sessions/start` |
| POST `/api/v2/personas/end-session` | POST `/api/sessions/end` |
| POST `/api/v2/personas/{name}/chat` | POST `/api/chat` |
| GET `/api/v2/progress/initialize` | GET `/api/progress/initialize` |
| GET `/api/v2/progress/{user}/dashboard` | GET `/api/progress/{user}/dashboard` |

## Notes

- All endpoints are CORS-enabled based on settings in `config/settings.py`.
- The model is loaded on app startup; chat requests are served via the shared pipeline.
- Persona names currently supported: Mary, Jake, Sarah, David (see `models/character_profiles.py`).
