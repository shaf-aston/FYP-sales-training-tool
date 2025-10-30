"""
Main FastAPI application entry point for AI Sales Training Chatbot
Modular architecture with clean separation of concerns
"""
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Project imports
from config.settings import (
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
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
  )
  
  # Mount static files
  app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
  
  # Include API routes
  app.include_router(api_router)
  
  return app

def initialize_services():
  """Initialize all application services"""
  logger.info("🚀 Initializing AI Sales Training System...")
  
  # Initialize model service
  logger.info("📦 Loading AI model...")
  model_service.initialize_model(DEFAULT_MODEL)
  logger.info("✅ Model service initialized")
  
  logger.info("✅ All services initialized successfully")

# Create FastAPI application
app = create_app()

@app.on_event("startup")
async def startup_event():
  """Application startup event handler"""
  initialize_services()
  logger.info("🎯 AI Sales Training Chatbot is ready for training sessions!")

@app.on_event("shutdown")
async def shutdown_event():
  """Application shutdown event handler"""
  logger.info("🛑 Shutting down AI Sales Training System...")