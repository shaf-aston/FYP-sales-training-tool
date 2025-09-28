import os
import sys
import logging
import argparse
import time
from pathlib import Path

# Add utils to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "utils"))

from paths import LOGS_DIR, MODEL_CACHE_DIR
from env import setup_model_env, assert_model_present

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "download_model.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("download_model")

def download_model(model_name: str = None, force_download: bool = False):
    """Download the specified model to the local cache."""
    try:
        # Import transformers here to check if it's available
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch
        
        # Centralized env + offline flags
        model_name = setup_model_env(model_name)
        logger.info(f"Starting download of model: {model_name}")
        logger.info(f"Cache directory: {MODEL_CACHE_DIR}")
        # (Environment + offline flags already set in setup_model_env)
        
        # Check if model already exists
        model_cache_path = MODEL_CACHE_DIR / model_name.replace("/", "--")
        if model_cache_path.exists() and not force_download:
            try:
                assert_model_present(model_name)
                logger.info(f"Model already present at {model_cache_path}")
                logger.info("Use --force to re-download")
                return True
            except RuntimeError:
                logger.warning("Model directory exists but appears incomplete; proceeding to re-download.")
        
        start_time = time.time()
        
        # Download tokenizer first
        logger.info("Downloading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            cache_dir=MODEL_CACHE_DIR,
            trust_remote_code=True
        )
        
        # Download model
        logger.info("Downloading model...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            cache_dir=MODEL_CACHE_DIR,
            trust_remote_code=True,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None
        )
        
        end_time = time.time()
        logger.info(f"Model downloaded successfully in {end_time - start_time:.2f} seconds")
        logger.info(f"Model cached at: {MODEL_CACHE_DIR}")
        
        # Test the model briefly
        logger.info("Testing model...")
        from transformers import pipeline
        # Offline flags already set; quick functional test
        pipe = pipeline("text-generation", model=model_name, trust_remote_code=True)
        test_output = pipe("Hello", max_length=10, num_return_sequences=1)
        logger.info("Model test successful!")
        
        return True
        
    except ImportError as e:
        logger.error(f"Required packages not installed: {e}")
        logger.error("Please install required packages with: pip install transformers torch")
        return False
    except Exception as e:
        logger.error(f"Error downloading model: {e}")
        return False

def main():
    """Main function to handle command line arguments and download model."""
    parser = argparse.ArgumentParser(description="Download model for offline use")
    parser.add_argument(
        "--model", 
        type=str, 
        default=None,
        help="Model name to download (default: Qwen/Qwen2.5-0.5B-Instruct)"
    )
    parser.add_argument(
        "--force", 
        action="store_true",
        help="Force re-download even if model exists"
    )
    
    args = parser.parse_args()
    
    logger.info("Starting model download process...")
    success = download_model(args.model, args.force)
    
    if success:
        logger.info("Model download completed successfully!")
        logger.info("You can now run the chatbot with: python scripts/run_chatbot.py")
    else:
        logger.error("Model download failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
