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

from infrastructure.settings import (
  APP_TITLE, APP_VERSION, CORS_ORIGINS, STATIC_DIR, LOGS_DIR, DEFAULT_MODEL
)
from services.ai_services import model_service
from api import api_router
from utils.logger_config import setup_logging

setup_logging(LOGS_DIR)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
  app = FastAPI(title=APP_TITLE, version=APP_VERSION)
  
  app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-production-domain.com"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=True
  )
  
  app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
  
  app.include_router(api_router)
  
  return app

async def initialize_services_async():
  logger.info("🚀 Initializing AI Sales Training System...")
  
  from services.model_service import model_service
  logger.info(f"📦 Initializing AI model: {DEFAULT_MODEL}")
  model_service.initialize_model(DEFAULT_MODEL)
  
  logger.info("✅ All services initialized successfully")

def initialize_services():
  logger.info("🚀 Fast startup mode - AI Sales Training System...")
  
  from services.model_service import model_service
  logger.info(f"📦 Setting model for lazy loading: {DEFAULT_MODEL}")
  model_service.initialize_model(DEFAULT_MODEL)
  
  logger.info("📦 Model will load on first request (lazy loading)")
  logger.info("✅ Critical services ready")

def validate_environment_variables():
    if not os.getenv("MODEL_NAME") and not DEFAULT_MODEL:
        raise EnvironmentError("❌ Missing required environment variable: MODEL_NAME or DEFAULT_MODEL")

validate_environment_variables()

app = create_app()

@app.on_event("startup")
async def startup_event():
  initialize_services()
  logger.info("🎯 AI Sales Training Chatbot server ready! (Models load on-demand)")

@app.on_event("shutdown")
async def shutdown_event():
  logger.info("🛑 Shutting down AI Sales Training System...")

@app.get("/api/health")
async def health_check():
    from services.model_service import model_service

    start_time = time.time()
    model_loaded = model_service._model_loaded
    model_name = model_service.model_name
    response_time = time.time() - start_time

    memory_info = psutil.virtual_memory()
    memory_usage = {
        "total": memory_info.total,
        "available": memory_info.available,
        "used": memory_info.used,
        "percent": memory_info.percent,
    }

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