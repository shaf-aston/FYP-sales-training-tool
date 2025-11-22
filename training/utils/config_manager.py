"""
Enhanced configuration management with validation and environment variable support
Integrates with Hydra/OmegaConf for dynamic configuration management
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional
from omegaconf import OmegaConf, DictConfig
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ConfigValidationError(Exception):
    """Custom exception for configuration validation errors"""
    message: str
    config_key: str

class ConfigManager:
    """Enhanced configuration manager with validation and environment support"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = None
        self._env_prefix = "SALES_TRAINING_"
    
    def load_config(self, config_name: str = "roleplay_training_config") -> DictConfig:
        """Load configuration with environment variable overrides"""
        try:
            # Load base configuration
            if self.config_path:
                self.config = OmegaConf.load(self.config_path)
            else:
                config_dir = Path(__file__).parent.parent / "configs"
                config_file = config_dir / f"{config_name}.yaml"
                self.config = OmegaConf.load(config_file)
            
            # Apply environment variable overrides
            self._apply_env_overrides()
            
            # Validate configuration
            self._validate_config()
            
            logger.info("Configuration loaded and validated successfully")
            return self.config
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides to configuration"""
        env_mappings = {
            f"{self._env_prefix}MODEL_NAME": "model.name",
            f"{self._env_prefix}BATCH_SIZE": "training.batch_size",
            f"{self._env_prefix}LEARNING_RATE": "training.learning_rate",
            f"{self._env_prefix}NUM_EPOCHS": "training.num_epochs",
            f"{self._env_prefix}DATA_PATH": "data.processed_data_path",
            f"{self._env_prefix}OUTPUT_DIR": "output.model_save_path",
            f"{self._env_prefix}WANDB_ENABLED": "monitoring.wandb.enabled",
            f"{self._env_prefix}WANDB_PROJECT": "monitoring.wandb.project",
        }
        
        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Convert string values to appropriate types
                typed_value = self._convert_env_value(env_value, config_path)
                OmegaConf.set(self.config, config_path, typed_value)
                logger.info(f"Applied environment override: {config_path} = {typed_value}")
    
    def _convert_env_value(self, value: str, config_path: str) -> Any:
        """Convert environment variable string to appropriate type"""
        # Boolean conversions
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Numeric conversions based on config path
        if 'batch_size' in config_path or 'num_epochs' in config_path:
            return int(value)
        elif 'learning_rate' in config_path:
            return float(value)
        
        # Default to string
        return value
    
    def _validate_config(self):
        """Validate configuration for required fields and logical consistency"""
        required_fields = [
            ("model.name", str),
            ("training.batch_size", int),
            ("training.learning_rate", (int, float)),
            ("training.num_epochs", int),
            ("data.processed_data_path", str),
            ("output.model_save_path", str),
        ]
        
        for field_path, expected_type in required_fields:
            try:
                value = OmegaConf.select(self.config, field_path)
                if value is None:
                    raise ConfigValidationError(
                        f"Required field '{field_path}' is missing",
                        field_path
                    )
                
                if not isinstance(value, expected_type):
                    raise ConfigValidationError(
                        f"Field '{field_path}' must be of type {expected_type}, got {type(value)}",
                        field_path
                    )
            except Exception as e:
                raise ConfigValidationError(
                    f"Validation failed for '{field_path}': {e}",
                    field_path
                )
        
        # Logical validations
        self._validate_logical_constraints()
    
    def _validate_logical_constraints(self):
        """Validate logical constraints across configuration fields"""
        # Training parameter constraints
        if self.config.training.batch_size <= 0:
            raise ConfigValidationError(
                "Batch size must be positive",
                "training.batch_size"
            )
        
        if self.config.training.learning_rate <= 0 or self.config.training.learning_rate > 1:
            raise ConfigValidationError(
                "Learning rate must be between 0 and 1",
                "training.learning_rate"
            )
        
        if self.config.training.num_epochs <= 0:
            raise ConfigValidationError(
                "Number of epochs must be positive",
                "training.num_epochs"
            )
        
        # Path validations
        data_path = Path(self.config.data.processed_data_path)
        if not data_path.parent.exists():
            logger.warning(f"Data directory parent does not exist: {data_path.parent}")
        
        output_path = Path(self.config.output.model_save_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    
    def get_config(self) -> DictConfig:
        """Get the current configuration"""
        if self.config is None:
            self.load_config()
        return self.config
    
    def save_config(self, output_path: Optional[str] = None):
        """Save current configuration to file"""
        if output_path is None:
            output_path = "config_backup.yaml"
        
        with open(output_path, 'w') as f:
            OmegaConf.save(self.config, f)
        
        logger.info(f"Configuration saved to {output_path}")
    
    def merge_config(self, other_config: Dict[str, Any]):
        """Merge additional configuration"""
        other_omega = OmegaConf.create(other_config)
        self.config = OmegaConf.merge(self.config, other_omega)
        self._validate_config()
        logger.info("Configuration merged and re-validated")

def create_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    """Factory function to create a configuration manager"""
    return ConfigManager(config_path)

def load_training_config(config_name: str = "roleplay_training_config") -> DictConfig:
    """Convenience function to load training configuration"""
    manager = create_config_manager()
    return manager.load_config(config_name)

# Environment variable documentation
ENV_VAR_DOCS = {
    "SALES_TRAINING_MODEL_NAME": "Override the model name (e.g., 'microsoft/DialoGPT-medium')",
    "SALES_TRAINING_BATCH_SIZE": "Override training batch size (e.g., '8')",
    "SALES_TRAINING_LEARNING_RATE": "Override learning rate (e.g., '2e-5')",
    "SALES_TRAINING_NUM_EPOCHS": "Override number of training epochs (e.g., '3')",
    "SALES_TRAINING_DATA_PATH": "Override data directory path",
    "SALES_TRAINING_OUTPUT_DIR": "Override model output directory",
    "SALES_TRAINING_WANDB_ENABLED": "Enable/disable Wandb tracking ('true'/'false')",
    "SALES_TRAINING_WANDB_PROJECT": "Override Wandb project name",
}

if __name__ == "__main__":
    # Example usage
    print("Environment Variable Documentation:")
    for var, desc in ENV_VAR_DOCS.items():
        print(f"  {var}: {desc}")
    
    # Test configuration loading
    try:
        config = load_training_config()
        print(f"✅ Configuration loaded successfully")
        print(f"Model: {config.model.name}")
        print(f"Batch size: {config.training.batch_size}")
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")