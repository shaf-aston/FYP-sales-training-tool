# Sales Roleplay Chatbot - Test Suite

This directory contains comprehensive tests for the Sales Roleplay Chatbot system. The test suite is designed to work with different dependency configurations and provides detailed feedback about system health.

## 🧪 Test Files Overview

### Core Test Files

- **`run_all_tests.py`** - Main test runner that orchestrates all test suites
- **`test_dependencies.py`** - Validates which optional packages are available and working
- **`test_voice_service.py`** - Tests voice processing functionality with and without optional dependencies
- **`test_model_optimization.py`** - Tests model optimization features and fallback behavior
- **`test_integration.py`** - Tests full system functionality with different dependency configurations

### Legacy Test Files

- **`test_imports.py`** - Validates import paths are working correctly
- **`test_modular.py`** - Tests modular architecture components
- **`test_enhanced_responses.py`** - Tests enhanced response generation
- **`test_ai_improvement.py`** - Tests improved AI response generation with live API

## 🚀 Quick Start

### Run All Tests
```bash
# Run complete test suite
python tests/run_all_tests.py

# Run tests without legacy files
python tests/run_all_tests.py --skip-existing

# Quick dependency check only
python tests/run_all_tests.py --quick
```

### Run Specific Test Suites
```bash
# Dependency validation only
python tests/run_all_tests.py --suite deps

# Voice service tests only
python tests/run_all_tests.py --suite voice

# Model optimization tests only
python tests/run_all_tests.py --suite optimization

# Integration tests only
python tests/run_all_tests.py --suite integration

# Legacy tests only
python tests/run_all_tests.py --suite existing
```

### Run Individual Test Files
```bash
# Dependency validation
python tests/test_dependencies.py

# Voice service tests
python tests/test_voice_service.py

# Model optimization tests
python tests/test_model_optimization.py

# Integration tests
python tests/test_integration.py
```

## 📋 Test Categories

### 1. Dependency Validation (`test_dependencies.py`)

**Purpose**: Validates which optional packages are available and provides installation guidance.

**Features**:
- ✅ Checks core dependencies (required)
- ✅ Checks optimization dependencies (optional)
- ✅ Checks voice processing dependencies (optional)
- ✅ Tests system compatibility
- ✅ Provides installation recommendations
- ✅ Generates dependency report

**Sample Output**:
```
🔍 Checking Core Dependencies (Required)
✅ PyTorch: 2.0.1
✅ Transformers: 4.30.2
❌ Coqui TTS: Not available
   Install with: pip install coqui-tts
```

### 2. Voice Service Tests (`test_voice_service.py`)

**Purpose**: Tests voice processing functionality with graceful degradation.

**Features**:
- ✅ Tests with and without Whisper (speech-to-text)
- ✅ Tests with and without Coqui TTS (text-to-speech)
- ✅ Tests fallback behavior
- ✅ Tests emotion synthesis
- ✅ Tests contextual voice generation
- ✅ Tests voice analysis features

**Sample Output**:
```
🧪 Running Voice Service Tests
✅ Dependency reporting working
   Whisper: True
   Coqui TTS: False
✅ Speech-to-text fallback working
✅ Text-to-speech fallback working
```

### 3. Model Optimization Tests (`test_model_optimization.py`)

**Purpose**: Tests model optimization features and performance monitoring.

**Features**:
- ✅ Tests with and without optimization libraries
- ✅ Tests caching functionality
- ✅ Tests memory management
- ✅ Tests performance monitoring
- ✅ Tests cleanup operations
- ✅ Tests different optimization configurations

**Sample Output**:
```
🧪 Running Model Optimization Service Tests
✅ Optimization features reporting:
   quantization: False
   accelerate: True
   optimum: False
✅ Cache management working
✅ Performance analytics working
```

### 4. Integration Tests (`test_integration.py`)

**Purpose**: Tests full system functionality and component interaction.

**Features**:
- ✅ Tests system integration
- ✅ Tests service compatibility
- ✅ Tests different dependency configurations
- ✅ Tests error handling and graceful degradation
- ✅ Tests data persistence
- ✅ Performs system health check

**Sample Output**:
```
🧪 Running Integration Tests
✅ Configuration loaded: Sales Training Chatbot v1.0
✅ Voice service integration working
✅ Cross-service compatibility working
🎯 Overall Health: 85% (4/5 components)
```

## 🔧 Dependency Configurations

The test suite is designed to work with different dependency configurations:

### Minimal Configuration (Required)
```bash
pip install -r requirements.txt
```
- Core chatbot functionality
- Text-only mode
- Basic performance

### Optimization Configuration (Optional)
```bash
pip install -r requirements.txt -r requirements-optimization.txt
```
- Enhanced performance
- GPU acceleration
- Memory efficiency

### Voice Configuration (Optional)
```bash
pip install -r requirements.txt -r requirements-voice.txt
```
- Speech-to-text
- Text-to-speech
- Audio processing

### Full Configuration (All Features)
```bash
pip install -r requirements.txt -r requirements-optimization.txt -r requirements-voice.txt
```
- All features enabled
- Maximum performance
- Complete functionality

## 📊 Understanding Test Results

### Success Indicators
- ✅ **Green checkmarks**: Features working correctly
- ⚠️ **Yellow warnings**: Features not available but system working
- ❌ **Red X marks**: Actual failures that need attention

### Test Output Interpretation

**Dependency Tests**:
- Shows which packages are available
- Provides installation commands for missing packages
- Explains impact of missing dependencies

**Service Tests**:
- Validates service initialization
- Tests fallback behavior
- Confirms graceful degradation

**Integration Tests**:
- Verifies component interaction
- Tests end-to-end functionality
- Provides system health assessment

## 🛠️ Troubleshooting

### Common Issues

**1. Import Errors**
```bash
# Add project root to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python tests/run_all_tests.py
```

**2. Missing Dependencies**
```bash
# Run dependency validation first
python tests/test_dependencies.py
# Follow installation recommendations
```

**3. Test Failures**
```bash
# Check specific test output
python tests/test_voice_service.py
# Review error messages and install missing packages
```

**4. Permission Issues**
```bash
# Ensure write access to logs and model_cache directories
mkdir -p logs model_cache
chmod 755 logs model_cache
```

### Platform-Specific Issues

**Windows**:
- Use conda for easier package management
- Some packages may require Visual Studio Build Tools

**macOS**:
- Use homebrew for system dependencies
- Apple Silicon may have limited package support

**Linux**:
- Install system dependencies: `sudo apt-get install build-essential ffmpeg`
- Consider using conda for GPU support

## 📈 Test Reports

### Automatic Reports

The test runner generates several reports:

1. **Console Output**: Real-time test results
2. **test_report.json**: Detailed test results in JSON format
3. **dependency_report.json**: Dependency status report

### Reading Reports

**Test Report Structure**:
```json
{
  "timestamp": "2024-01-01T12:00:00",
  "duration_seconds": 45.2,
  "test_results": {
    "dependencies": {"success": true},
    "voice_service": {"success": false},
    "integration": {"success": true}
  },
  "summary": {
    "total_suites": 4,
    "passed_suites": 3
  }
}
```

## 🎯 Best Practices

### For Development
1. Run `python tests/run_all_tests.py --quick` before starting work
2. Run full test suite before committing changes
3. Check dependency status when adding new features

### For Deployment
1. Run complete test suite in target environment
2. Verify all required dependencies are available
3. Test with actual production configuration

### For Maintenance
1. Run tests regularly to catch regressions
2. Update tests when adding new features
3. Monitor test reports for system health

## 🔍 Advanced Usage

### Custom Test Configurations

Create custom test configurations by modifying the test runner:

```python
# Example: Test with specific model
from tests.run_all_tests import TestRunner

runner = TestRunner()
runner.run_dependency_validation()
# Add custom tests here
```

### Integration with CI/CD

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    python tests/run_all_tests.py
    if [ $? -eq 0 ]; then
      echo "All tests passed"
    else
      echo "Tests failed"
      exit 1
    fi
```

### Performance Monitoring

Use test results to monitor system performance over time:

```bash
# Regular health checks
python tests/run_all_tests.py --suite integration
```

## 📚 Additional Resources

- [Main README](../README.md) - Project overview and setup
- [Requirements Documentation](../requirements.txt) - Dependency information
- [API Documentation](../src/api/) - API endpoint details
- [Service Documentation](../src/services/) - Service implementation details

---

**Need Help?** 

If you encounter issues with the test suite:

1. Check the console output for specific error messages
2. Review the dependency validation report
3. Ensure all required packages are installed
4. Verify file permissions for logs and cache directories
5. Check platform-specific requirements

The test suite is designed to be informative and helpful - it should guide you toward resolving any issues you encounter.