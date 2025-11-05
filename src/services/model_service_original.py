"""
AI Model loading and management service
"""
import torch
import time
import logging
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
from pathlib import Path

from infrastructure.settings import (
  ENABLE_4BIT, ENABLE_ACCELERATE, ENABLE_OPTIMUM, MODEL_CACHE_DIR
)

logger = logging.getLogger(__name__)

class ModelService:
  """Service for managing AI model loading and inference"""
  
  def __init__(self):
    self.pipe = None
    self.model_name = None
  
  def _load_pipeline(self, model_name: str):
    """Load model and return a text-generation pipeline with timing logs."""
    start_time = time.time()
    logger.info("🚀 Starting model loading process...")

    # Tokenizer
    tok_start = time.time()
    tokenizer = AutoTokenizer.from_pretrained(
      model_name,
      cache_dir=MODEL_CACHE_DIR,
      trust_remote_code=True
    )
    tok_time = time.time() - tok_start
    logger.info(f"⏱️ Tokenizer loaded in {tok_time:.2f}s")

    # Model
    preferred_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    model_start = time.time()
    model = AutoModelForCausalLM.from_pretrained(
      pretrained_model_name_or_path=model_name,
      cache_dir=MODEL_CACHE_DIR,
      trust_remote_code=True,
      torch_dtype=preferred_dtype,
      low_cpu_mem_usage=True
    )
    if torch.cuda.is_available():
      try:
        model = model.to("cuda")
        logger.info("📦 Model moved to CUDA device")
      except Exception as e:
        logger.warning(f"Failed to move model to CUDA: {e}")
    mdl_time = time.time() - model_start
    logger.info(f"⏱️ Model loaded in {mdl_time:.2f}s (dtype={preferred_dtype})")

    # Pipeline
    pipe_start = time.time()
    pipe = pipeline(
      "text-generation",
      model=model,
      tokenizer=tokenizer,
      device=(0 if torch.cuda.is_available() else -1),
      batch_size=1,
      return_full_text=False
    )
    pipe_time = time.time() - pipe_start
    total_time = time.time() - start_time
    logger.info(f"⏱️ Pipeline created in {pipe_time:.2f}s | TOTAL load: {total_time:.2f}s")
    return pipe
  
  def initialize_model(self, model_name: str):
    """Initialize the AI model pipeline"""
    # Add utils to path for model setup - this should be handled by main.py
    try:
      from utils.env import setup_model_env, assert_model_present
    except ImportError:
      import sys
      utils_path = str(Path(__file__).resolve().parent.parent.parent / "utils")
      if utils_path not in sys.path:
        sys.path.insert(0, utils_path)
      from utils.env import setup_model_env, assert_model_present
    
    # Centralized environment & offline configuration
    configured_model = setup_model_env()
    logger.info(f"Configured environment for model: {configured_model}")

    # Ensure model exists locally before attempting load
    try:
      mdir = assert_model_present(configured_model)
      logger.info(f"Validated local model directory: {mdir}")
    except RuntimeError as e:
      logger.error(str(e))
      raise

    # Load pipeline with optimizations
    try:
      self.pipe = self._load_pipeline(configured_model)
      self.model_name = configured_model
      logger.info("Model pipeline loaded successfully with optimizations")
    except Exception as e:
      logger.exception("Failed to initialize optimized model pipeline, falling back to standard")
      try:
        self.pipe = pipeline("text-generation", model=configured_model, trust_remote_code=True)
        self.model_name = configured_model
        logger.info("Standard pipeline loaded successfully")
      except Exception as fallback_error:
        logger.exception("Both optimized and standard pipeline loading failed")
        raise
  
  def get_pipeline(self):
    """Get the loaded pipeline"""
    return self.pipe
  
  def get_model_name(self):
    """Get the loaded model name"""
    return self.model_name

# Global model service instance
model_service = ModelService()