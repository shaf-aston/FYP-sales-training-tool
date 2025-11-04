# 📚 Documentation Index - Sales Roleplay Chatbot

## 📖 Quick Navigation

### 🚀 Getting Started
1. **[STARTUP_GUIDE.md](./STARTUP_GUIDE.md)** - How to start the application
2. **[PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md)** - Complete project organization
3. **[README.md](./README.md)** - Project overview and setup
4. **[docs/API_REFERENCE.md](./docs/API_REFERENCE.md)** - Unified API endpoints and migration map
5. **[docs/UPGRADING_MODELS.md](./docs/UPGRADING_MODELS.md)** - Safe upgrade process for AI models
6. **[docs/POSTGRES_MIGRATION.md](./docs/POSTGRES_MIGRATION.md)** - Plan and utilities for PostgreSQL migration

---

## 🔧 Recent Changes & Fixes

### ✅ Latest Optimizations (Nov 4, 2025)
- **[OPTIMIZATION_FIXES_COMPLETE.md](./OPTIMIZATION_FIXES_COMPLETE.md)**
  - 2x faster AI responses (15-20s → 7-10s)
  - Frontend endpoint fixed
  - Model switching system added
  - Training pipeline preserved
  - Dependency validation tests updated

---

## 📂 Feature Documentation

### 🎯 Core Features
- **[IMPLEMENTATION_COMPLETE.md](./IMPLEMENTATION_COMPLETE.md)** - Core implementation status
- **[FUNCTIONALITY_VERIFIED.md](./FUNCTIONALITY_VERIFIED.md)** - Verified features
- **[CHAT_INTERFACE_IMPLEMENTATION.md](./CHAT_INTERFACE_IMPLEMENTATION.md)** - Chat interface details

### 🎤 Voice Features
- **[VOICE_FEATURES.md](./VOICE_FEATURES.md)** - Voice capabilities overview
- **[GOOGLE_CLOUD_STT_SETUP.md](./GOOGLE_CLOUD_STT_SETUP.md)** - STT setup instructions
- **[GOOGLE_CLOUD_STT_QUICK_REF.md](./GOOGLE_CLOUD_STT_QUICK_REF.md)** - STT quick reference
- **[STT_OPTIMIZATION_TECHNICAL_SUMMARY.md](./STT_OPTIMIZATION_TECHNICAL_SUMMARY.md)** - STT optimizations

### ⚡ Performance & Optimization
- **[OPTIMIZATION_COMPLETE.md](./OPTIMIZATION_COMPLETE.md)** - General optimizations
- **[demo_optimizations.py](./demo_optimizations.py)** - Demo optimization code
- **[validate_optimizations.py](./validate_optimizations.py)** - Validation scripts
- **[verify_optimizations.py](./verify_optimizations.py)** - Verification test suite

---

## 🏗️ Implementation Details

### 📋 Implementation Guides
- **[IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md)** - Overall status
- **[IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)** - Summary of implementations
- **[IMPLEMENTATION_GOOGLE_CLOUD_STT.md](./IMPLEMENTATION_GOOGLE_CLOUD_STT.md)** - STT implementation
- **[IMPLEMENTATION_TRANSCRIPT_PREPROCESSING.md](./IMPLEMENTATION_TRANSCRIPT_PREPROCESSING.md)** - Transcript processing

### 🧪 Testing
- **[tests/README.md](./tests/README.md)** - Testing overview
- **Test Scripts:**
  - `test_integration.py` - Integration tests
  - `test_google_cloud_stt.py` - STT tests
  - `test_optimization_features.py` - Optimization tests
  - `test_server.py` - Server tests
  - `test_dependencies.py` - Dependency validation tests

---

## 🎓 Technical References

### 📊 Architecture
- **[model training chat architecture.mmd](./model%20training%20chat%20architecture.mmd)** - System architecture diagram
- **[use_case.mmd](./use_case.mmd)** - Use case diagram

### 🔍 Analysis & Reports
- **[dependency_report.json](./dependency_report.json)** - Dependency analysis
- **[dashboard_fixes_summary.py](./dashboard_fixes_summary.py)** - Dashboard fixes

---

## 📝 Planning & Tasks

- **[TODO.md](./TODO.md)** - Task list and pending items
- **[Project Plan](./Project%20Plan)** - Overall project plan

---

## 📁 Code Documentation

### 🎨 Frontend
- **[frontend/README.md](./frontend/README.md)** - Frontend documentation
- **[frontend/DESIGN_SYSTEM.md](./frontend/DESIGN_SYSTEM.md)** - Design system
- **[frontend/PERFORMANCE_OPTIMIZATIONS.md](./frontend/PERFORMANCE_OPTIMIZATIONS.md)** - Frontend optimizations

### 🔧 Backend
- **[src/](./src/)** - Main source code (see PROJECT_STRUCTURE.md)
  - API routes in `src/api/routes/`
  - Business logic in `src/services/`
  - Configuration in `src/config/`

---

## 🔑 Quick Reference by Topic

### 🚀 Starting the App
1. Read: **STARTUP_GUIDE.md**
2. Run: `uvicorn src.main:app --reload --port 8000`
3. Frontend: `cd frontend && npm start`

### 🔧 Configuration
1. **App Settings**: `src/config/settings.py`
2. **Model Config**: `src/config/model_config.py`
3. **CORS Settings**: In `settings.py`

### ⚡ Performance Issues
1. Check: **OPTIMIZATION_FIXES_COMPLETE.md**
2. Run: `python verify_optimizations.py`
3. Verify: Response time should be 7-10s

### 🎤 Voice Features
1. Setup: **GOOGLE_CLOUD_STT_SETUP.md**
2. Quick Ref: **GOOGLE_CLOUD_STT_QUICK_REF.md**
3. Code: `src/services/stt_service.py`

### 🐛 Troubleshooting
1. **Frontend not loading**: Check CORS in `src/config/settings.py`
2. **Slow responses**: See OPTIMIZATION_FIXES_COMPLETE.md
3. **500 errors**: Use `/api/chat` endpoint (not `/api/v2/personas/chat`)
4. **Import errors**: Run `pip install -r requirements.txt`

### 🎓 Training Pipeline
1. **Location**: `training/` directory
2. **Status**: Preserved, not activated
3. **Activate**: Set `USE_TRAINED_MODEL=1` environment variable
4. **Config**: `src/config/model_config.py`

---

## 📊 Document Status

| Document | Status | Last Updated |
|----------|--------|--------------|
| OPTIMIZATION_FIXES_COMPLETE.md | ✅ Current | Nov 4, 2025 |
| PROJECT_STRUCTURE.md | ✅ Current | Nov 4, 2025 |
| STARTUP_GUIDE.md | ✅ Current | Recent |
| README.md | ✅ Current | Recent |
| VOICE_FEATURES.md | ✅ Current | Recent |
| TODO.md | ⚠️ May need update | Check file |

---

## 🎯 Key Takeaways

### ✅ What's Working
- Main chat endpoint: `/api/chat`
- Voice features: STT/TTS
- Context management: Enhanced selection
- Performance: 2x faster responses (optimized)

### 🔧 What Changed Recently
- AI generation optimized (32 tokens, greedy decoding)
- Frontend fixed to use working endpoint
- Model switching system added
- Backup files moved to `backups/` directory
- Dependency validation tests added

### 📋 What's Next
- Test optimizations with `verify_optimizations.py`
- Optional: Train custom model in `training/`
- Monitor response times in logs
- Customize personas in `src/models/character_profiles.py`

---

## 💡 Pro Tips

1. **Always start here**: Read STARTUP_GUIDE.md first
2. **Check structure**: Use PROJECT_STRUCTURE.md to navigate code
3. **Verify fixes**: Run verify_optimizations.py after changes
4. **Read recent docs**: OPTIMIZATION_FIXES_COMPLETE.md has latest info
5. **Test incrementally**: Use test scripts in `tests/` directory

---

*This index is your starting point for all documentation.*  
*For quick help, use Ctrl+F to search for keywords.*

**Most Important Files:**
1. 🚀 **STARTUP_GUIDE.md** - Get started
2. 📁 **PROJECT_STRUCTURE.md** - Understand organization
3. ⚡ **OPTIMIZATION_FIXES_COMPLETE.md** - Recent improvements

---

*Last Updated: November 4, 2025*  
*Documentation Status: ✅ Organized & Current*
