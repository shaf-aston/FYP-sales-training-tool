"""
API router configuration
"""
from fastapi import APIRouter
from .routes.chat_routes import router as chat_router
from .routes.system_routes import router as system_router
from .routes.web_routes import router as web_router

# Create main API router
api_router = APIRouter()

# Include route modules with prefixes
api_router.include_router(chat_router, prefix="/api", tags=["chat"])
api_router.include_router(system_router, prefix="", tags=["system"])
api_router.include_router(web_router, prefix="", tags=["web"])