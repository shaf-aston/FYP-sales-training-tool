"""
AI Model loading and management service with lazy loading
"""
import time
import logging
from pathlib import Path

from config.settings import (
  ENABLE_4BIT, ENABLE_ACCELERATE, ENABLE_OPTIMUM, MODEL_CACHE_DIR
)

# Lazy loading globals
torch = None
pipeline = None
AutoTokenizer = None
AutoModelForCausalLM = None

def _lazy_load_transformers():
    """Lazy load transformers and torch"""
    global torch, pipeline, AutoTokenizer, AutoModelForCausalLM
    if pipeline is None:
        try:
            import torch as _torch
            from transformers import pipeline as _pipeline, AutoTokenizer as _AutoTokenizer, AutoModelForCausalLM as _AutoModelForCausalLM
            
            torch = _torch
            pipeline = _pipeline
            AutoTokenizer = _AutoTokenizer
            AutoModelForCausalLM = _AutoModelForCausalLM
            
            logging.info("✅ Transformers and PyTorch loaded successfully")
            return True
        except ImportError as e:
            logging.error(f"Failed to load transformers: {e}")
            return False
    return True

logger = logging.getLogger(__name__)

class ModelService:
  """Service for managing AI model loading and inference"""
  
  def __init__(self):
    self.pipe = None
    self.model_name = None
  
  def _load_pipeline(self, model_name: str):
    """Load model and return a text-generation pipeline with timing logs."""
    # Lazy load transformers first
    if not _lazy_load_transformers():
      logger.error("Failed to load transformers - falling back to simple responses")
      return None
    
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
    
    # Apply BetterTransformer for CPU inference speedup if available
    if not torch.cuda.is_available():
      try:
        from optimum.bettertransformer import BetterTransformer
        model = BetterTransformer.transform(model)
        logger.info("🔥 BetterTransformer applied for CPU optimization")
      except Exception as e:
        logger.warning(f"BetterTransformer not available: {e}")
    
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
      return_full_text=False,
      # Balanced optimizations: longer responses but still fast
      max_new_tokens=120,  # Increased for complete sentences
      do_sample=False,
      num_beams=1,
    )
    pipe_time = time.time() - pipe_start
    total_time = time.time() - start_time
    logger.info(f"⏱️ Pipeline created in {pipe_time:.2f}s | TOTAL model load: {total_time:.2f}s")
    logger.info(f"🎯 Pipeline optimized: greedy decoding, max_tokens=120, batch=1")
    return pipe
  
  def initialize_model(self, model_name: str):
    """Initialize the AI model pipeline with lazy loading"""
    logger.info(f"🚀 Preparing to load model: {model_name}")
    
    # Store model name for lazy loading
    self.model_name = model_name
    
    # Don't actually load the model yet - use lazy loading
    logger.info("✅ Model service ready (lazy loading enabled)")
    return True

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
    """Get the loaded pipeline with lazy loading"""
    if self.pipe is None and self.model_name:
      # Lazy load the pipeline when first requested
      load_start = time.time()
      logger.info(f"⏳ Loading model {self.model_name} on first use...")
      self.pipe = self._load_pipeline(self.model_name)
      load_duration = time.time() - load_start
      logger.info(f"✅ Model ready in {load_duration:.2f}s (lazy load)")
    return self.pipe
  
  def get_model_name(self):
    """Get the loaded model name"""
    return self.model_name

# Global model service instance
model_service = ModelService()