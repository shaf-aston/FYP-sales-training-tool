"""
Adaptive Training Configuration System
Automatically adjusts hyperparameters based on dataset characteristics
Ensures optimal training regardless of data size changes
"""
import torch
from typing import Dict, Optional, Union, List
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import logging
import yaml

logger = logging.getLogger(__name__)


@dataclass
class AdaptiveTrainingConfig:
    """
    Training configuration that adapts to dataset size and characteristics.
    
    Provides intelligent defaults and automatic scaling for:
    - Batch size (based on dataset size and available memory)
    - Learning rate (scaled with batch size)
    - Number of epochs (more epochs for smaller datasets)
    - Gradient accumulation (for large effective batch sizes)
    - Warmup steps (proportional to total steps)
    - Evaluation frequency (more frequent for smaller datasets)
    """
    
    # Model configuration
    model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"
    model_type: str = "causal_lm"  # causal_lm, seq2seq, etc.
    
    # Data configuration
    max_length: Optional[int] = None  # Auto-computed from dataset if None
    train_test_split: float = 0.1  # Validation split ratio
    stratify_by: Optional[str] = "persona"  # Field for stratified splitting
    
    # Training hyperparameters (will be auto-adjusted)
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 4
    per_device_eval_batch_size: int = 4
    gradient_accumulation_steps: int = 8
    learning_rate: float = 2e-5
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1  # Warmup as % of total steps
    max_grad_norm: float = 1.0
    
    # Optimizer configuration
    optimizer_type: str = "adamw"  # adamw, adam, sgd
    adam_beta1: float = 0.9
    adam_beta2: float = 0.999
    adam_epsilon: float = 1e-8
    
    # Learning rate scheduling
    lr_scheduler_type: str = "linear"  # linear, cosine, constant, polynomial
    num_cycles: float = 0.5  # For cosine scheduler
    
    # Mixed precision and performance
    fp16: bool = False  # Auto-detect based on GPU availability
    bf16: bool = False  # Use bfloat16 if available
    use_cpu: bool = False  # Force CPU training
    dataloader_num_workers: int = 0  # Auto-set based on CPU count
    dataloader_pin_memory: bool = True
    
    # Logging and evaluation
    logging_steps: int = 10
    eval_steps: Optional[int] = None  # Auto-computed
    save_steps: Optional[int] = None  # Auto-computed
    save_total_limit: int = 3  # Keep only N best checkpoints
    load_best_model_at_end: bool = True
    metric_for_best_model: str = "eval_loss"
    greater_is_better: bool = False
    
    # Output configuration
    output_dir: str = "./training/models/fine-tuned"
    logging_dir: Optional[str] = None
    run_name: Optional[str] = None
    
    # Early stopping
    early_stopping_patience: Optional[int] = None  # Auto-set for small datasets
    early_stopping_threshold: float = 0.0
    
    # Data weighting (for multi-source datasets)
    data_source_weights: Optional[Dict[str, float]] = None
    persona_weights: Optional[Dict[str, float]] = None
    
    # Resume training
    resume_from_checkpoint: Optional[str] = None
    
    # Seed for reproducibility
    seed: int = 42
    
    # Advanced options
    remove_unused_columns: bool = False
    group_by_length: bool = False  # Group similar lengths for efficiency
    length_column_name: str = "length"
    report_to: List[str] = field(default_factory=lambda: ["tensorboard"])
    
    # Auto-configuration flags
    auto_configure: bool = True
    auto_find_batch_size: bool = False  # Automatically reduce batch size if OOM
    
    def __post_init__(self):
        """Post-initialization validation and setup"""
        # Auto-detect GPU capabilities
        if not self.use_cpu:
            if torch.cuda.is_available():
                # Check for bf16 support (Ampere and newer)
                if torch.cuda.get_device_capability()[0] >= 8:
                    self.bf16 = True
                    self.fp16 = False
                    logger.info("BFloat16 training enabled (Ampere+ GPU detected)")
                else:
                    self.fp16 = True
                    logger.info("FP16 training enabled")
            else:
                logger.warning("No GPU detected, using CPU (slower training)")
                self.use_cpu = True
        
        # Set dataloader workers based on CPU count
        if self.dataloader_num_workers == 0:
            import os
            self.dataloader_num_workers = min(4, os.cpu_count() or 1)
        
        # Create output directory
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # Set logging directory
        if self.logging_dir is None:
            self.logging_dir = str(Path(self.output_dir) / "logs")
    
    def adapt_to_dataset_size(self, total_samples: int, avg_sample_length: float = 256):
        """
        Automatically adjust hyperparameters based on dataset size.
        
        Args:
            total_samples: Total number of training samples
            avg_sample_length: Average token length of samples
        """
        if not self.auto_configure:
            logger.info("Auto-configuration disabled, using manual settings")
            return
        
        logger.info(f"Adapting configuration for {total_samples} samples...")
        
        # Adjust epochs based on dataset size
        if total_samples < 100:
            self.num_train_epochs = 10
            self.early_stopping_patience = 3
            logger.info("Small dataset detected: Using more epochs with early stopping")
        elif total_samples < 500:
            self.num_train_epochs = 5
            self.early_stopping_patience = 2
        elif total_samples < 2000:
            self.num_train_epochs = 3
        else:
            self.num_train_epochs = 2
            logger.info("Large dataset detected: Using fewer epochs")
        
        # Adjust batch size based on dataset size and GPU memory
        if total_samples < 100:
            self.per_device_train_batch_size = 2
            self.gradient_accumulation_steps = 4
        elif total_samples < 500:
            self.per_device_train_batch_size = 4
            self.gradient_accumulation_steps = 4
        elif total_samples < 2000:
            self.per_device_train_batch_size = 8
            self.gradient_accumulation_steps = 2
        else:
            self.per_device_train_batch_size = 16
            self.gradient_accumulation_steps = 1
        
        # Adjust batch size for long sequences
        if avg_sample_length > 512:
            self.per_device_train_batch_size = max(1, self.per_device_train_batch_size // 2)
            self.gradient_accumulation_steps *= 2
            logger.info("Long sequences detected: Reduced batch size, increased gradient accumulation")
        
        # Calculate effective batch size
        effective_batch_size = self.per_device_train_batch_size * self.gradient_accumulation_steps
        
        # Adjust learning rate based on effective batch size (linear scaling rule)
        base_lr = 2e-5
        base_batch_size = 32
        self.learning_rate = base_lr * (effective_batch_size / base_batch_size)
        logger.info(f"Adjusted learning rate to {self.learning_rate:.2e} for effective batch size {effective_batch_size}")
        
        # Compute total training steps
        steps_per_epoch = (total_samples + effective_batch_size - 1) // effective_batch_size
        total_steps = steps_per_epoch * self.num_train_epochs
        
        # Set warmup steps
        warmup_steps = int(total_steps * self.warmup_ratio)
        logger.info(f"Total training steps: {total_steps}, warmup steps: {warmup_steps}")
        
        # Set evaluation and save steps
        if self.eval_steps is None:
            # Evaluate 3-5 times per epoch for small datasets, less for large
            if total_samples < 500:
                self.eval_steps = max(10, steps_per_epoch // 5)
            else:
                self.eval_steps = max(50, steps_per_epoch // 3)
        
        if self.save_steps is None:
            # Save less frequently for large datasets
            if total_samples < 500:
                self.save_steps = self.eval_steps
            else:
                self.save_steps = self.eval_steps * 2
        
        logger.info(f"Configuration adapted:")
        logger.info(f"  Epochs: {self.num_train_epochs}")
        logger.info(f"  Batch size: {self.per_device_train_batch_size}")
        logger.info(f"  Gradient accumulation: {self.gradient_accumulation_steps}")
        logger.info(f"  Effective batch size: {effective_batch_size}")
        logger.info(f"  Learning rate: {self.learning_rate:.2e}")
        logger.info(f"  Eval steps: {self.eval_steps}")
        logger.info(f"  Save steps: {self.save_steps}")
    
    def adapt_to_available_memory(self, available_memory_gb: Optional[float] = None):
        """
        Adjust batch size based on available GPU/CPU memory.
        
        Args:
            available_memory_gb: Available memory in GB (auto-detected if None)
        """
        if available_memory_gb is None:
            if torch.cuda.is_available():
                available_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            else:
                # Assume reasonable CPU RAM
                import psutil
                available_memory_gb = psutil.virtual_memory().available / (1024**3)
        
        logger.info(f"Available memory: {available_memory_gb:.2f} GB")
        
        # Rough heuristic: 1GB per batch for 0.5B model
        # Adjust based on model size
        model_size_gb = 0.5  # Qwen 0.5B default
        memory_per_batch = model_size_gb * 2  # Model + activations
        
        max_batch_size = int(available_memory_gb / memory_per_batch)
        max_batch_size = max(1, max_batch_size)
        
        if self.per_device_train_batch_size > max_batch_size:
            old_batch_size = self.per_device_train_batch_size
            self.per_device_train_batch_size = max_batch_size
            # Compensate with gradient accumulation
            self.gradient_accumulation_steps = (old_batch_size + max_batch_size - 1) // max_batch_size
            logger.warning(f"Reduced batch size to {max_batch_size} due to memory constraints")
            logger.info(f"Increased gradient accumulation to {self.gradient_accumulation_steps}")
    
    def to_dict(self) -> Dict:
        """Convert configuration to dictionary"""
        return asdict(self)
    
    def save(self, path: Union[str, Path]):
        """Save configuration to file (YAML or JSON)"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        config_dict = self.to_dict()
        
        if path.suffix == '.yaml' or path.suffix == '.yml':
            with open(path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False)
        else:
            with open(path, 'w') as f:
                json.dump(config_dict, f, indent=2)
        
        logger.info(f"Configuration saved to {path}")
    
    @classmethod
    def from_dict(cls, config_dict: Dict) -> 'AdaptiveTrainingConfig':
        """Load configuration from dictionary"""
        return cls(**config_dict)
    
    @classmethod
    def load(cls, path: Union[str, Path]) -> 'AdaptiveTrainingConfig':
        """Load configuration from file (YAML or JSON)"""
        path = Path(path)
        
        if path.suffix == '.yaml' or path.suffix == '.yml':
            with open(path, 'r') as f:
                config_dict = yaml.safe_load(f)
        else:
            with open(path, 'r') as f:
                config_dict = json.load(f)
        
        return cls.from_dict(config_dict)
    
    def get_effective_batch_size(self) -> int:
        """Calculate effective batch size"""
        return self.per_device_train_batch_size * self.gradient_accumulation_steps
    
    def get_total_steps(self, total_samples: int) -> int:
        """Calculate total training steps"""
        effective_batch_size = self.get_effective_batch_size()
        steps_per_epoch = (total_samples + effective_batch_size - 1) // effective_batch_size
        return steps_per_epoch * self.num_train_epochs
    
    def get_warmup_steps(self, total_samples: int) -> int:
        """Calculate warmup steps"""
        total_steps = self.get_total_steps(total_samples)
        return int(total_steps * self.warmup_ratio)


def create_config_from_dataset_stats(stats: 'DatasetStats', **overrides) -> AdaptiveTrainingConfig:
    """
    Create an optimally configured training config from dataset statistics.
    
    Args:
        stats: Dataset statistics object
        **overrides: Manual overrides for specific parameters
    
    Returns:
        Configured AdaptiveTrainingConfig
    """
    config = AdaptiveTrainingConfig(**overrides)
    
    # Use recommended values from stats
    if config.max_length is None:
        config.max_length = stats.recommended_max_length
    
    # Adapt to dataset size
    config.adapt_to_dataset_size(
        total_samples=stats.total_samples,
        avg_sample_length=(stats.avg_input_length + stats.avg_output_length)
    )
    
    # Set persona weights if imbalanced
    if stats.persona_distribution:
        total_samples = sum(stats.persona_distribution.values())
        imbalance_ratio = max(stats.persona_distribution.values()) / min(stats.persona_distribution.values())
        
        if imbalance_ratio > 3:
            # Compute inverse frequency weights
            config.persona_weights = {
                persona: total_samples / (count * len(stats.persona_distribution))
                for persona, count in stats.persona_distribution.items()
            }
            logger.info(f"Persona imbalance detected (ratio: {imbalance_ratio:.1f}), applying weights")
    
    return config


# Preset configurations for common scenarios
PRESET_CONFIGS = {
    "quick_test": {
        "num_train_epochs": 1,
        "per_device_train_batch_size": 2,
        "gradient_accumulation_steps": 2,
        "eval_steps": 10,
        "save_steps": 10,
        "auto_configure": False
    },
    "small_dataset": {
        "num_train_epochs": 10,
        "per_device_train_batch_size": 2,
        "gradient_accumulation_steps": 4,
        "learning_rate": 3e-5,
        "warmup_ratio": 0.15,
        "early_stopping_patience": 3
    },
    "medium_dataset": {
        "num_train_epochs": 5,
        "per_device_train_batch_size": 8,
        "gradient_accumulation_steps": 2,
        "learning_rate": 2e-5,
        "warmup_ratio": 0.1
    },
    "large_dataset": {
        "num_train_epochs": 2,
        "per_device_train_batch_size": 16,
        "gradient_accumulation_steps": 1,
        "learning_rate": 1e-5,
        "warmup_ratio": 0.05
    },
    "production": {
        "num_train_epochs": 3,
        "save_total_limit": 5,
        "load_best_model_at_end": True,
        "metric_for_best_model": "eval_loss",
        "early_stopping_patience": 2,
        "report_to": ["tensorboard", "wandb"]
    }
}


def get_preset_config(preset_name: str, **overrides) -> AdaptiveTrainingConfig:
    """
    Get a preset configuration with optional overrides.
    
    Args:
        preset_name: Name of preset (quick_test, small_dataset, medium_dataset, large_dataset, production)
        **overrides: Parameters to override
    
    Returns:
        AdaptiveTrainingConfig with preset values
    """
    if preset_name not in PRESET_CONFIGS:
        raise ValueError(f"Unknown preset: {preset_name}. Available: {list(PRESET_CONFIGS.keys())}")
    
    preset = PRESET_CONFIGS[preset_name].copy()
    preset.update(overrides)
    
    return AdaptiveTrainingConfig(**preset)
