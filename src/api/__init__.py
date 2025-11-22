"""
API router configuration
"""
from fastapi import APIRouter
from .routes.chat_routes import router as chat_router
from .routes.system_routes import router as system_router
from .routes.web_routes import router as web_router
from .routes.enhanced_routes import enhanced_router
from .routes.voice_routes import router as voice_router
from .routes.dashboard_routes import router as dashboard_router
from .routes.sessions_routes import router as sessions_router
from .routes.persona_admin_routes import router as persona_admin_router
from .routes.team_routes import router as team_router
from .routes.external_routes import router as external_router
from .routes.training_routes import training_router
from .routes.feedback_routes import feedback_router
from .routes.testing_routes import testing_router

api_router = APIRouter()

api_router.include_router(chat_router, prefix="/api", tags=["chat"])
api_router.include_router(system_router, prefix="", tags=["system"])
api_router.include_router(web_router, prefix="", tags=["web"])
api_router.include_router(enhanced_router, tags=["enhanced"])
api_router.include_router(voice_router, tags=["voice"])
api_router.include_router(dashboard_router, prefix="", tags=["dashboard"])
api_router.include_router(sessions_router, tags=["sessions"])
api_router.include_router(persona_admin_router, tags=["persona-admin"])
api_router.include_router(team_router, tags=["team"])
api_router.include_router(external_router, tags=["external"])
api_router.include_router(training_router, tags=["training"])
api_router.include_router(feedback_router, tags=["feedback"])
api_router.include_router(testing_router, tags=["testing"])