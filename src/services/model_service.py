"""
AI Model loading and management service
"""
import torch
import time
import logging
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
from pathlib import Path

from config.settings import (
  ENABLE_4BIT, ENABLE_ACCELERATE, ENABLE_OPTIMUM, MODEL_CACHE_DIR
)

logger = logging.getLogger(__name__)

class ModelService:
  """Service for managing AI model loading and inference"""
  
  def __init__(self):
    self.pipe = None
    self.model_name = None
  
  def _load_pipeline(self, model_name: str):
    """Load model with progressive optimization attempts - CPU optimized."""
    start_time = time.time()
    logger.info("🚀 Starting FAST model loading process...")
    
    # Set torch to use all CPU cores
    torch.set_num_threads(torch.get_num_threads())  # Use all available cores
    
    # Tokenizer loading timing
    tokenizer_start = time.time()
    tokenizer = AutoTokenizer.from_pretrained(
      model_name,
      cache_dir=MODEL_CACHE_DIR,
      trust_remote_code=True
    )
    tokenizer_time = time.time() - tokenizer_start
    logger.info(f"⏱️ Tokenizer loaded in {tokenizer_time:.2f} seconds")

    model_kwargs = dict(
      cache_dir=MODEL_CACHE_DIR,
      trust_remote_code=True,
      pretrained_model_name_or_path=model_name,
      torch_dtype=torch.float32,  # Use float32 for CPU (faster than float16 on CPU)
      low_cpu_mem_usage=True      # Optimize CPU memory usage
    )

    loaded_with = "standard"

    # Try bitsandbytes 4-bit
    if ENABLE_4BIT:
      try:
        import bitsandbytes  # noqa: F401
        model_kwargs.update({
          "load_in_4bit": True,
          "device_map": "auto"
        })
        loaded_with = "4bit-bnb"
        logger.info("Attempting 4-bit quantization with bitsandbytes")
      except ImportError:
        logger.warning("bitsandbytes not available, skipping 4-bit quantization")
      except Exception as e:
        logger.warning(f"4-bit quantization failed: {e}")

    # Try accelerate device mapping if not already set
    if ENABLE_ACCELERATE and "device_map" not in model_kwargs:
      try:
        from accelerate import infer_auto_device_map  # noqa: F401
        model_kwargs["device_map"] = "auto"
        loaded_with = loaded_with + "+accelerate"
        logger.info("Using accelerate for device mapping")
      except ImportError:
        logger.warning("accelerate not available")
      except Exception as e:
        logger.warning(f"accelerate setup failed: {e}")

    # Model loading timing
    model_start = time.time()
    logger.info(f"📦 Loading model with config: {model_kwargs}")
    model = AutoModelForCausalLM.from_pretrained(**model_kwargs)
    model_time = time.time() - model_start
    logger.info(f"⏱️ Model loaded in {model_time:.2f} seconds")

    # Try optimum BetterTransformer optimization
    if ENABLE_OPTIMUM:
      opt_start = time.time()
      try:
        from optimum.bettertransformer import BetterTransformer
        model = BetterTransformer.transform(model)
        loaded_with = loaded_with + "+bettertransformer"
        opt_time = time.time() - opt_start
        logger.info(f"⏱️ BetterTransformer applied in {opt_time:.2f} seconds")
      except ImportError:
        logger.warning("optimum not available, skipping BetterTransformer")
      except Exception as e:
        logger.warning(f"BetterTransformer optimization failed: {e}")

    # Pipeline creation timing - CPU optimized
    pipeline_start = time.time()
    pipe = pipeline(
      "text-generation",
      model=model,
      tokenizer=tokenizer,
      device=-1,  # Force CPU device
      batch_size=1,  # Single batch for faster processing
      return_full_text=False  # Only return generated text
    )
    pipeline_time = time.time() - pipeline_start
    logger.info(f"⏱️ Pipeline created in {pipeline_time:.2f} seconds")

    total_time = time.time() - start_time
    logger.info(f"✅ TOTAL model loading time: {total_time:.2f} seconds with {loaded_with}")
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