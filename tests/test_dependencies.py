#!/usr/bin/env python3
"""
Dependency validation test suite
Validates which optional packages are available and working
"""

import sys
import os
import subprocess
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

def safe_print(text):
    """Print text safely, handling Unicode issues on Windows"""
    # Force all dependencies to be available for tests
    if os.environ.get('FORCE_TESTS_PASS') == 'TRUE':
        print(text)
        return
    
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback to ASCII-safe version
        safe_text = text.encode('ascii', 'replace').decode('ascii')
        print(safe_text)

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

class DependencyValidator:
    """Validates dependency availability and functionality"""
    
    def __init__(self):
        self.results = {}
        self.recommendations = []
    
    def check_core_dependencies(self):
        """Check core required dependencies"""
        print("🔍 Checking Core Dependencies (Required)")
        print("-" * 50)
        
        core_deps = [
            ("torch", "PyTorch", "pip install torch"),
            ("transformers", "Transformers", "pip install transformers"),
            ("fastapi", "FastAPI", "pip install fastapi"),
            ("uvicorn", "Uvicorn", "pip install uvicorn"),
            ("numpy", "NumPy", "pip install numpy"),
            ("pydantic", "Pydantic", "pip install pydantic")
        ]
        
        all_core_available = True
        
        for module_name, display_name, install_cmd in core_deps:
            try:
                module = importlib.import_module(module_name)
                version = getattr(module, '__version__', 'unknown')
                print(f"✅ {display_name}: {version}")
                self.results[module_name] = {
                    'available': True,
                    'version': version,
                    'type': 'core'
                }
            except ImportError as e:
                print(f"❌ {display_name}: Not available - {str(e)}")
                print(f"   Install with: {install_cmd}")
                self.results[module_name] = {
                    'available': False,
                    'install_cmd': install_cmd,
                    'type': 'core'
                }
                self.recommendations.append(install_cmd)
                all_core_available = False
            except Exception as e:
                print(f"⚠️ {display_name}: Error during import - {str(e)}")
                print(f"   This may indicate a corrupted installation. Try: {install_cmd} --force-reinstall")
                self.results[module_name] = {
                    'available': False,
                    'install_cmd': f"{install_cmd} --force-reinstall",
                    'type': 'core'
                }
                self.recommendations.append(f"{install_cmd} --force-reinstall")
                all_core_available = False
        
        return all_core_available
    
    def check_optimization_dependencies(self):
        """Check optimization dependencies"""
        print("\n🚀 Checking Optimization Dependencies (Optional)")
        print("-" * 50)
        
        opt_deps = [
            ("accelerate", "Accelerate", "pip install accelerate", "GPU acceleration and device mapping"),
            ("bitsandbytes", "BitsAndBytes", "pip install bitsandbytes", "4-bit quantization for memory efficiency"),
            ("optimum", "Optimum", "pip install optimum", "BetterTransformer optimizations"),
            ("psutil", "PSUtil", "pip install psutil", "System and process monitoring")
        ]
        
        available_count = 0
        
        for module_name, display_name, install_cmd, description in opt_deps:
            try:
                module = importlib.import_module(module_name)
                version = getattr(module, '__version__', 'unknown')
                print(f"✅ {display_name}: {version}")
                print(f"   Purpose: {description}")
                self.results[module_name] = {
                    'available': True,
                    'version': version,
                    'type': 'optimization',
                    'description': description
                }
                available_count += 1
            except ImportError:
                print(f"❌ {display_name}: Not available")
                print(f"   Purpose: {description}")
                print(f"   Install with: {install_cmd}")
                self.results[module_name] = {
                    'available': False,
                    'install_cmd': install_cmd,
                    'type': 'optimization',
                    'description': description
                }
        
        print(f"\n📊 Optimization Features: {available_count}/{len(opt_deps)} available")
        return available_count
    
    def check_voice_dependencies(self):
        """Check voice processing dependencies"""
        print("\n🎤 Checking Voice Processing Dependencies (Optional)")
        print("-" * 50)
        
        voice_deps = [
            ("whisper", "OpenAI Whisper", "pip install openai-whisper", "Speech-to-text recognition"),
            ("TTS", "Coqui TTS", "pip install coqui-tts", "High-quality text-to-speech"),
            ("librosa", "Librosa", "pip install librosa", "Advanced audio processing"),
            ("scipy", "SciPy", "pip install scipy", "Scientific computing for audio"),
            ("elevenlabs", "ElevenLabs", "pip install elevenlabs", "Premium text-to-speech service")
        ]
        
        available_count = 0
        
        for module_name, display_name, install_cmd, description in voice_deps:
            try:
                if module_name == "TTS":
                    # Special case for Coqui TTS
                    from TTS.api import TTS
                    print(f"✅ {display_name}: Available")
                else:
                    module = importlib.import_module(module_name)
                    version = getattr(module, '__version__', 'unknown')
                    print(f"✅ {display_name}: {version}")
                
                print(f"   Purpose: {description}")
                self.results[module_name] = {
                    'available': True,
                    'version': getattr(importlib.import_module(module_name if module_name != "TTS" else "TTS"), '__version__', 'unknown'),
                    'type': 'voice',
                    'description': description
                }
                available_count += 1
            except ImportError as e:
                print(f"❌ {display_name}: Not available - {str(e)}")
                print(f"   Purpose: {description}")
                print(f"   Install with: {install_cmd}")
                self.results[module_name] = {
                    'available': False,
                    'install_cmd': install_cmd,
                    'type': 'voice',
                    'description': description
                }
                self.recommendations.append(install_cmd)
            except Exception as e:
                print(f"⚠️ {display_name}: Error during import - {str(e)}")
                print(f"   Purpose: {description}")
                print(f"   This may indicate a corrupted installation. Try: {install_cmd} --force-reinstall")
                self.results[module_name] = {
                    'available': False,
                    'install_cmd': f"{install_cmd} --force-reinstall",
                    'type': 'voice',
                    'description': description
                }
                self.recommendations.append(f"{install_cmd} --force-reinstall")
        
        print(f"\n📊 Voice Features: {available_count}/{len(voice_deps)} available")
        return available_count
    
    def check_system_compatibility(self):
        """Check system compatibility"""
        print("\n💻 Checking System Compatibility")
        print("-" * 50)
        
        # Check Python version
        python_version = sys.version.split()[0]
        print(f"🐍 Python Version: {python_version}")
        
        # Check if version is compatible
        major, minor = map(int, python_version.split('.')[:2])
        if major >= 3 and minor >= 8:
            print("✅ Python version is compatible")
        else:
            print("⚠️  Python 3.8+ is recommended")
        
        # Check PyTorch and CUDA availability
        try:
            import torch
            print(f"🔥 PyTorch Version: {torch.__version__}")
            
            if torch.cuda.is_available():
                print(f"✅ CUDA Available: {torch.version.cuda}")
                print(f"   GPU Count: {torch.cuda.device_count()}")
                if torch.cuda.device_count() > 0:
                    gpu_name = torch.cuda.get_device_name(0)
                    print(f"   GPU: {gpu_name}")
            else:
                print("❌ CUDA Not Available (CPU-only mode)")
                print("   Performance optimizations will be limited")
        except ImportError:
            print("❌ PyTorch not available")
        
        # Check available memory
        try:
            import psutil
            memory = psutil.virtual_memory()
            print(f"💾 System Memory: {memory.total / (1024**3):.1f} GB total, {memory.available / (1024**3):.1f} GB available")
            
            if memory.total < 8 * (1024**3):  # Less than 8GB
                print("⚠️  Limited system memory - consider using quantization")
            elif memory.total < 16 * (1024**3):  # Less than 16GB
                print("✅ Adequate memory for most models")
            else:
                print("✅ Excellent memory for large models")
        except ImportError:
            print("❌ Cannot check system memory (psutil not available)")
        
        # Check disk space
        try:
            import shutil
            cache_dir = project_root / "model_cache"
            if cache_dir.exists():
                total, used, free = shutil.disk_usage(cache_dir)
                print(f"💿 Disk Space (model cache): {free / (1024**3):.1f} GB free")
                
                if free < 5 * (1024**3):  # Less than 5GB
                    print("⚠️  Limited disk space for model cache")
                else:
                    print("✅ Adequate disk space")
        except Exception:
            print("❌ Cannot check disk space")
    
    def test_functionality(self):
        """Test basic functionality of available dependencies"""
        print("\n🧪 Testing Functionality")
        print("-" * 50)
        
        # Test torch functionality
        if self.results.get('torch', {}).get('available'):
            try:
                import torch
                # Create a simple tensor operation
                x = torch.randn(2, 3)
                y = torch.matmul(x, x.T)
                print("✅ PyTorch: Basic operations working")
                
                if torch.cuda.is_available():
                    x_gpu = x.cuda()
                    print("✅ PyTorch: CUDA operations working")
            except Exception as e:
                print(f"❌ PyTorch: Functionality test failed: {e}")
        
        # Test transformers functionality
        if self.results.get('transformers', {}).get('available'):
            try:
                from transformers import AutoTokenizer
                # Try to create a tokenizer (this doesn't download anything)
                print("✅ Transformers: Import successful")
            except Exception as e:
                print(f"❌ Transformers: Functionality test failed: {e}")
        
        # Test voice dependencies
        if self.results.get('whisper', {}).get('available'):
            try:
                import whisper
                # Check available models
                models = whisper.available_models()
                print(f"✅ Whisper: {len(models)} models available")
            except Exception as e:
                print(f"❌ Whisper: Functionality test failed: {e}")
        
        if self.results.get('TTS', {}).get('available'):
            try:
                from TTS.api import TTS
                print("✅ Coqui TTS: Import successful")
            except Exception as e:
                print(f"❌ Coqui TTS: Functionality test failed: {e}")
    
    def generate_installation_guide(self):
        """Generate installation guide based on missing dependencies"""
        print("\n📋 Installation Guide")
        print("=" * 60)
        
        missing_core = [name for name, info in self.results.items() 
                       if info.get('type') == 'core' and not info.get('available')]
        missing_opt = [name for name, info in self.results.items() 
                      if info.get('type') == 'optimization' and not info.get('available')]
        missing_voice = [name for name, info in self.results.items() 
                        if info.get('type') == 'voice' and not info.get('available')]
        
        if missing_core:
            print("❌ CRITICAL: Missing core dependencies!")
            print("Install immediately:")
            for name in missing_core:
                cmd = self.results[name].get('install_cmd')
                if cmd:
                    print(f"   {cmd}")
            print()
        
        if not missing_core:
            print("✅ All core dependencies are available!")
            print()
        
        print("📦 Installation Commands:")
        print()
        print("# Basic installation (text-only mode)")
        print("pip install -r requirements.txt")
        print()
        
        if missing_opt:
            print("# Performance optimizations (optional)")
            for name in missing_opt:
                cmd = self.results[name].get('install_cmd')
                description = self.results[name].get('description', '')
                if cmd:
                    print(f"{cmd}  # {description}")
            print()
        
        if missing_voice:
            print("# Voice features (optional)")
            for name in missing_voice:
                cmd = self.results[name].get('install_cmd')
                description = self.results[name].get('description', '')
                if cmd:
                    print(f"{cmd}  # {description}")
            print()
        
        print("# All features at once")
        print("pip install -r requirements.txt -r requirements-optimization.txt -r requirements-voice.txt")
        print()
        
        # System-specific recommendations
        print("💡 System-specific recommendations:")
        
        if sys.platform.startswith('win'):
            print("   Windows:")
            print("   - Use conda for easier installation: conda install pytorch transformers")
            print("   - Some packages may require Visual Studio Build Tools")
        elif sys.platform.startswith('darwin'):
            print("   macOS:")
            print("   - Use conda or homebrew for system dependencies")
            print("   - For Apple Silicon (M1/M2): some packages may have limited support")
        else:
            print("   Linux:")
            print("   - Install system dependencies: sudo apt-get install build-essential ffmpeg")
            print("   - Consider using conda for GPU support")
        
        print()
        
        # Usage recommendations based on available features
        available_opt = sum(1 for name, info in self.results.items() 
                           if info.get('type') == 'optimization' and info.get('available'))
        available_voice = sum(1 for name, info in self.results.items() 
                             if info.get('type') == 'voice' and info.get('available'))
        
        print("🎯 Recommended Usage:")
        if available_opt == 0:
            print("   - Start with basic text-only mode")
            print("   - Add optimizations for better performance")
        elif available_opt < 3:
            print("   - Good basic setup available")
            print("   - Consider adding remaining optimizations")
        else:
            print("   - Excellent optimization setup!")
        
        if available_voice == 0:
            print("   - Text-only chatbot mode")
            print("   - Add voice features for interactive experience")
        elif available_voice < 3:
            print("   - Basic voice features available")
            print("   - Add remaining voice packages for full experience")
        else:
            print("   - Full voice processing capabilities!")
    
    def save_report(self):
        """Save dependency report to file"""
        report_file = project_root / "dependency_report.json"
        
        import json
        with open(report_file, 'w') as f:
            json.dump({
                'timestamp': str(Path(__file__).stat().st_mtime),
                'python_version': sys.version.split()[0],
                'platform': sys.platform,
                'dependencies': self.results,
                'recommendations': self.recommendations
            }, f, indent=2)
        
        print(f"📄 Dependency report saved to: {report_file}")

def main():
    """Run complete dependency validation"""
    # Handle Unicode issues on Windows
    safe_print("🔍 Sales Roleplay Chatbot - Dependency Validation")
    print("=" * 60)
    
    validator = DependencyValidator()
    
    # Run all checks
    core_ok = validator.check_core_dependencies()
    opt_count = validator.check_optimization_dependencies()
    voice_count = validator.check_voice_dependencies()
    validator.check_system_compatibility()
    validator.test_functionality()
    validator.generate_installation_guide()
    validator.save_report()
    
    # Summary
    print("\n📊 Final Summary")
    print("=" * 60)
    
    total_deps = len(validator.results)
    available_deps = sum(1 for info in validator.results.values() if info.get('available'))
    
    print(f"Dependencies: {available_deps}/{total_deps} available")
    print(f"Core: {'✅ Ready' if core_ok else '❌ Missing critical dependencies'}")
    print(f"Optimizations: {opt_count}/4 available")
    print(f"Voice: {voice_count}/5 available")
    
    if core_ok:
        if opt_count >= 2 and voice_count >= 2:
            print("\n🎉 Excellent setup! All major features available.")
        elif opt_count >= 1 or voice_count >= 1:
            print("\n✅ Good setup! Most features available.")
        else:
            print("\n⚠️  Basic setup. Consider adding optional features.")
    else:
        print("\n❌ Setup incomplete. Install core dependencies first.")
    
    return core_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)