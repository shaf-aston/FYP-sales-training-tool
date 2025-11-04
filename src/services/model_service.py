"""
AI Model loading and management service with lazy loading
"""
import time
import logging
from pathlib import Path
import pickle
import sys

from config.settings import (
  ENABLE_4BIT, ENABLE_ACCELERATE, ENABLE_OPTIMUM, MODEL_CACHE_DIR
)

# Ensure utils directory is in the Python path
utils_path = Path(__file__).resolve().parent.parent / "utils"
if str(utils_path) not in sys.path:
    sys.path.insert(0, str(utils_path))

# Lazy loading globals
torch = None
pipeline = None
AutoTokenizer = None
AutoModelForCausalLM = None
_transformers_loaded = False

def _lazy_load_transformers():
    """Lazy load transformers and torch"""
    global torch, pipeline, AutoTokenizer, AutoModelForCausalLM, _transformers_loaded
    
    if _transformers_loaded:
        return True
        
    try:
        import torch as _torch
        from transformers import pipeline as _pipeline, AutoTokenizer as _AutoTokenizer, AutoModelForCausalLM as _AutoModelForCausalLM
        
        torch = _torch
        pipeline = _pipeline
        AutoTokenizer = _AutoTokenizer
        AutoModelForCausalLM = _AutoModelForCausalLM
        _transformers_loaded = True
        
        logging.info("✅ Transformers and PyTorch loaded successfully")
        return True
    except ImportError as e:
        logging.error(f"❌ Failed to load transformers: {e}")
        logging.error("Please install: pip install transformers torch")
        return False

logger = logging.getLogger(__name__)

class ModelService:
  """Service for managing AI model loading and inference with lazy loading"""
  
  def __init__(self):
    self.pipe = None
    self.model_name = None
    self._model_loaded = False
    self._loading_in_progress = False
    self.cache_file = Path(MODEL_CACHE_DIR) / "model_cache.pkl"

  def _load_pipeline(self, model_name: str):
    """Load model and return a text-generation pipeline with timing logs."""
    # Check if cached model exists
    if self.cache_file.exists():
      try:
        with open(self.cache_file, "rb") as f:
          self.pipe = pickle.load(f)
        self._model_loaded = True
        logger.info("✅ Loaded model from cache.")
        return self.pipe
      except Exception as e:
        logger.warning(f"⚠️ Failed to load model from cache: {e}")

    # Lazy load transformers first
    if not _lazy_load_transformers():
      logger.error("Failed to load transformers - falling back to simple responses")
      return None

    start_time = time.time()
    logger.info("🚀 Starting model loading process...")

    # Tokenizer
    tok_start = time.time()
    logger.info("⏳ Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
      model_name,
      cache_dir=MODEL_CACHE_DIR,
      trust_remote_code=True
    )
    tok_time = time.time() - tok_start
    logger.info(f"✅ Tokenizer loaded in {tok_time:.2f}s")

    # Model
    preferred_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    model_start = time.time()
    logger.info("⏳ Loading model weights...")
    model = AutoModelForCausalLM.from_pretrained(
      pretrained_model_name_or_path=model_name,
      cache_dir=MODEL_CACHE_DIR,
      trust_remote_code=True,
      torch_dtype=preferred_dtype,
      low_cpu_mem_usage=True
    )
    mdl_time = time.time() - model_start
    logger.info(f"✅ Model weights loaded in {mdl_time:.2f}s")

    # Move to CUDA if available
    if torch.cuda.is_available():
      try:
        cuda_start = time.time()
        model = model.to("cuda")
        cuda_time = time.time() - cuda_start
        logger.info(f"📦 Model moved to CUDA device in {cuda_time:.2f}s")
      except Exception as e:
        logger.warning(f"Failed to move model to CUDA: {e}")

    # Pipeline
    pipe_start = time.time()
    logger.info("⏳ Initializing text-generation pipeline...")
    pipe = pipeline(
      "text-generation",
      model=model,
      tokenizer=tokenizer,
      device=(0 if torch.cuda.is_available() else -1),
      batch_size=1,
      return_full_text=False,
      # Updated for better responses: increased tokens, enable sampling
      max_new_tokens=200,     # Increased for detailed responses
      do_sample=True,         # Enable sampling for natural variation
      temperature=0.85,       # Slightly creative
      repetition_penalty=1.15, # Prevent repetition
      num_beams=1,            # Fast greedy decoding
    )
    pipe_time = time.time() - pipe_start
    logger.info(f"✅ Pipeline initialized in {pipe_time:.2f}s")

    total_time = time.time() - start_time
    logger.info(f"✅ Total model loading time: {total_time:.2f}s (tokenizer: {tok_time:.2f}s, model: {mdl_time:.2f}s, pipeline: {pipe_time:.2f}s)")
    
    # Cache the loaded pipeline
    try:
      with open(self.cache_file, "wb") as f:
        pickle.dump(pipe, f)
      logger.info("✅ Model pipeline cached successfully.")
    except Exception as e:
      logger.warning(f"⚠️ Failed to cache model pipeline: {e}")

    return pipe
  
  def initialize_model(self, model_name: str):
    """Initialize the AI model pipeline with lazy loading"""
    logger.info(f"🚀 Preparing model service for: {model_name}")
    
    # Store model name for lazy loading
    self.model_name = model_name
    self._model_loaded = False
    
    # Don't actually load the model yet - use lazy loading for faster startup
    logger.info("✅ Model service ready (lazy loading enabled)")
    return True

  def _ensure_model_loaded(self):
    """Ensure model is loaded (lazy loading)"""
    if self._model_loaded and self.pipe is not None:
        return True
    
    if self._loading_in_progress:
        logger.warning("Model loading already in progress...")
        return False
    
    if not self.model_name:
        logger.error("❌ No model name set for loading")
        return False
    
    self._loading_in_progress = True
    retry_attempts = 3
    for attempt in range(1, retry_attempts + 1):
      try:
        logger.info(f"⏳ Attempt {attempt} to load model...")
        # First check if transformers is available
        if not _lazy_load_transformers():
            logger.error("❌ Transformers not available - cannot load model")
            return False
        
        # Try to get model config
        try:
            from env import assert_model_present
            # Ensure model exists locally before attempting load
            mdir = assert_model_present(self.model_name)
            logger.info(f"✅ Validated local model directory: {mdir}")
        except Exception as e:
            logger.warning(f"⚠️ Could not validate model directory: {e}")
            logger.info("Will attempt to download model from HuggingFace...")
        
        # Load pipeline with optimizations
        load_start = time.time()
        logger.info(f"⏳ Loading model {self.model_name} on first use...")
        
        try:
            self.pipe = self._load_pipeline(self.model_name)
            if self.pipe is None:
                logger.error("❌ Pipeline loading returned None")
                return False
            logger.info("✅ Model pipeline loaded successfully")
            self._model_loaded = True
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load optimized pipeline: {e}")
            # Try simpler fallback
            try:
                logger.info("Attempting standard pipeline loading...")
                self.pipe = pipeline(
                    "text-generation", 
                    model=self.model_name, 
                    trust_remote_code=True,
                    device=-1  # CPU
                )
                logger.info("✅ Standard pipeline loaded successfully")
                self._model_loaded = True
                return True
            except Exception as e2:
                logger.exception(f"❌ Standard pipeline also failed: {e2}")
                return False
        
        load_duration = time.time() - load_start
        logger.info(f"✅ Model ready in {load_duration:.2f}s (lazy load)")
        self._model_loaded = True
        return True
        
      except Exception as e:
        logger.error(f"❌ Attempt {attempt} failed: {e}")
        time.sleep(2)  # Backoff before retry

    logger.error("❌ All attempts to load the model failed. Falling back to default responses.")
    self._loading_in_progress = False
    return False
  
  def get_pipeline(self):
    """Get the loaded pipeline with lazy loading"""
    if not self._model_loaded or self.pipe is None:
      success = self._ensure_model_loaded()
      if not success:
        logger.error("❌ Failed to load model pipeline")
        return None
    return self.pipe
  
  def get_model_name(self):
    """Get the loaded model name"""
    return self.model_name

  def preload_model(self):
    """Preload the model during application startup."""
    if not self.model_name:
      logger.error("❌ No model name set for preloading")
      return False

    logger.info("🚀 Preloading model during startup...")
    success = self._ensure_model_loaded()
    if success:
      logger.info("✅ Model preloaded successfully.")
    else:
      logger.error("❌ Model preloading failed.")
    return success

# Global model service instance
model_service = ModelService()