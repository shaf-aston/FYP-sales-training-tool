"""
API router configuration
"""
from fastapi import APIRouter
from .routes.chat_routes import router as chat_router
from .routes.system_routes import router as system_router
from .routes.web_routes import router as web_router
from .routes.enhanced_routes import enhanced_router
from .routes.voice_routes import router as voice_router
from .routes.persona_chat_routes import persona_chat_router
from .routes.dashboard_routes import router as dashboard_router
from .routes.sessions_routes import router as sessions_router
from .routes.persona_admin_routes import router as persona_admin_router
from .routes.team_routes import router as team_router
from .routes.external_routes import router as external_router
from .routes.training_routes import training_router
from .routes.feedback_routes import feedback_router
from .routes.general_chat_routes import general_chat_router
from .routes.testing_routes import testing_router

# Create main API router
api_router = APIRouter()

# Include route modules with prefixes
api_router.include_router(chat_router, prefix="/api", tags=["chat"])
api_router.include_router(system_router, prefix="", tags=["system"])
api_router.include_router(web_router, prefix="", tags=["web"])
api_router.include_router(enhanced_router, tags=["enhanced"])  # Enhanced training features
api_router.include_router(voice_router, tags=["voice"])  # Voice processing routes
api_router.include_router(persona_chat_router, tags=["persona-chat"])  # Persona-specific chat routes
api_router.include_router(dashboard_router, prefix="", tags=["dashboard"])  # Dashboard and progress routes
api_router.include_router(sessions_router, tags=["sessions"])  # Unified session routes under /api
api_router.include_router(persona_admin_router, tags=["persona-admin"])  # Persona cloning & management
api_router.include_router(team_router, tags=["team"])  # Team training features
api_router.include_router(external_router, tags=["external"])  # External read-only integration
api_router.include_router(training_router, tags=["training"])  # Training session management
api_router.include_router(feedback_router, tags=["feedback"])  # Session feedback and analytics
api_router.include_router(general_chat_router, tags=["general-chat"])  # General chat (renamed from Direct Chat)
api_router.include_router(testing_router, tags=["testing"])  # Comprehensive API testing endpoints