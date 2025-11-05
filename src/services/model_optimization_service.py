"""
Advanced Model Optimization Service for Sales Training System
Handles model caching, tokenizer optimization, configuration management, and performance monitoring
Gracefully handles optional optimization packages with fallback functionality
"""

import os
import json
import time
import logging
import hashlib
import threading
from typing import Dict, Any, Optional, List, Tuple, TYPE_CHECKING
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict

# Core requirements (should always be available)
try:
    import torch
    TORCH_AVAILABLE = True
    logging.info("✅ PyTorch loaded successfully")
except ImportError:
    TORCH_AVAILABLE = False
    logging.error("❌ PyTorch not available - this is required for the system")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logging.warning("NumPy not available - some features will be limited")

try:
    from transformers import (
        AutoTokenizer, AutoModelForCausalLM, 
        PreTrainedTokenizer, PreTrainedModel,
        pipeline, Pipeline
    )
    TRANSFORMERS_AVAILABLE = True
    logging.info("✅ Transformers loaded successfully")
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logging.error("❌ Transformers not available - this is required for the system")
    # Define placeholder types for type hints when transformers is not available
    if TYPE_CHECKING:
        from transformers import PreTrainedTokenizer, PreTrainedModel, Pipeline
    else:
        PreTrainedTokenizer = Any
        PreTrainedModel = Any
        Pipeline = Any
        AutoTokenizer = None
        AutoModelForCausalLM = None
        pipeline = None

# Optional optimization libraries
try:
    import psutil
    PSUTIL_AVAILABLE = True
    logging.info("✅ psutil loaded successfully")
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.info("ℹ️  psutil not available - system monitoring will be limited")
    logging.info("   To enable: pip install psutil")

# Optional: bitsandbytes for quantization
try:
    import bitsandbytes as bnb
    BITSANDBYTES_AVAILABLE = True
    logging.info("✅ bitsandbytes loaded successfully")
except ImportError:
    BITSANDBYTES_AVAILABLE = False
    logging.info("ℹ️  bitsandbytes not available - 4-bit quantization disabled")
    logging.info("   To enable: pip install bitsandbytes")

# Optional: accelerate for device mapping
try:
    from accelerate import infer_auto_device_map
    ACCELERATE_AVAILABLE = True
    logging.info("✅ accelerate loaded successfully")
except ImportError:
    ACCELERATE_AVAILABLE = False
    logging.info("ℹ️  accelerate not available - automatic device mapping disabled")
    logging.info("   To enable: pip install accelerate")

# Optional: optimum for BetterTransformer (handle version conflicts)
try:
    from optimum.bettertransformer import BetterTransformer
    OPTIMUM_AVAILABLE = True
    logging.info("✅ optimum loaded successfully")
except (ImportError, RuntimeError) as e:
    OPTIMUM_AVAILABLE = False
    if "BetterTransformer requires transformers" in str(e):
        logging.info("ℹ️  optimum BetterTransformer disabled - version conflict with transformers")
        logging.info("   Note: BetterTransformer is deprecated in optimum v2.0")
    else:
        logging.info("ℹ️  optimum not available - BetterTransformer optimization disabled")
        logging.info("   To enable: pip install optimum")

from infrastructure.settings import MODEL_CACHE_DIR
try:
    from infrastructure.settings import ENABLE_4BIT, ENABLE_ACCELERATE, ENABLE_OPTIMUM
except ImportError:
    # Fallback values if config doesn't exist
    ENABLE_4BIT = BITSANDBYTES_AVAILABLE
    ENABLE_ACCELERATE = ACCELERATE_AVAILABLE
    ENABLE_OPTIMUM = OPTIMUM_AVAILABLE

logger = logging.getLogger(__name__)

@dataclass
class ModelPerformanceMetrics:
    """Container for model performance metrics"""
    model_name: str
    load_time: float
    memory_usage_mb: float
    inference_time_avg: float
    inference_count: int
    cache_hits: int
    cache_misses: int
    optimization_level: str
    device_type: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass 
class CacheConfig:
    """Configuration for model and tokenizer caching"""
    max_model_cache_size: int = 5  # Maximum number of models to keep in memory
    max_tokenizer_cache_size: int = 10  # Maximum number of tokenizers to keep in memory
    cache_ttl_hours: int = 24  # Time to live for cached items
    enable_disk_cache: bool = True
    enable_memory_cache: bool = True
    cache_compression: bool = False
    preload_models: List[str] = None

    def __post_init__(self):
        if self.preload_models is None:
            self.preload_models = []

class ModelOptimizationService:
    """Advanced service for model optimization, caching, and performance monitoring"""
    
    def __init__(self, cache_config: Optional[CacheConfig] = None):
        # Check for required dependencies - warn but don't crash
        if not TORCH_AVAILABLE or not TRANSFORMERS_AVAILABLE:
            missing = []
            if not TORCH_AVAILABLE:
                missing.append("torch")
            if not TRANSFORMERS_AVAILABLE:
                missing.append("transformers")
            
            logger.warning(
                f"Missing dependencies: {', '.join(missing)}. "
                "Model optimization features will be limited. "
                "To enable: pip install " + " ".join(missing)
            )
            # Initialize with minimal functionality
            self.available = False
            self.cache_config = cache_config or CacheConfig()
            self.model_cache = {}
            self.tokenizer_cache = {}
            self.pipeline_cache = {}
            return
        
        self.available = True
        self.cache_config = cache_config or CacheConfig()
        
        # Caching systems
        self.model_cache = {}  # In-memory model cache
        self.tokenizer_cache = {}  # In-memory tokenizer cache
        self.pipeline_cache = {}  # Pipeline cache
        
        # Cache metadata
        self.cache_metadata = {}
        self.access_times = defaultdict(list)
        self.performance_metrics = {}
        
        # Threading for async operations
        self.cache_lock = threading.RLock()
        self.optimization_lock = threading.RLock()
        
        # Performance monitoring
        self.inference_stats = defaultdict(list)
        self.system_stats = []
        
        # Configuration management
        self.config_history = []
        self.active_optimizations = {}
        
        # Track available optimization features
        self.optimization_features = {
            'quantization': BITSANDBYTES_AVAILABLE,
            'accelerate': ACCELERATE_AVAILABLE,
            'optimum': OPTIMUM_AVAILABLE,
            'torch_compile': hasattr(torch, 'compile'),
            'psutil': PSUTIL_AVAILABLE
        }
        
        # Initialize cache directory structure
        self._initialize_cache_structure()
        
        # Load existing cache metadata
        self._load_cache_metadata()
        
        # Log optimization features status
        self._log_optimization_features()
        
        logger.info("Model Optimization Service initialized")
    
    def _log_optimization_features(self):
        """Log the status of optimization features"""
        logger.info("🚀 Model Optimization Features:")
        logger.info(f"   4-bit Quantization (bitsandbytes): {'✅ Available' if self.optimization_features['quantization'] else '❌ Not available'}")
        logger.info(f"   Device Mapping (accelerate): {'✅ Available' if self.optimization_features['accelerate'] else '❌ Not available'}")
        logger.info(f"   BetterTransformer (optimum): {'✅ Available' if self.optimization_features['optimum'] else '❌ Not available'}")
        logger.info(f"   Torch Compile: {'✅ Available' if self.optimization_features['torch_compile'] else '❌ Not available'}")
        logger.info(f"   System Monitoring (psutil): {'✅ Available' if self.optimization_features['psutil'] else '❌ Not available'}")
        
        missing_features = []
        if not self.optimization_features['quantization']:
            missing_features.append("pip install bitsandbytes  # For 4-bit quantization")
        if not self.optimization_features['accelerate']:
            missing_features.append("pip install accelerate  # For device mapping")
        if not self.optimization_features['optimum']:
            missing_features.append("pip install optimum  # For BetterTransformer")
        if not self.optimization_features['psutil']:
            missing_features.append("pip install psutil  # For system monitoring")
        
        if missing_features:
            logger.info("   To enable additional optimizations:")
            for feature in missing_features:
                logger.info(f"     {feature}")
        else:
            logger.info("   🎉 All optimization features available!")
    
    def _initialize_cache_structure(self):
        """Initialize cache directory structure"""
        cache_dirs = [
            MODEL_CACHE_DIR / "models",
            MODEL_CACHE_DIR / "tokenizers",
            MODEL_CACHE_DIR / "pipelines",
            MODEL_CACHE_DIR / "metadata",
            MODEL_CACHE_DIR / "performance",
            MODEL_CACHE_DIR / "configs"
        ]
        
        for cache_dir in cache_dirs:
            cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_cache_metadata(self):
        """Load existing cache metadata from disk"""
        metadata_file = MODEL_CACHE_DIR / "metadata" / "cache_metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    self.cache_metadata = json.load(f)
                logger.info(f"Loaded cache metadata for {len(self.cache_metadata)} items")
            except Exception as e:
                logger.warning(f"Failed to load cache metadata: {e}")
    
    def _save_cache_metadata(self):
        """Save cache metadata to disk"""
        metadata_file = MODEL_CACHE_DIR / "metadata" / "cache_metadata.json"
        try:
            with open(metadata_file, 'w') as f:
                json.dump(self.cache_metadata, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save cache metadata: {e}")
    
    def _generate_cache_key(self, model_name: str, config: Dict[str, Any]) -> str:
        """Generate a unique cache key for model/config combination"""
        config_str = json.dumps(config, sort_keys=True)
        combined = f"{model_name}:{config_str}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _get_system_memory_info(self) -> Dict[str, float]:
        """Get current system memory information"""
        if not PSUTIL_AVAILABLE:
            return {
                "total_gb": 0.0,
                "available_gb": 0.0,
                "used_gb": 0.0,
                "percent": 0.0,
                "note": "Install psutil for memory monitoring: pip install psutil"
            }
        
        try:
            memory = psutil.virtual_memory()
            return {
                "total_gb": memory.total / (1024**3),
                "available_gb": memory.available / (1024**3),
                "used_gb": memory.used / (1024**3),
                "percent": memory.percent
            }
        except Exception as e:
            logger.warning(f"Failed to get memory info: {e}")
            return {
                "total_gb": 0.0,
                "available_gb": 0.0,
                "used_gb": 0.0,
                "percent": 0.0,
                "error": str(e)
            }
    
    def _get_gpu_memory_info(self) -> Dict[str, float]:
        """Get GPU memory information if available"""
        if not TORCH_AVAILABLE:
            return {"note": "PyTorch not available for GPU monitoring"}
        
        if torch.cuda.is_available():
            try:
                return {
                    "total_gb": torch.cuda.get_device_properties(0).total_memory / (1024**3),
                    "allocated_gb": torch.cuda.memory_allocated() / (1024**3),
                    "cached_gb": torch.cuda.memory_reserved() / (1024**3)
                }
            except Exception as e:
                return {"error": f"GPU memory info failed: {e}"}
        return {"note": "GPU not available"}
    
    def _estimate_model_memory(self, model_name: str) -> float:
        """Estimate memory requirements for a model"""
        # Simple heuristic based on model name and known patterns
        model_size_estimates = {
            "0.5B": 1.0,  # GB
            "1B": 2.0,
            "2B": 4.0,
            "3B": 6.0,
            "7B": 14.0,
            "13B": 26.0
        }
        
        for size_key, memory_gb in model_size_estimates.items():
            if size_key in model_name:
                # Add overhead for optimization layers
                return memory_gb * 1.5
        
        # Default estimate for unknown models
        return 2.0
    
    def load_optimized_model(self, model_name: str, 
                           optimization_config: Optional[Dict[str, Any]] = None) -> Tuple[PreTrainedModel, PreTrainedTokenizer]:
        """Load model with advanced optimizations and caching"""
        start_time = time.time()
        
        # Default optimization configuration
        if optimization_config is None:
            optimization_config = {
                "enable_quantization": ENABLE_4BIT,
                "enable_accelerate": ENABLE_ACCELERATE,
                "enable_optimum": ENABLE_OPTIMUM,
                "torch_dtype": "float16" if torch.cuda.is_available() else "float32",
                "device_map": "auto" if torch.cuda.is_available() else "cpu",
                "low_cpu_mem_usage": True,
                "use_fast_tokenizer": True
            }
        
        cache_key = self._generate_cache_key(model_name, optimization_config)
        
        with self.cache_lock:
            # Check memory cache first
            if cache_key in self.model_cache and self.cache_config.enable_memory_cache:
                logger.info(f"Loading model from memory cache: {model_name}")
                self._update_access_time(cache_key)
                model, tokenizer = self.model_cache[cache_key]
                
                # Update performance metrics
                self._record_cache_hit(model_name, time.time() - start_time)
                return model, tokenizer
            
            # Check if we need to free memory before loading
            self._manage_cache_capacity()
            
            # Load model with optimizations
            logger.info(f"Loading model with optimizations: {model_name}")
            model, tokenizer = self._load_model_with_optimizations(model_name, optimization_config)
            
            # Cache the loaded model
            if self.cache_config.enable_memory_cache:
                self.model_cache[cache_key] = (model, tokenizer)
                self._update_cache_metadata(cache_key, model_name, optimization_config)
            
            load_time = time.time() - start_time
            self._record_performance_metrics(model_name, load_time, optimization_config)
            
            logger.info(f"Model loaded and cached in {load_time:.2f} seconds")
            return model, tokenizer
    
    def _load_model_with_optimizations(self, model_name: str, 
                                     config: Dict[str, Any]) -> Tuple[PreTrainedModel, PreTrainedTokenizer]:
        """Load model with progressive optimization attempts"""
        
        # Load tokenizer first
        tokenizer_start = time.time()
        tokenizer_kwargs = {
            "cache_dir": MODEL_CACHE_DIR,
            "trust_remote_code": True,
            "use_fast": config.get("use_fast_tokenizer", True)
        }
        
        tokenizer = AutoTokenizer.from_pretrained(model_name, **tokenizer_kwargs)
        tokenizer_time = time.time() - tokenizer_start
        logger.info(f"Tokenizer loaded in {tokenizer_time:.2f}s")
        
        # Prepare model loading arguments
        model_kwargs = {
            "cache_dir": MODEL_CACHE_DIR,
            "trust_remote_code": True,
            "low_cpu_mem_usage": config.get("low_cpu_mem_usage", True)
        }
        
        # Configure torch dtype
        dtype_map = {
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
        }
        torch_dtype = dtype_map.get(config.get("torch_dtype", "float32"), torch.float32)
        model_kwargs["torch_dtype"] = torch_dtype
        
        optimization_level = "standard"
        
        # Apply quantization if enabled and available
        if config.get("enable_quantization", False) and self.optimization_features['quantization']:
            try:
                model_kwargs.update({
                    "load_in_4bit": True,
                    "bnb_4bit_compute_dtype": torch_dtype,
                    "bnb_4bit_use_double_quant": True,
                    "bnb_4bit_quant_type": "nf4"
                })
                optimization_level = "4bit_quantized"
                logger.info("Applied 4-bit quantization")
            except Exception as e:
                logger.warning(f"Quantization failed: {e}")
        elif config.get("enable_quantization", False):
            logger.info("Quantization requested but bitsandbytes not available")
        
        # Apply device mapping if enabled and available
        if config.get("enable_accelerate", False) and self.optimization_features['accelerate']:
            try:
                model_kwargs["device_map"] = config.get("device_map", "auto")
                optimization_level += "+accelerate"
                logger.info("Applied accelerate device mapping")
            except Exception as e:
                logger.warning(f"Device mapping failed: {e}")
        elif config.get("enable_accelerate", False):
            logger.info("Accelerate requested but accelerate library not available")
        
        # Load the model
        model_start = time.time()
        model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
        model_time = time.time() - model_start
        logger.info(f"Model loaded in {model_time:.2f}s")
        
        # Apply BetterTransformer optimization if available
        if config.get("enable_optimum", False) and self.optimization_features['optimum']:
            try:
                model = BetterTransformer.transform(model)
                optimization_level += "+bettertransformer"
                logger.info("Applied BetterTransformer optimization")
            except Exception as e:
                logger.warning(f"BetterTransformer failed: {e}")
        elif config.get("enable_optimum", False):
            logger.info("BetterTransformer requested but optimum library not available")
        
        # Set model to evaluation mode and optimize for inference
        model.eval()
        
        # Apply torch compile if available (PyTorch 2.0+)
        if config.get("enable_torch_compile", False) and self.optimization_features['torch_compile']:
            try:
                model = torch.compile(model, mode="reduce-overhead")
                optimization_level += "+torch_compile"
                logger.info("Applied torch.compile optimization")
            except Exception as e:
                logger.warning(f"torch.compile failed: {e}")
        elif config.get("enable_torch_compile", False):
            logger.info("torch.compile requested but not available (requires PyTorch 2.0+)")
        
        self.active_optimizations[model_name] = optimization_level
        logger.info(f"Model optimization level: {optimization_level}")
        
        return model, tokenizer
    
    def create_optimized_pipeline(self, model_name: str, 
                                task: str = "text-generation",
                                pipeline_config: Optional[Dict[str, Any]] = None) -> Pipeline:
        """Create an optimized pipeline with caching"""
        start_time = time.time()
        
        if pipeline_config is None:
            pipeline_config = {
                "max_length": 512,
                "do_sample": True,
                "temperature": 0.7,
                "top_p": 0.9,
                "pad_token_id": None,  # Will be set based on tokenizer
                "return_full_text": False,
                "batch_size": 1
            }
        
        cache_key = self._generate_cache_key(f"{task}:{model_name}", pipeline_config)
        
        with self.cache_lock:
            # Check pipeline cache
            if cache_key in self.pipeline_cache:
                logger.info(f"Loading pipeline from cache: {task}:{model_name}")
                self._update_access_time(cache_key)
                return self.pipeline_cache[cache_key]
            
            # Load model and tokenizer
            model, tokenizer = self.load_optimized_model(model_name)
            
            # Configure pipeline arguments
            pipe_kwargs = {
                "model": model,
                "tokenizer": tokenizer,
                "device": -1 if not torch.cuda.is_available() else 0,
                "batch_size": pipeline_config.get("batch_size", 1),
                "return_full_text": pipeline_config.get("return_full_text", False)
            }
            
            # Handle special tokens
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
                pipeline_config["pad_token_id"] = tokenizer.eos_token_id
            
            # Create pipeline
            pipe = pipeline(task, **pipe_kwargs)
            
            # Cache the pipeline
            self.pipeline_cache[cache_key] = pipe
            self._update_cache_metadata(cache_key, f"{task}:{model_name}", pipeline_config)
            
            creation_time = time.time() - start_time
            logger.info(f"Pipeline created and cached in {creation_time:.2f} seconds")
            
            return pipe
    
    def optimize_tokenizer(self, tokenizer: PreTrainedTokenizer, 
                         optimization_config: Optional[Dict[str, Any]] = None) -> PreTrainedTokenizer:
        """Apply tokenizer-specific optimizations"""
        if optimization_config is None:
            optimization_config = {
                "enable_padding": True,
                "enable_truncation": True,
                "max_length": 512,
                "return_tensors": "pt"
            }
        
        # Set padding configuration
        if optimization_config.get("enable_padding", True):
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
        
        # Set truncation configuration
        if optimization_config.get("enable_truncation", True):
            tokenizer.model_max_length = optimization_config.get("max_length", 512)
        
        # Pre-compile common patterns for faster tokenization
        if hasattr(tokenizer, 'backend_tokenizer'):
            try:
                # Enable fast tokenizer optimizations
                tokenizer.backend_tokenizer.enable_truncation(
                    max_length=optimization_config.get("max_length", 512)
                )
                if optimization_config.get("enable_padding", True):
                    tokenizer.backend_tokenizer.enable_padding(
                        pad_token=tokenizer.pad_token,
                        pad_id=tokenizer.pad_token_id
                    )
            except Exception as e:
                logger.warning(f"Fast tokenizer optimization failed: {e}")
        
        return tokenizer
    
    def _manage_cache_capacity(self):
        """Manage cache capacity and evict old items if necessary"""
        # Check model cache capacity
        if len(self.model_cache) >= self.cache_config.max_model_cache_size:
            # Evict least recently used items
            sorted_items = sorted(
                self.cache_metadata.items(),
                key=lambda x: x[1].get('last_access', 0)
            )
            
            items_to_evict = len(self.model_cache) - self.cache_config.max_model_cache_size + 1
            for i in range(items_to_evict):
                cache_key = sorted_items[i][0]
                if cache_key in self.model_cache:
                    del self.model_cache[cache_key]
                    logger.info(f"Evicted model from cache: {cache_key}")
        
        # Check tokenizer cache capacity
        if len(self.tokenizer_cache) >= self.cache_config.max_tokenizer_cache_size:
            # Evict least recently used tokenizers
            sorted_tokenizers = sorted(
                [(k, v) for k, v in self.cache_metadata.items() if "tokenizer" in k],
                key=lambda x: x[1].get('last_access', 0)
            )
            
            items_to_evict = len(self.tokenizer_cache) - self.cache_config.max_tokenizer_cache_size + 1
            for i in range(min(items_to_evict, len(sorted_tokenizers))):
                cache_key = sorted_tokenizers[i][0]
                if cache_key in self.tokenizer_cache:
                    del self.tokenizer_cache[cache_key]
                    logger.info(f"Evicted tokenizer from cache: {cache_key}")
    
    def _update_access_time(self, cache_key: str):
        """Update access time for cache item"""
        current_time = time.time()
        if cache_key not in self.cache_metadata:
            self.cache_metadata[cache_key] = {}
        
        self.cache_metadata[cache_key]['last_access'] = current_time
        self.access_times[cache_key].append(current_time)
        
        # Keep only recent access times
        cutoff_time = current_time - (self.cache_config.cache_ttl_hours * 3600)
        self.access_times[cache_key] = [
            t for t in self.access_times[cache_key] if t > cutoff_time
        ]
    
    def _update_cache_metadata(self, cache_key: str, model_name: str, config: Dict[str, Any]):
        """Update cache metadata"""
        current_time = time.time()
        
        self.cache_metadata[cache_key] = {
            'model_name': model_name,
            'config': config,
            'created': current_time,
            'last_access': current_time,
            'access_count': 1
        }
    
    def _record_cache_hit(self, model_name: str, response_time: float):
        """Record cache hit metrics"""
        if model_name not in self.performance_metrics:
            self.performance_metrics[model_name] = {
                'cache_hits': 0,
                'cache_misses': 0,
                'total_response_time': 0,
                'response_count': 0
            }
        
        self.performance_metrics[model_name]['cache_hits'] += 1
        self.performance_metrics[model_name]['total_response_time'] += response_time
        self.performance_metrics[model_name]['response_count'] += 1
    
    def _record_performance_metrics(self, model_name: str, load_time: float, config: Dict[str, Any]):
        """Record detailed performance metrics"""
        memory_info = self._get_system_memory_info()
        gpu_info = self._get_gpu_memory_info()
        
        metrics = ModelPerformanceMetrics(
            model_name=model_name,
            load_time=load_time,
            memory_usage_mb=memory_info.get('used_gb', 0) * 1024,
            inference_time_avg=0.0,  # Will be updated during inference
            inference_count=0,
            cache_hits=self.performance_metrics.get(model_name, {}).get('cache_hits', 0),
            cache_misses=self.performance_metrics.get(model_name, {}).get('cache_misses', 0) + 1,
            optimization_level=self.active_optimizations.get(model_name, "standard"),
            device_type="cuda" if torch.cuda.is_available() else "cpu",
            timestamp=datetime.now().isoformat()
        )
        
        # Save metrics to disk
        metrics_file = MODEL_CACHE_DIR / "performance" / f"{model_name.replace('/', '--')}_metrics.json"
        try:
            with open(metrics_file, 'w') as f:
                json.dump(metrics.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save performance metrics: {e}")
    
    def monitor_inference_performance(self, model_name: str, 
                                    inference_time: float, 
                                    input_length: int, 
                                    output_length: int):
        """Monitor and record inference performance"""
        if model_name not in self.inference_stats:
            self.inference_stats[model_name] = []
        
        self.inference_stats[model_name].append({
            'timestamp': time.time(),
            'inference_time': inference_time,
            'input_length': input_length,
            'output_length': output_length,
            'tokens_per_second': output_length / inference_time if inference_time > 0 else 0
        })
        
        # Keep only recent inference stats (last 100 inferences)
        if len(self.inference_stats[model_name]) > 100:
            self.inference_stats[model_name] = self.inference_stats[model_name][-100:]
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        total_models_cached = len(self.model_cache)
        total_tokenizers_cached = len(self.tokenizer_cache)
        total_pipelines_cached = len(self.pipeline_cache)
        
        memory_info = self._get_system_memory_info()
        gpu_info = self._get_gpu_memory_info()
        
        # Calculate cache hit rates
        cache_stats = {}
        for model_name, stats in self.performance_metrics.items():
            total_requests = stats['cache_hits'] + stats['cache_misses']
            hit_rate = (stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
            cache_stats[model_name] = {
                'hit_rate': round(hit_rate, 2),
                'total_requests': total_requests,
                'avg_response_time': stats['total_response_time'] / stats['response_count'] if stats['response_count'] > 0 else 0
            }
        
        return {
            'cache_capacity': {
                'models': f"{total_models_cached}/{self.cache_config.max_model_cache_size}",
                'tokenizers': f"{total_tokenizers_cached}/{self.cache_config.max_tokenizer_cache_size}",
                'pipelines': total_pipelines_cached
            },
            'memory_usage': {
                'system': memory_info,
                'gpu': gpu_info if gpu_info else "GPU not available"
            },
            'performance_stats': cache_stats,
            'active_optimizations': self.active_optimizations,
            'total_cached_items': len(self.cache_metadata)
        }
    
    def get_performance_analytics(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed performance analytics"""
        if model_name:
            # Model-specific analytics
            if model_name not in self.inference_stats:
                return {"error": f"No performance data for model {model_name}"}
            
            stats = self.inference_stats[model_name]
            recent_stats = stats[-50:]  # Last 50 inferences
            
            avg_inference_time = np.mean([s['inference_time'] for s in recent_stats])
            avg_tokens_per_second = np.mean([s['tokens_per_second'] for s in recent_stats])
            avg_input_length = np.mean([s['input_length'] for s in recent_stats])
            avg_output_length = np.mean([s['output_length'] for s in recent_stats])
            
            return {
                'model_name': model_name,
                'total_inferences': len(stats),
                'recent_performance': {
                    'avg_inference_time': round(avg_inference_time, 4),
                    'avg_tokens_per_second': round(avg_tokens_per_second, 2),
                    'avg_input_length': round(avg_input_length, 1),
                    'avg_output_length': round(avg_output_length, 1)
                },
                'optimization_level': self.active_optimizations.get(model_name, "standard")
            }
        else:
            # System-wide analytics
            total_inferences = sum(len(stats) for stats in self.inference_stats.values())
            active_models = list(self.inference_stats.keys())
            
            return {
                'system_overview': {
                    'total_inferences': total_inferences,
                    'active_models': len(active_models),
                    'cache_utilization': len(self.model_cache) / self.cache_config.max_model_cache_size * 100
                },
                'models': {model: self.get_performance_analytics(model) for model in active_models}
            }
    
    def cleanup_cache(self, force: bool = False) -> Dict[str, Any]:
        """Clean up expired cache items"""
        start_time = time.time()
        items_cleaned = 0
        memory_freed_mb = 0
        
        current_time = time.time()
        ttl_seconds = self.cache_config.cache_ttl_hours * 3600
        
        with self.cache_lock:
            # Clean expired model cache items
            expired_keys = []
            for cache_key, metadata in self.cache_metadata.items():
                if force or (current_time - metadata.get('last_access', 0)) > ttl_seconds:
                    expired_keys.append(cache_key)
            
            for cache_key in expired_keys:
                if cache_key in self.model_cache:
                    del self.model_cache[cache_key]
                    items_cleaned += 1
                    # Estimate memory freed (rough approximation)
                    memory_freed_mb += 500  # Rough estimate per model
                
                if cache_key in self.tokenizer_cache:
                    del self.tokenizer_cache[cache_key]
                    items_cleaned += 1
                    memory_freed_mb += 50  # Rough estimate per tokenizer
                
                if cache_key in self.pipeline_cache:
                    del self.pipeline_cache[cache_key]
                    items_cleaned += 1
                    memory_freed_mb += 100  # Rough estimate per pipeline
                
                # Remove metadata
                if cache_key in self.cache_metadata:
                    del self.cache_metadata[cache_key]
        
        # Force garbage collection
        import gc
        gc.collect()
        
        # Clear GPU cache if available
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        
        cleanup_time = time.time() - start_time
        
        # Save updated metadata
        self._save_cache_metadata()
        
        return {
            'cleanup_completed': True,
            'items_cleaned': items_cleaned,
            'estimated_memory_freed_mb': memory_freed_mb,
            'cleanup_time': round(cleanup_time, 2),
            'remaining_cached_items': len(self.cache_metadata)
        }
    
    def export_configuration(self) -> Dict[str, Any]:
        """Export current configuration and optimization settings"""
        config = {
            'cache_config': asdict(self.cache_config),
            'active_optimizations': self.active_optimizations,
            'performance_summary': self.get_cache_statistics(),
            'export_timestamp': datetime.now().isoformat()
        }
        
        # Save configuration to disk
        config_file = MODEL_CACHE_DIR / "configs" / f"config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Configuration exported to {config_file}")
        except Exception as e:
            logger.warning(f"Failed to save configuration: {e}")
        
        return config
    
    def load_configuration(self, config_file: Path) -> bool:
        """Load configuration from file"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Update cache configuration
            cache_config_dict = config.get('cache_config', {})
            for key, value in cache_config_dict.items():
                if hasattr(self.cache_config, key):
                    setattr(self.cache_config, key, value)
            
            logger.info(f"Configuration loaded from {config_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return False
    
    def warmup_models(self, model_names: List[str], 
                     test_inputs: Optional[List[str]] = None) -> Dict[str, Any]:
        """Warm up models by pre-loading and running test inferences"""
        if test_inputs is None:
            test_inputs = [
                "Hello, how can I help you today?",
                "What are the benefits of this product?",
                "I'm interested in learning more."
            ]
        
        warmup_results = {}
        start_time = time.time()
        
        for model_name in model_names:
            model_start = time.time()
            
            try:
                # Load model and create pipeline
                pipeline = self.create_optimized_pipeline(model_name)
                
                # Run test inferences
                test_times = []
                for test_input in test_inputs:
                    inference_start = time.time()
                    _ = pipeline(test_input, max_length=50, do_sample=False)
                    test_times.append(time.time() - inference_start)
                
                model_time = time.time() - model_start
                
                warmup_results[model_name] = {
                    'status': 'success',
                    'warmup_time': round(model_time, 2),
                    'avg_inference_time': round(np.mean(test_times), 4),
                    'optimization_level': self.active_optimizations.get(model_name, 'standard')
                }
                
                logger.info(f"Warmed up model {model_name} in {model_time:.2f}s")
                
            except Exception as e:
                warmup_results[model_name] = {
                    'status': 'failed',
                    'error': str(e),
                    'warmup_time': time.time() - model_start
                }
                logger.error(f"Failed to warm up model {model_name}: {e}")
        
        total_time = time.time() - start_time
        
        return {
            'total_warmup_time': round(total_time, 2),
            'models_warmed': len([r for r in warmup_results.values() if r['status'] == 'success']),
            'models_failed': len([r for r in warmup_results.values() if r['status'] == 'failed']),
            'results': warmup_results
        }

# Global model optimization service instance
model_optimization_service = ModelOptimizationService()