"""
AI Model loading and management service with lazy loading
"""
import logging
import time
import pickle
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import tempfile
import shutil
# Import centralized config
from config.config_loader import config

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)

# Global variables for lazy-loaded modules
_torch_local = None
AutoTokenizer = None
AutoModelForCausalLM = None
pipeline = None

def _lazy_load_transformers():
    """Lazy load transformers and its dependencies."""
    global AutoTokenizer, AutoModelForCausalLM, pipeline, _torch_local
    if _torch_local is None:
        try:
            import torch as torch_local
            from transformers import AutoTokenizer as AutoTokenizer_local, AutoModelForCausalLM as AutoModelForCausalLM_local, pipeline as pipeline_local
            _torch_local = torch_local
            AutoTokenizer = AutoTokenizer_local
            AutoModelForCausalLM = AutoModelForCausalLM_local
            pipeline = pipeline_local
            logger.info("Successfully lazy-loaded torch and transformers.")
            return True
        except ImportError as e:
            logger.error(f"Failed to lazy-load transformers: {e}")
            return False
    return True

class ModelService:
    def __init__(self):
        self.model_name: str | None = None
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        self._load_lock = asyncio.Lock()
        self._model_loaded_event = asyncio.Event()
        self.cache_dir: Path | None = None
        self._load_error: Exception | None = None

    def initialize_model(self, model_name: str = None, cache_dir: Path = None):
        """Set the model name and cache directory for lazy loading. Uses config if not provided."""
        # Use config loader for model name
        if model_name is None:
            model_name = config.get("llm.model_name")
        self.model_name = model_name
        # Use config for endpoint if needed (not used here, but available)
        self.endpoint = config.get("llm.endpoint")
        if cache_dir is not None:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = Path(config.get("llm.cache_dir", "model_cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Model '{self.model_name}' initialized for lazy loading.")

    async def load_model_async(self):
        """Run the synchronous model loading in a thread pool."""
        # only one loader at a time
        async with self._load_lock:
            if self._model_loaded_event.is_set():
                return
            logger.info("Scheduling model loading in background.")
            loop = asyncio.get_running_loop()
            # Run the synchronous _load_model in a separate thread
            try:
                await loop.run_in_executor(_executor, self._load_model_sync)
            except Exception as e:
                self._load_error = e
                logger.exception("Model loading failed")
                raise
            else:
                self._model_loaded_event.set()
                logger.info("✅ Model loading background task finished and event is set.")


    def _load_model_sync(self):
        """Load model and return a text-generation pipeline with timing logs."""
        # ensure transformers are available
        if not _lazy_load_transformers():
            raise ImportError("transformers not available")

        # load cache if model/tokenizer were saved with save_pretrained()
        model_cache_dir = self.cache_dir / self.model_name.replace("/", "_")
        if model_cache_dir.exists():
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(str(model_cache_dir))
                self.model = AutoModelForCausalLM.from_pretrained(str(model_cache_dir), low_cpu_mem_usage=True)
                logger.info("Loaded model/tokenizer from cache dir")
            except Exception:
                logger.warning("Cache load failed; will re-download")

        if self.model is None:
            # download and then save locally (atomic)
            tokenizer = AutoTokenizer.from_pretrained(self.model_name, cache_dir=self.cache_dir, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir,
                trust_remote_code=True,
                low_cpu_mem_usage=True
            )
            # use temp dir then atomically move
            tmp = tempfile.TemporaryDirectory(dir=self.cache_dir)
            tmpd = Path(tmp.name)
            tokenizer.save_pretrained(tmpd)
            model.save_pretrained(tmpd)
            dest = model_cache_dir
            if dest.exists():
                shutil.rmtree(dest)
            tmpd.rename(dest)
            self.tokenizer, self.model = AutoTokenizer.from_pretrained(dest), AutoModelForCausalLM.from_pretrained(dest)
            tmp.cleanup()

        # move to cuda if available
        if _torch_local.cuda.is_available():
            try:
                self.model.to("cuda")
            except Exception as e:
                logger.warning("Moving to cuda failed: %s", e)

        # reduce memory usage during pipeline init
        self.model.eval()
        with _torch_local.no_grad():
            self.pipeline = pipeline("text-generation",
                                     model=self.model,
                                     tokenizer=self.tokenizer,
                                     device=(0 if _torch_local.cuda.is_available() else -1),
                                     return_full_text=False,
                                     max_new_tokens=200,
                                     do_sample=True)
        logger.info("Model pipeline ready")

    async def get_pipeline(self):
        """Get the loaded pipeline with lazy loading. Waits for model to be loaded."""
        if not self._model_loaded_event.is_set():
            logger.info("Waiting for model to be loaded...")
            await self._model_loaded_event.wait()
        
        if not self.pipeline:
            logger.error("❌ Failed to load model pipeline")
            return None
            
        return self.pipeline

    def get_model_name(self):
        """Get the loaded model name from config."""
        return config.get("llm.model_name")

model_service = ModelService()
