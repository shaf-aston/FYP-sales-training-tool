"""
Enhanced Training Package
Complete training infrastructure aligned with architectural diagram
"""

# Primary enhanced coordinator (recommended)
from .enhanced_training_coordinator import EnhancedTrainingCoordinator

# Legacy coordinator (backwards compatibility)
from .training_coordinator import TrainingCoordinator

# Core pipeline components
from .core_pipeline import (
    DataProcessingPipeline, ModelTrainer, TrainingConfig, ModelEvaluator,
    PersonaResponseGenerator, ObjectionHandler, FeatureExtraction,
    SalesPerformanceClassifier, FeedbackGenerator, ProgressTracker
)

# Validation and quality control systems
from .validation_quality_control import (
    ExpertComparisonValidator, AdvancedQualityValidator, ValidationOrchestrator
)

# Continuous improvement systems
from .continuous_improvement import ContinuousImprovementEngine

# Advanced analysis systems
from .analysis_systems import (
    NEPQAnalyzer, QuestionQualityAnalyzer, ActiveListeningAnalyzer, AdvancedPerformanceAnalyzer,
    BuyingStateAnalyzer, ScriptAlignmentAnalyzer, SalesStageProgressionAnalyzer,
    SpeechClarityAnalyzer, DisfluencyAnalyzer, QuestioningStyleAnalyzer, ComprehensiveSpeechAnalyzer
)

__version__ = "2.0.0"
__architecture_compliant__ = True

__all__ = [
    # Primary coordinator
    "EnhancedTrainingCoordinator",
    
    # Legacy coordinator
    "TrainingCoordinator",
    
    # Core pipeline
    "DataProcessingPipeline",
    "ModelTrainer", 
    "TrainingConfig",
    "ModelEvaluator",
    "PersonaResponseGenerator",
    "ObjectionHandler",
    "FeatureExtraction",
    "SalesPerformanceClassifier",
    "FeedbackGenerator",
    "ProgressTracker",
    
    # Validation systems
    "ExpertComparisonValidator",
    "AdvancedQualityValidator",
    "ValidationOrchestrator",
    
    # Improvement systems
    "ContinuousImprovementEngine",
    
    # Analysis systems
    "NEPQAnalyzer",
    "QuestionQualityAnalyzer",
    "ActiveListeningAnalyzer", 
    "AdvancedPerformanceAnalyzer",
    "BuyingStateAnalyzer",
    "ScriptAlignmentAnalyzer",
    "SalesStageProgressionAnalyzer",
    "SpeechClarityAnalyzer",
    "DisfluencyAnalyzer",
    "QuestioningStyleAnalyzer",
    "ComprehensiveSpeechAnalyzer"
]