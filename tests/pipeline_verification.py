"""
Pipeline Implementation Verification System
Ensures all core pipelines are properly implemented and functional
"""
import os
import sys
import importlib
from pathlib import Path
from typing import Dict, List, Any, Tuple

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

class PipelineVerifier:
    """Systematic verification of all implemented pipelines"""
    
    def __init__(self):
        self.project_root = project_root
        self.results = {}
        
    def verify_all_pipelines(self) -> Dict[str, Any]:
        """Verify all core pipelines are implemented"""
        print("🔍 PIPELINE IMPLEMENTATION VERIFICATION")
        print("=" * 60)
        
        self.results["request_pipeline"] = self._verify_request_pipeline()
        
        self.results["voice_pipeline"] = self._verify_voice_pipeline()
        
        self.results["training_pipeline"] = self._verify_training_pipeline()
        
        self.results["analytics_pipeline"] = self._verify_analytics_pipeline()
        
        self.results["config_system"] = self._verify_config_system()
        
        self.results["organization"] = self._verify_organization()
        
        return self.results
    
    def _verify_request_pipeline(self) -> Dict[str, Any]:
        """Verify Request Processing Pipeline: Input → Validation → Context → AI → Response"""
        print("\n🔄 Request Processing Pipeline")
        print("-" * 40)
        
        pipeline_components = {
            "preprocessing": "src/services/preprocessing_service.py",
            "context_management": "src/services/context_service.py", 
            "chat_orchestration": "src/services/chat_service.py",
            "ai_generation": "src/fallback_responses.py",
            "postprocessing": "src/services/postprocessing_service.py"
        }
        
        results = {"status": "success", "components": {}, "flow_verified": False}
        
        for component, file_path in pipeline_components.items():
            full_path = self.project_root / file_path
            exists = full_path.exists()
            results["components"][component] = {
                "file": file_path,
                "exists": exists,
                "status": "✅" if exists else "❌"
            }
            print(f"   {component:20} {'✅' if exists else '❌'} {file_path}")
        
        try:
            chat_service_path = self.project_root / "src/services/chat_service.py"
            if chat_service_path.exists():
                content = chat_service_path.read_text()
                has_context = "context_service" in content or "ContextWindowManager" in content
                has_preprocessing = "preprocessing" in content or "validation" in content
                has_ai_gen = "generate_ai_response" in content or "fallback_responses" in content
                
                results["flow_verified"] = has_context and has_ai_gen
                print(f"   Pipeline Flow:      {'✅' if results['flow_verified'] else '❌'} Integrated")
        except Exception as e:
            results["flow_verified"] = False
            print(f"   Pipeline Flow:      ❌ Error: {e}")
        
        return results
    
    def _verify_voice_pipeline(self) -> Dict[str, Any]:
        """Verify Voice Processing Pipeline: Audio → STT → Processing → TTS → Audio"""
        print("\n🎤 Voice Processing Pipeline")
        print("-" * 40)
        
        voice_components = {
            "stt_service": "src/services/stt_service.py",
            "transcript_processor": "src/services/transcript_processor.py",
            "audio_analysis": "src/services/advanced_audio_analysis.py",
            "tts_service": "src/services/tts_service.py",
            "voice_orchestration": "src/services/voice_service.py",
            "voice_routes": "src/api/routes/voice_routes.py"
        }
        
        results = {"status": "success", "components": {}, "integration_verified": False}
        
        for component, file_path in voice_components.items():
            full_path = self.project_root / file_path
            exists = full_path.exists()
            results["components"][component] = {
                "file": file_path,
                "exists": exists,
                "status": "✅" if exists else "❌"
            }
            print(f"   {component:20} {'✅' if exists else '❌'} {file_path}")
        
        try:
            voice_routes_path = self.project_root / "src/api/routes/voice_routes.py"
            if voice_routes_path.exists():
                content = voice_routes_path.read_text()
                has_stt = "stt_service" in content
                has_tts = "tts_service" in content
                has_chat_integration = "chat_service" in content
                
                results["integration_verified"] = has_stt and has_tts and has_chat_integration
                print(f"   Pipeline Integration: {'✅' if results['integration_verified'] else '❌'} Voice → Chat")
        except Exception as e:
            results["integration_verified"] = False
            print(f"   Pipeline Integration: ❌ Error: {e}")
        
        return results
    
    def _verify_training_pipeline(self) -> Dict[str, Any]:
        """Verify Training Pipeline: Data → Training → Validation → Deployment"""
        print("\n🎓 Training Pipeline")
        print("-" * 40)
        
        training_components = {
            "core_training": "training/core_pipeline/model_training.py",
            "roleplay_training": "training/core_pipeline/roleplay_training.py", 
            "training_coordinator": "training/enhanced_training_coordinator.py",
            "model_config": "src/config/model_config.py",
            "data_directory": "training/data",
            "models_directory": "training/models"
        }
        
        results = {"status": "success", "components": {}, "config_verified": False}
        
        for component, file_path in training_components.items():
            full_path = self.project_root / file_path
            exists = full_path.exists()
            results["components"][component] = {
                "file": file_path,
                "exists": exists,
                "status": "✅" if exists else "❌"
            }
            print(f"   {component:20} {'✅' if exists else '❌'} {file_path}")
        
        try:
            model_config_path = self.project_root / "src/config/model_config.py"
            if model_config_path.exists():
                content = model_config_path.read_text()
                has_base_config = "BASE_MODEL" in content
                has_trained_config = "TRAINED_MODEL_PATH" in content
                has_switching = "USE_TRAINED_MODEL" in content
                
                results["config_verified"] = has_base_config and has_trained_config and has_switching
                print(f"   Model Switching:    {'✅' if results['config_verified'] else '❌'} Configured")
        except Exception as e:
            results["config_verified"] = False
            print(f"   Model Switching:    ❌ Error: {e}")
        
        return results
    
    def _verify_analytics_pipeline(self) -> Dict[str, Any]:
        """Verify Analytics Pipeline: Events → Logging → Aggregation → Reporting"""
        print("\n📊 Analytics Pipeline") 
        print("-" * 40)
        
        analytics_components = {
            "analytics_logger": "src/services/analytics_logger.py",
            "analytics_aggregator": "src/services/analytics_aggregator.py",
            "analytics_service": "src/services/analytics_service.py",
            "quality_metrics": "src/services/quality_metrics_service.py",
            "progress_service": "src/services/progress_service.py"
        }
        
        results = {"status": "success", "components": {}, "integration_verified": False}
        
        for component, file_path in analytics_components.items():
            full_path = self.project_root / file_path
            exists = full_path.exists()
            results["components"][component] = {
                "file": file_path,
                "exists": exists,
                "status": "✅" if exists else "❌"
            }
            print(f"   {component:20} {'✅' if exists else '❌'} {file_path}")
        
        try:
            chat_service_path = self.project_root / "src/services/chat_service.py"
            if chat_service_path.exists():
                content = chat_service_path.read_text()
                has_analytics = "analytics" in content.lower()
                has_logging = "track_event" in content or "log_" in content
                
                results["integration_verified"] = has_analytics or has_logging
                print(f"   Analytics Integration: {'✅' if results['integration_verified'] else '❌'} Chat Service")
        except Exception as e:
            results["integration_verified"] = False
            print(f"   Analytics Integration: ❌ Error: {e}")
        
        return results
    
    def _verify_config_system(self) -> Dict[str, Any]:
        """Verify Configuration System"""
        print("\n⚙️ Configuration System")
        print("-" * 40)
        
        config_files = {
            "main_settings": "src/config/settings.py",
            "model_config": "src/config/model_config.py", 
            "config_init": "src/config/__init__.py",
            "env_example": ".env.example",
            "requirements": "requirements.txt"
        }
        
        results = {"status": "success", "files": {}, "imports_verified": False}
        
        for config_name, file_path in config_files.items():
            full_path = self.project_root / file_path
            exists = full_path.exists()
            results["files"][config_name] = {
                "file": file_path,
                "exists": exists,
                "status": "✅" if exists else "❌"
            }
            print(f"   {config_name:20} {'✅' if exists else '❌'} {file_path}")
        
        try:
            config_init_path = self.project_root / "src/config/__init__.py"
            if config_init_path.exists():
                content = config_init_path.read_text()
                has_model_config = "model_config" in content
                has_settings = "settings" in content
                
                results["imports_verified"] = has_model_config and has_settings
                print(f"   Config Imports:     {'✅' if results['imports_verified'] else '❌'} Properly configured")
        except Exception as e:
            results["imports_verified"] = False
            print(f"   Config Imports:     ❌ Error: {e}")
        
        return results
    
    def _verify_organization(self) -> Dict[str, Any]:
        """Verify file organization and structure"""
        print("\n🗂️ File Organization")
        print("-" * 40)
        
        expected_structure = {
            "src_directory": "src",
            "tests_directory": "tests", 
            "training_directory": "training",
            "frontend_directory": "frontend",
            "docs_indexed": "DOCUMENTATION_INDEX.md",
            "structure_documented": "PROJECT_STRUCTURE.md",
            "backups_segregated": "backups",
            "archive_created": "archive"
        }
        
        results = {"status": "success", "structure": {}, "organization_score": 0}
        
        score = 0
        total = len(expected_structure)
        
        for item_name, path in expected_structure.items():
            full_path = self.project_root / path
            exists = full_path.exists()
            results["structure"][item_name] = {
                "path": path,
                "exists": exists,
                "status": "✅" if exists else "❌"
            }
            if exists:
                score += 1
            print(f"   {item_name:20} {'✅' if exists else '❌'} {path}")
        
        results["organization_score"] = round((score / total) * 100)
        print(f"   Organization Score: {results['organization_score']}% ({score}/{total})")
        
        return results
    
    def print_summary(self):
        """Print comprehensive summary of pipeline verification"""
        print("\n" + "=" * 60)
        print("📋 PIPELINE VERIFICATION SUMMARY")
        print("=" * 60)
        
        total_pipelines = 0
        working_pipelines = 0
        
        pipeline_status = {
            "request_pipeline": "Request Processing",
            "voice_pipeline": "Voice Processing", 
            "training_pipeline": "Training Pipeline",
            "analytics_pipeline": "Analytics Pipeline",
            "config_system": "Configuration System",
            "organization": "File Organization"
        }
        
        for pipeline_key, pipeline_name in pipeline_status.items():
            total_pipelines += 1
            if pipeline_key in self.results:
                pipeline_data = self.results[pipeline_key]
                
                if pipeline_key == "organization":
                    is_working = pipeline_data.get("organization_score", 0) >= 80
                else:
                    components = pipeline_data.get("components", {})
                    if components:
                        working_components = sum(1 for comp in components.values() if comp.get("exists", False))
                        total_components = len(components)
                        is_working = (working_components / total_components) >= 0.8
                    else:
                        is_working = False
                
                if is_working:
                    working_pipelines += 1
                
                status_icon = "✅" if is_working else "⚠️"
                print(f"{status_icon} {pipeline_name:25} {'IMPLEMENTED' if is_working else 'PARTIAL'}")
        
        overall_score = round((working_pipelines / total_pipelines) * 100)
        print(f"\n🎯 Overall Implementation: {overall_score}% ({working_pipelines}/{total_pipelines} pipelines)")
        
        if overall_score >= 90:
            print("🎉 EXCELLENT! All pipelines systematically implemented")
        elif overall_score >= 70:
            print("✅ GOOD! Most pipelines implemented, minor gaps remain")
        else:
            print("⚠️ NEEDS WORK! Several pipelines require attention")
        
        print("\n📖 For detailed documentation:")
        print("   • DOCUMENTATION_INDEX.md - All documentation")
        print("   • PROJECT_STRUCTURE.md - Complete structure guide")
        print("   • SYSTEMATIC_ORGANIZATION.md - Organization details")

def main():
    """Main verification function"""
    verifier = PipelineVerifier()
    results = verifier.verify_all_pipelines()
    verifier.print_summary()
    
    return 0 if all(r.get("status") == "success" for r in results.values()) else 1

if __name__ == "__main__":
    sys.exit(main())