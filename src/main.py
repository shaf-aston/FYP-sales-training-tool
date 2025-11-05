"""
Main FastAPI application entry point for AI Sales Training Chatbot
Modular architecture with clean separation of concerns
"""
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import psutil
import time
import os
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

# Project imports
from infrastructure.settings import (
  APP_TITLE, APP_VERSION, CORS_ORIGINS, STATIC_DIR, LOGS_DIR, DEFAULT_MODEL
)
from services.model_service import model_service
from api import api_router
from utils.logger_config import setup_logging

# Initialize logging
setup_logging(LOGS_DIR)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
  """Create and configure FastAPI application"""
  
  # Create FastAPI app
  app = FastAPI(title=APP_TITLE, version=APP_VERSION)
  
  # Configure CORS middleware
  app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-production-domain.com"],  # Restrict to specific origins
    allow_methods=["GET", "POST"],  # Restrict to necessary methods
    allow_headers=["Authorization", "Content-Type"],  # Restrict to necessary headers
    allow_credentials=True
  )
  
  # Mount static files
  app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
  
  # Include API routes
  app.include_router(api_router)
  
  return app

async def initialize_services_async():
  """Initialize all application services asynchronously"""
  logger.info("🚀 Initializing AI Sales Training System...")
  
  # Initialize model service with proper model name
  from services.model_service import model_service
  logger.info(f"📦 Initializing AI model: {DEFAULT_MODEL}")
  model_service.initialize_model(DEFAULT_MODEL)
  
  logger.info("✅ All services initialized successfully")

def initialize_services():
  """Initialize critical services only (for fast startup)"""
  logger.info("🚀 Fast startup mode - AI Sales Training System...")
  
  # Initialize model service with model name (lazy loading)
  from services.model_service import model_service
  logger.info(f"📦 Setting model for lazy loading: {DEFAULT_MODEL}")
  model_service.initialize_model(DEFAULT_MODEL)
  
  logger.info("📦 Model will load on first request (lazy loading)")
  logger.info("✅ Critical services ready")

def validate_environment_variables():
    """Validate critical environment variables"""
    # Only check for MODEL_NAME if not set in config
    if not os.getenv("MODEL_NAME") and not DEFAULT_MODEL:
        raise EnvironmentError("❌ Missing required environment variable: MODEL_NAME or DEFAULT_MODEL")

# Validate environment variables during startup
validate_environment_variables()

# Create FastAPI application
app = create_app()

@app.on_event("startup")
async def startup_event():
  """Application startup event handler - optimized for speed"""
  # Fast startup - initialize with model name set
  initialize_services()
  logger.info("🎯 AI Sales Training Chatbot server ready! (Models load on-demand)")

@app.on_event("shutdown")
async def shutdown_event():
  """Application shutdown event handler"""
  logger.info("🛑 Shutting down AI Sales Training System...")

# Add a simple health check endpoint directly
@app.get("/api/health")
async def health_check():
    """Extended health check endpoint with detailed metrics"""
    from services.model_service import model_service

    # Measure response time
    start_time = time.time()
    model_loaded = model_service._model_loaded
    model_name = model_service.model_name
    response_time = time.time() - start_time

    # Get memory usage
    memory_info = psutil.virtual_memory()
    memory_usage = {
        "total": memory_info.total,
        "available": memory_info.available,
        "used": memory_info.used,
        "percent": memory_info.percent,
    }

    # Get active connections
    active_connections = len(psutil.net_connections())

    return {
        "status": "healthy",
        "model_loaded": model_loaded,
        "model_name": model_name,
        "version": APP_VERSION,
        "response_time": response_time,
        "memory_usage": memory_usage,
        "active_connections": active_connections,
    }