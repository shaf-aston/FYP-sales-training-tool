"""
Model Configuration with Training Pipeline Support
Allows switching between base model and trained model while preserving training pipeline
"""
import os
from pathlib import Path

# Configuration flags
USE_TRAINED_MODEL = os.environ.get("USE_TRAINED_MODEL", "0") == "1"  # Set to "1" to use trained model
TRAINING_ENABLED = True  # Always keep training pipeline available

# Model paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
TRAINED_MODEL_PATH = PROJECT_ROOT / "training" / "models" / "sales_roleplay_model"  # Your trained model location

# Performance optimization settings with better context
GENERATION_CONFIG = {
    "base_model": {
        "max_new_tokens": 200,      # INCREASED: More detailed, contextual responses
        "do_sample": True,          # Enable sampling for variety
        "num_beams": 1,            # No beam search for speed
        "temperature": 0.85,       # Slightly more creative for natural responses
        "repetition_penalty": 1.15, # Stronger penalty to prevent repetition
        "pad_token_id": 151643,    # Qwen pad token
        "eos_token_id": 151645     # Qwen end token
    },
    "trained_model": {
        "max_new_tokens": 250,     # Even longer for trained model with full context
        "do_sample": True,         # Sampling for natural responses
        "num_beams": 1,
        "temperature": 0.9,        # More creative for engaging responses
        "repetition_penalty": 1.2, # Stronger anti-repetition
        "pad_token_id": 151643,
        "eos_token_id": 151645
    }
}

# Context memory settings
CONTEXT_CONFIG = {
    "max_history_turns": 15,       # Remember last 15 exchanges (increased)
    "context_window": 2048,        # Maximum context length
    "memory_retention": True,      # Keep consistent facts
    "persona_consistency": True,   # Maintain persona traits
    "creative_gaps": False,        # DON'T make up info - admit unknowns
    "user_prompt_weight": 0.9      # HIGH weight for user context relevance
}

def get_active_model_config():
    """Get the active model configuration"""
    if USE_TRAINED_MODEL and TRAINED_MODEL_PATH.exists():
        return {
            "model_path": str(TRAINED_MODEL_PATH),
            "model_type": "trained",
            "generation_config": GENERATION_CONFIG["trained_model"],
            "description": "Sales Roleplay Trained Model"
        }
    else:
        return {
            "model_path": BASE_MODEL,
            "model_type": "base",
            "generation_config": GENERATION_CONFIG["base_model"],
            "description": "Base Qwen Model (Optimized for Speed)"
        }

def get_training_config():
    """Get training pipeline configuration - ALWAYS AVAILABLE"""
    return {
        "enabled": TRAINING_ENABLED,
        "base_model": BASE_MODEL,
        "output_dir": str(PROJECT_ROOT / "training" / "models"),
        "training_data_dir": str(PROJECT_ROOT / "training" / "data"),
        "checkpoint_dir": str(PROJECT_ROOT / "training" / "checkpoints"),
        "logs_dir": str(PROJECT_ROOT / "training" / "logs"),
        "training_scripts": [
            str(PROJECT_ROOT / "training" / "core_pipeline" / "model_training.py"),
            str(PROJECT_ROOT / "training" / "core_pipeline" / "roleplay_training.py"),
            str(PROJECT_ROOT / "training" / "enhanced_training_coordinator.py")
        ]
    }

# Display current configuration
if __name__ == "__main__":
    print("=" * 60)
    print("MODEL CONFIGURATION")
    print("=" * 60)
    
    active_config = get_active_model_config()
    print(f"\n🤖 Active Model: {active_config['model_type'].upper()}")
    print(f"   Path: {active_config['model_path']}")
    print(f"   Description: {active_config['description']}")
    print(f"\n⚡ Generation Settings:")
    for key, value in active_config['generation_config'].items():
        print(f"   {key}: {value}")
    
    training_config = get_training_config()
    print(f"\n🎓 Training Pipeline: {'✅ ENABLED' if training_config['enabled'] else '❌ DISABLED'}")
    print(f"   Base Model: {training_config['base_model']}")
    print(f"   Output Directory: {training_config['output_dir']}")
    
    print(f"\n💡 To use trained model:")
    print(f"   export USE_TRAINED_MODEL=1")
    print(f"   (or set environment variable before starting server)")
    
    print("\n" + "=" * 60)
