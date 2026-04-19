"""Unit tests for web routes: voice and prospect endpoints."""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from io import BytesIO
import json


@pytest.fixture
def app():
    """Create a Flask app for testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    # Register blueprints
    from web.routes.voice import bp as voice_bp, init_routes as voice_init
    from web.routes.prospect import bp as prospect_bp, init_routes as prospect_init

    # Mock dependencies
    voice_init(
        app,
        require_session_func=lambda: (MagicMock(), None),
        validate_message_func=lambda x: (x, None),
        bot_state_func=lambda: MagicMock(),
    )

    prospect_init(
        app,
        prospect_session_manager_obj=MagicMock(),
        validate_message_func=lambda x: (x, None),
    )

    app.register_blueprint(voice_bp)
    app.register_blueprint(prospect_bp)

    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


class TestVoiceStatus:
    """Test GET /api/voice/status endpoint."""

    def test_voice_status_success(self, client):
        """Should return voice provider status."""
        response = client.get("/api/voice/status")
        assert response.status_code == 200


# class TestVoiceTranscribe:
#     """Test POST /api/voice/transcribe endpoint."""
# 
#     def test_transcribe_no_audio_file(self, client):
#         """Should reject request with no audio file."""
#         response = client.post("/api/voice/transcribe", data={})
#         assert response.status_code == 400
# 
#     def test_transcribe_success(self, client):
#         """Should transcribe audio successfully."""
#         with patch("web.routes.voice.get_voice_provider") as mock_get_provider:
#             from chatbot.providers.voice_provider import TranscriptionResult
# 
#             mock_provider = MagicMock()
#             mock_provider.transcribe.return_value = TranscriptionResult(
#                 text="I want to buy this", latency_ms=500.0, provider="deepgram"
#             )
#             mock_get_provider.return_value = mock_provider
# 
#             response = client.post(
#                 "/api/voice/transcribe",
#                 data={"audio": (BytesIO(b"fake_audio"), "audio.webm")},
#             )
#             assert response.status_code == 200
# 
# 
# # class TestVoiceSynthesize:
# #     """Test POST /api/voice/synthesize endpoint."""
# # 
# #     def test_synthesize_no_text(self, client):
# #         """Should reject request with no text."""
# #         response = client.post(
# #             "/api/voice/synthesize",
# #             data=json.dumps({"text": ""}),
# #             content_type="application/json",
# #         )
# #         assert response.status_code == 400
# # 
# # 
# # class TestProspectInit:
#     """Test POST /api/prospect/init endpoint."""
# 
#     def test_prospect_init_invalid_difficulty(self, client):
#         """Should reject invalid difficulty."""
#         response = client.post(
#             "/api/prospect/init",
#             data=json.dumps({"difficulty": "impossible"}),
#             content_type="application/json",
#         )
#         assert response.status_code == 400
# 
#     def test_prospect_init_at_capacity(self, client):
#         """Should return 503 when at capacity."""
#         with patch("web.routes.prospect.bp.prospect_session_manager") as mock_mgr:
#             mock_mgr.can_create.return_value = False
#             response = client.post(
#                 "/api/prospect/init",
#                 data=json.dumps({}),
#                 content_type="application/json",
#             )
#             assert response.status_code == 503
# 
# 
# class TestProspectChat:
    """Test POST /api/prospect/chat endpoint."""

    def test_prospect_chat_missing_session_id(self, client):
        """Should reject request without session ID."""
        response = client.post(
            "/api/prospect/chat",
            data=json.dumps({"message": "Hello"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_prospect_chat_invalid_session(self, client):
        """Should reject invalid session ID."""
        with patch("web.routes.prospect.bp.prospect_session_manager") as mock_mgr:
            mock_mgr.get.return_value = None
            response = client.post(
                "/api/prospect/chat",
                data=json.dumps({"message": "Hello"}),
                headers={"X-Session-ID": "invalid"},
                content_type="application/json",
            )
            assert response.status_code == 400
