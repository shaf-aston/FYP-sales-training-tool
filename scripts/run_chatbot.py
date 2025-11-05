import subprocess
import sys
import os
import time
import logging
import platform
from pathlib import Path
import signal
import psutil

# Add utils to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "utils"))

from paths import LOGS_DIR, MODEL_CACHE_DIR, SRC_DIR, SCRIPTS_DIR
from env import setup_model_env, assert_model_present

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "chatbot_launcher.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("chatbot_launcher")

def check_python_version():
    """Check if Python version is at least 3.8"""
    logger.info(f"Python version: {platform.python_version()}")
    major, minor, _ = platform.python_version().split('.')
    if int(major) < 3 or (int(major) == 3 and int(minor) < 8):
        logger.error("Python 3.8 or higher is required.")
        sys.exit(1)
    logger.info("Python version check passed.")

def check_dependencies():
    """Check if all required packages are installed"""
    try:
        # Use timing for dependency checking
        start_time = time.time()
        
        # Core required packages
        required_packages = ["fastapi", "transformers", "uvicorn", "torch", "pydantic"]
        # Optional optimization packages
        optional_packages = ["accelerate", "bitsandbytes", "optimum"]
        
        missing_packages = []
        
        # Check required packages
        for package in required_packages:
            try:
                __import__(package)
                logger.info(f"Package {package} is installed.")
            except ImportError:
                logger.error(f"Package {package} is not installed.")
                missing_packages.append(package)
        
        # Check optional packages (warn but don't fail)
        for package in optional_packages:
            try:
                __import__(package)
                logger.info(f"Optional package {package} is installed.")
            except ImportError:
                logger.warning(f"Optional package {package} is not installed (optimizations may be disabled).")
        
        end_time = time.time()
        logger.info(f"Dependency check completed in {end_time - start_time:.2f} seconds.")
        
        if missing_packages:
            logger.error(f"Missing required packages: {', '.join(missing_packages)}")
            logger.info("Installing missing packages...")
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
            logger.info("Missing packages installed successfully.")
    except Exception as e:
        logger.error(f"Error checking dependencies: {e}")
        sys.exit(1)

def ensure_model():
    """Ensure model environment is configured and model is present locally.
    Will trigger download script if missing."""
    start_time = time.time()
    model_name = setup_model_env()
    try:
        assert_model_present(model_name)
        logger.info(f"Model '{model_name}' present locally.")
        logger.info(f"Model readiness check in {time.time() - start_time:.2f}s")
        return True
    except RuntimeError:
        logger.warning(
            f"Model '{model_name}' not found or incomplete. First-time download (or repair) starting..."
        )
        download_script = SCRIPTS_DIR / "download_model.py"
        if download_script.exists():
            try:
                subprocess.check_call([sys.executable, str(download_script)])
                # Re-validate
                assert_model_present(model_name)
                logger.info(f"Model '{model_name}' downloaded and validated.")
                logger.info(f"Model readiness (with download) in {time.time() - start_time:.2f}s")
                return True
            except Exception as e:
                logger.error(f"Automated download failed: {e}")
                return False
        else:
            logger.error(f"Download script missing at {download_script}")
            return False

def run_server():
    """Run the chatbot server with timing information"""
    try:
        # Use timing for server startup
        logger.info("Starting the fitness chatbot server...")
        server_start_time = time.time()
        
        # Set environment variables for offline model loading
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HOME"] = str(MODEL_CACHE_DIR)
        os.environ["TRANSFORMERS_CACHE"] = str(MODEL_CACHE_DIR)
        
        # Run the server
        chatbot_path = SRC_DIR / "main.py"
        logger.info(f"Running server from: {chatbot_path}")
        
        # Start the process
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-config", "None"],
            # [sys.executable, str(chatbot_path)],
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Process ID for potential later termination
        logger.info(f"Server started with PID: {process.pid}")
        
        # Monitor initial output to detect successful startup
        startup_timeout = 60  # seconds
        startup_start_time = time.time()
        while time.time() - startup_start_time < startup_timeout:
            # Check if process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                logger.error("Server failed to start")
                logger.error(f"STDOUT: {stdout}")
                logger.error(f"STDERR: {stderr}")
                return False
                
            # Read output line by line with timeout
            line = process.stdout.readline()
            if line:
                print(line, end="")  # Pass through to console
                
                if "Application startup complete" in line or "Uvicorn running on" in line:
                    server_ready_time = time.time()
                    startup_duration = server_ready_time - server_start_time
                    logger.info(f"Server started successfully in {startup_duration:.2f} seconds")
                    break
            
            # Small delay to prevent CPU hogging
            time.sleep(0.1)
        
        # Continue monitoring the process for errors or termination
        try:
            while process.poll() is None:
                line = process.stdout.readline()
                if line:
                    print(line, end="")  # Pass through to console
                
                err_line = process.stderr.readline()
                if err_line:
                    print(f"ERROR: {err_line}", file=sys.stderr, end="")
                    
                # Small delay to prevent CPU hogging
                time.sleep(0.1)
            
            # Process terminated
            return_code = process.poll()
            stdout, stderr = process.communicate()
            if return_code != 0:
                logger.error(f"Server terminated with code {return_code}")
                logger.error(f"STDOUT: {stdout}")
                logger.error(f"STDERR: {stderr}")
                return False
            else:
                logger.info("Server terminated normally")
                return True
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down server...")
            try:
                # Try graceful termination first
                if platform.system() == "Windows":
                    os.kill(process.pid, signal.CTRL_C_EVENT)
                else:
                    os.kill(process.pid, signal.SIGINT)
                    
                # Wait for termination
                timeout = 5  # seconds
                for _ in range(timeout * 10):
                    if process.poll() is not None:
                        break
                    time.sleep(0.1)
                    
                # Force kill if still running
                if process.poll() is None:
                    logger.info("Server did not shut down gracefully, forcing termination")
                    process.kill()
                    
                logger.info("Server shut down complete")
            except Exception as e:
                logger.error(f"Error shutting down server: {e}")
                
            return True
    
    except Exception as e:
        logger.error(f"Error running server: {e}")
        return False

def main():
    """Main function to run the chatbot"""
    start_time = time.time()
    
    # Check Python version
    check_python_version()
    
    # Check dependencies
    check_dependencies()
    
    # Ensure model is present (download if needed)
    if not ensure_model():
        logger.error("Model readiness failed. Exiting.")
        sys.exit(1)
        
    # Print startup time so far
    pre_server_time = time.time()
    logger.info(f"Pre-server initialization completed in {pre_server_time - start_time:.2f} seconds")
        
    # Run the server
    run_success = run_server()
    if not run_success:
        logger.error("Server failed to run correctly")
        sys.exit(1)
        
    # Calculate total runtime
    end_time = time.time()
    logger.info(f"Total runtime: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
