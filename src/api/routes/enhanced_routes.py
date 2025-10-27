"""
Enhanced API routes for AI Sales Training System
Includes persona management, progress tracking, and feedback analytics
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import logging

# Import services
from services.persona_service import persona_service, PersonaType, DifficultyLevel
from services.progress_service import progress_service, SkillLevel, TrainingMetric
from services.feedback_service import feedback_service, FeedbackType, FeedbackCategory
from services.rag_service import rag_service
from services.preprocessing_service import preprocessing_service
from services.postprocessing_service import postprocessing_service
from services.voice_service import get_voice_service
from services.model_optimization_service import model_optimization_service
from services.validation_service import validation_service

logger = logging.getLogger(__name__)

# Enhanced API router
enhanced_router = APIRouter(prefix="/api/v2", tags=["Enhanced Training"])

# Pydantic models for request/response validation
class PersonaSelectionRequest(BaseModel):
    persona_name: str
    scenario: Optional[str] = "initial_contact"
    difficulty_preference: Optional[str] = None

class TrainingSessionRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None

class FeedbackRequest(BaseModel):
    session_id: str
    user_id: str
    success_rating: Optional[int] = None

class LearningGoalRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    target_skill: str
    target_level: str
    target_date: Optional[float] = None
    milestones: Optional[List[Dict[str, Any]]] = []

class UserAssessmentRequest(BaseModel):
    experience_level: Optional[str] = "beginner"
    preferred_training_style: Optional[str] = "guided"
    strengths: Optional[List[str]] = []
    improvement_areas: Optional[List[str]] = []

# Persona Management Endpoints
@enhanced_router.get("/personas")
async def list_personas(
    difficulty: Optional[str] = None,
    persona_type: Optional[str] = None
) -> Dict[str, Any]:
    """List available training personas with filtering options"""
    try:
        personas = persona_service.list_personas()
        
        # Apply filters
        if difficulty:
            personas = [p for p in personas if p["difficulty"] == difficulty]
        
        if persona_type:
            personas = [p for p in personas if p["type"] == persona_type]
        
        return {
            "personas": personas,
            "total_count": len(personas),
            "available_difficulties": [d.value for d in DifficultyLevel],
            "available_types": [t.value for t in PersonaType]
        }
    except Exception as e:
        logger.error(f"Error listing personas: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve personas")

@enhanced_router.get("/personas/{persona_name}")
async def get_persona_details(persona_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific persona"""
    try:
        persona = persona_service.get_persona(persona_name)
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        
        return {
            "persona": persona.to_dict(),
            "training_tips": {
                "focus_areas": ["rapport building", "objection handling", "closing techniques"],
                "common_challenges": persona.objections,
                "success_strategies": [
                    f"Address their {persona.decision_style} decision-making style",
                    f"Focus on their budget range: {persona.budget_range}",
                    f"Adapt to their {persona.expertise_level} expertise level"
                ]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting persona details: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve persona details")

@enhanced_router.post("/personas/start-session")
async def start_persona_training_session(request: PersonaSelectionRequest) -> Dict[str, Any]:
    """Start a new training session with selected persona"""
    try:
        # Generate user_id if not provided (in production, this would come from authentication)
        user_id = f"user_{int(time.time())}"
        
        session_data = persona_service.start_training_session(
            user_id=user_id,
            persona_name=request.persona_name,
            scenario=request.scenario
        )
        
        # Initialize user progress tracking if needed
        progress_service.initialize_user_profile(user_id)
        
        return {
            "session_started": True,
            "session_data": session_data,
            "initial_greeting": f"Hello! I'm {session_data['persona']['name']}. {session_data['persona']['background']}",
            "training_guidance": {
                "focus_on": [
                    "Building rapport",
                    "Understanding their needs",
                    "Addressing their concerns",
                    "Presenting relevant solutions"
                ],
                "persona_hints": {
                    "personality": session_data['persona']['personality_traits'],
                    "main_concerns": session_data['persona']['concerns'],
                    "budget_range": session_data['persona']['budget_range']
                }
            }
        }
    except Exception as e:
        logger.error(f"Error starting persona session: {e}")
        raise HTTPException(status_code=500, detail="Failed to start training session")

@enhanced_router.post("/personas/chat")
async def chat_with_persona(request: TrainingSessionRequest) -> Dict[str, Any]:
    """Send message to persona and get response"""
    try:
        from services.model_service import model_service
        pipe = model_service.get_pipeline()
        
        if not pipe:
            raise HTTPException(status_code=503, detail="AI model not available")
        
        response_data = persona_service.generate_persona_response(
            session_id=request.session_id,
            user_message=request.message,
            pipe=pipe
        )
        
        return {
            "success": True,
            "persona_response": response_data["response"],
            "persona_name": response_data["persona_name"],
            "analysis": response_data["analysis"],
            "training_feedback": {
                "interaction_type": response_data["analysis"].get("interaction_type"),
                "engagement_level": response_data["analysis"].get("engagement_level"),
                "suggestions": response_data["analysis"].get("suggested_improvements", [])
            }
        }
    except Exception as e:
        logger.error(f"Error in persona chat: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate persona response")

# Progress Tracking Endpoints
@enhanced_router.post("/progress/initialize")
async def initialize_user_progress(
    user_id: str,
    assessment: Optional[UserAssessmentRequest] = None
) -> Dict[str, Any]:
    """Initialize user progress tracking with optional initial assessment"""
    try:
        assessment_data = assessment.dict() if assessment else None
        profile = progress_service.initialize_user_profile(user_id, assessment_data)
        
        return {
            "profile_created": True,
            "user_profile": profile,
            "next_steps": [
                "Complete your first training session",
                "Set learning goals",
                "Choose preferred persona types"
            ]
        }
    except Exception as e:
        logger.error(f"Error initializing user progress: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize user progress")

@enhanced_router.get("/progress/{user_id}/dashboard")
async def get_progress_dashboard(user_id: str) -> Dict[str, Any]:
    """Get comprehensive progress dashboard for user"""
    try:
        dashboard = progress_service.get_user_progress_dashboard(user_id)
        
        if "error" in dashboard:
            raise HTTPException(status_code=404, detail=dashboard["error"])
        
        return dashboard
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting progress dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve progress dashboard")

@enhanced_router.post("/progress/{user_id}/goals")
async def create_learning_goal(user_id: str, goal_data: LearningGoalRequest) -> Dict[str, Any]:
    """Create a new learning goal for the user"""
    try:
        goal_id = progress_service.create_learning_goal(user_id, goal_data.dict())
        
        return {
            "goal_created": True,
            "goal_id": goal_id,
            "message": "Learning goal created successfully"
        }
    except Exception as e:
        logger.error(f"Error creating learning goal: {e}")
        raise HTTPException(status_code=500, detail="Failed to create learning goal")

@enhanced_router.get("/progress/leaderboard")
async def get_leaderboard(
    timeframe: str = "all_time",
    skill: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """Get leaderboard rankings"""
    try:
        leaderboard = progress_service.get_leaderboard(timeframe, skill)
        
        return {
            "leaderboard": leaderboard[:limit],
            "timeframe": timeframe,
            "skill_filter": skill,
            "total_users": len(leaderboard)
        }
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve leaderboard")

# Feedback Analytics Endpoints
@enhanced_router.post("/feedback/analyze")
async def analyze_training_session(request: FeedbackRequest) -> Dict[str, Any]:
    """Analyze a completed training session and provide detailed feedback"""
    try:
        # Get session data from persona service
        if request.session_id not in persona_service.active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = persona_service.active_sessions[request.session_id].copy()
        
        # Add success rating if provided
        if request.success_rating:
            session_data["success_rating"] = request.success_rating
        
        # Perform comprehensive analysis
        analysis_results = feedback_service.analyze_conversation(session_data, request.user_id)
        
        # Record session in progress tracking
        progress_record = progress_service.record_training_session(request.user_id, session_data)
        
        # End the persona session
        persona_service.end_training_session(request.session_id, request.success_rating)
        
        return {
            "analysis_completed": True,
            "feedback_analysis": analysis_results,
            "progress_update": progress_record,
            "recommendations": {
                "immediate_focus": analysis_results.get("improvement_priorities", [])[:2],
                "next_training_session": progress_record.get("next_recommendations", [])[:3],
                "skill_development": progress_record.get("updated_skills", {})
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing training session: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze training session")

@enhanced_router.get("/feedback/{user_id}/improvement-plan")
async def get_improvement_plan(
    user_id: str,
    timeframe_days: int = 30
) -> Dict[str, Any]:
    """Generate personalized improvement plan based on feedback history"""
    try:
        improvement_plan = feedback_service.generate_improvement_plan(user_id, timeframe_days)
        
        if "error" in improvement_plan:
            raise HTTPException(status_code=404, detail=improvement_plan["error"])
        
        return improvement_plan
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating improvement plan: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate improvement plan")

@enhanced_router.get("/feedback/analytics/dashboard")
async def get_analytics_dashboard(
    user_id: Optional[str] = None,
    timeframe_days: int = 30
) -> Dict[str, Any]:
    """Get analytics dashboard (user-specific or system-wide)"""
    try:
        dashboard = feedback_service.get_analytics_dashboard(user_id, timeframe_days)
        
        if "error" in dashboard:
            raise HTTPException(status_code=404, detail=dashboard["error"])
        
        return dashboard
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analytics dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics dashboard")

# Training Recommendations Endpoints
@enhanced_router.get("/training/recommendations/{user_id}")
async def get_training_recommendations(user_id: str) -> Dict[str, Any]:
    """Get personalized training recommendations"""
    try:
        # Get user progress data
        dashboard = progress_service.get_user_progress_dashboard(user_id)
        
        if "error" in dashboard:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get feedback history for additional recommendations
        improvement_plan = feedback_service.generate_improvement_plan(user_id, 14)  # 2 weeks
        
        # Combine recommendations
        recommendations = {
            "user_id": user_id,
            "current_level": dashboard["user_profile"]["experience_level"],
            "immediate_priorities": dashboard.get("next_recommendations", []),
            "skill_focus_areas": [
                area for area, data in dashboard["skills_breakdown"].items() 
                if data["progress_percentage"] < 70
            ],
            "recommended_personas": [],
            "suggested_difficulty": "medium",
            "training_frequency": "3-4 sessions per week",
            "improvement_plan": improvement_plan if "error" not in improvement_plan else None
        }
        
        # Recommend personas based on skill gaps
        skill_gaps = [area for area, data in dashboard["skills_breakdown"].items() 
                     if data["progress_percentage"] < 60]
        
        if "objection_handling" in skill_gaps:
            recommendations["recommended_personas"].append("Jake (Skeptical)")
        if "rapport_building" in skill_gaps:
            recommendations["recommended_personas"].append("Mary (Health-focused)")
        if "time_management" in skill_gaps:
            recommendations["recommended_personas"].append("David (Time-constrained)")
        
        return recommendations
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting training recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get training recommendations")

# System Health and Monitoring
@enhanced_router.get("/system/health")
async def get_system_health() -> Dict[str, Any]:
    """Get comprehensive system health status"""
    try:
        from services.model_service import model_service
        from services.chat_service import chat_service
        
        model_name = model_service.get_model_name() or "Unknown"
        
        # Get health data from existing chat service
        base_health = chat_service.get_health_data(model_name)
        
        # Add enhanced system metrics
        enhanced_health = {
            **base_health,
            "enhanced_features": {
                "persona_management": {
                    "active_personas": len(persona_service.personas),
                    "active_sessions": len(persona_service.active_sessions),
                    "total_persona_interactions": sum(
                        p["total_sessions"] for p in persona_service.persona_performance.values()
                    )
                },
                "progress_tracking": {
                    "tracked_users": len(progress_service.user_profiles),
                    "active_learning_goals": sum(
                        len(goals) for goals in progress_service.learning_goals.values()
                    ),
                    "total_skill_assessments": len(progress_service.skill_assessments)
                },
                "feedback_analytics": {
                    "sessions_analyzed": len(feedback_service.session_analyses),
                    "users_with_feedback": len(feedback_service.user_feedback_history),
                    "total_feedback_items": sum(
                        len(analysis["feedback_items"]) 
                        for analysis in feedback_service.session_analyses.values()
                    )
                },
                "rag_system": {
                    "knowledge_base_loaded": len(rag_service.knowledge_base) > 0,
                    "total_documents": len(rag_service.knowledge_base),
                    "vector_store_ready": hasattr(rag_service, 'vector_store') and rag_service.vector_store is not None
                },
                "preprocessing_pipeline": {
                    "text_cleaner_active": True,
                    "persona_extractor_active": True,
                    "context_builder_active": True,
                    "metadata_assembler_active": True
                },
                "postprocessing_pipeline": {
                    "safety_filter_active": True,
                    "response_ranker_active": True,
                    "persona_refiner_active": True,
                    "tone_adjuster_active": True,
                    "response_validator_active": True
                },
                "voice_services": {
                    "tts_available": get_voice_service().is_available()["coqui_tts"],
                    "stt_available": get_voice_service().is_available()["whisper"],
                    "emotion_synthesis_enabled": True,
                    "voice_cloning_enabled": True
                },
                "model_optimization": {
                    "cache_active": len(model_optimization_service.model_cache) > 0,
                    "optimization_enabled": True,
                    "performance_monitoring": True
                },
                "validation_system": {
                    "input_validation_active": True,
                    "output_validation_active": True,
                    "safety_checks_enabled": True,
                    "total_validations_performed": validation_service.validation_stats["total_validations"]
                }
            },
            "api_status": {
                "persona_service": "operational",
                "progress_service": "operational", 
                "feedback_service": "operational",
                "rag_service": "operational",
                "preprocessing_service": "operational",
                "postprocessing_service": "operational",
                "voice_service": "operational",
                "model_optimization_service": "operational",
                "validation_service": "operational",
                "enhanced_routes": "active"
            },
            "system_capabilities": {
                "full_pipeline_processing": True,
                "rag_enhanced_responses": True,
                "voice_interaction": True,
                "comprehensive_validation": True,
                "performance_optimization": True,
                "advanced_feedback_analytics": True,
                "multi_persona_training": True,
                "progress_tracking": True
            }
        }
        
        return enhanced_health
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system health")

# Export user data (for compliance/backup)
@enhanced_router.get("/users/{user_id}/export")
async def export_user_data(user_id: str) -> Dict[str, Any]:
    """Export all user data for analysis or backup"""
    try:
        user_data = progress_service.export_user_data(user_id)
        
        if "error" in user_data:
            raise HTTPException(status_code=404, detail=user_data["error"])
        
        # Add feedback data
        feedback_history = feedback_service.user_feedback_history.get(user_id, [])
        user_data["feedback_history"] = feedback_history
        
        return {
            "export_successful": True,
            "user_data": user_data,
            "export_timestamp": user_data["export_date"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting user data: {e}")
        raise HTTPException(status_code=500, detail="Failed to export user data")

# Add time import at the top
import time

# New Pydantic models for additional services
class RAGQueryRequest(BaseModel):
    query: str
    context_size: Optional[int] = 5
    similarity_threshold: Optional[float] = 0.7

class VoiceProcessingRequest(BaseModel):
    audio_data: str  # Base64 encoded audio
    emotion_target: Optional[str] = "neutral"
    voice_clone_reference: Optional[str] = None

class ModelOptimizationRequest(BaseModel):
    model_name: str
    optimization_config: Optional[Dict[str, Any]] = None

class ValidationRequest(BaseModel):
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    validation_context: Optional[Dict[str, Any]] = None

# RAG Service Endpoints
@enhanced_router.post("/rag/query")
async def query_knowledge_base(request: RAGQueryRequest) -> Dict[str, Any]:
    """Query the RAG knowledge base for relevant information"""
    try:
        results = rag_service.search_knowledge_base(
            query=request.query,
            top_k=request.context_size,
            similarity_threshold=request.similarity_threshold
        )
        
        return {
            "success": True,
            "query": request.query,
            "results": results,
            "total_results": len(results)
        }
    except Exception as e:
        logger.error(f"Error in RAG query: {e}")
        raise HTTPException(status_code=500, detail="Failed to query knowledge base")

@enhanced_router.post("/rag/enhance-response")
async def enhance_response_with_rag(
    user_message: str,
    persona_response: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Enhance a response using RAG context"""
    try:
        enhanced_response = rag_service.enhance_response_with_context(
            user_message=user_message,
            persona_response=persona_response,
            context=context or {}
        )
        
        return {
            "success": True,
            "original_response": persona_response,
            "enhanced_response": enhanced_response["enhanced_response"],
            "context_used": enhanced_response["context_documents"],
            "enhancement_score": enhanced_response.get("enhancement_confidence", 0)
        }
    except Exception as e:
        logger.error(f"Error enhancing response with RAG: {e}")
        raise HTTPException(status_code=500, detail="Failed to enhance response")

# Preprocessing Service Endpoints
@enhanced_router.post("/preprocessing/analyze")
async def analyze_input_preprocessing(
    text: str,
    persona_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Analyze and preprocess input text"""
    try:
        # Perform comprehensive preprocessing
        cleaned_text = preprocessing_service.text_cleaner.clean_text(text)
        persona_analysis = preprocessing_service.persona_extractor.extract_persona_indicators(text)
        context_data = preprocessing_service.context_builder.build_context(text, persona_context or {})
        metadata = preprocessing_service.metadata_assembler.assemble_metadata(text, context_data)
        
        return {
            "success": True,
            "original_text": text,
            "cleaned_text": cleaned_text,
            "persona_indicators": persona_analysis,
            "context_data": context_data,
            "metadata": metadata,
            "processing_confidence": metadata.get("confidence_score", 0)
        }
    except Exception as e:
        logger.error(f"Error in preprocessing: {e}")
        raise HTTPException(status_code=500, detail="Failed to preprocess input")

# Post-processing Service Endpoints  
@enhanced_router.post("/postprocessing/enhance")
async def enhance_output_postprocessing(
    response: str,
    context: Optional[Dict[str, Any]] = None,
    persona_attributes: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Enhance output using post-processing pipeline"""
    try:
        # Run through post-processing pipeline
        safety_result = postprocessing_service.safety_filter.filter_response(response)
        
        if safety_result["safe"]:
            ranking_result = postprocessing_service.response_ranker.rank_responses([response], context or {})
            refined_response = postprocessing_service.persona_refiner.refine_for_persona(
                response, persona_attributes or {}
            )
            adjusted_response = postprocessing_service.tone_adjuster.adjust_tone(
                refined_response["refined_response"], context or {}
            )
            validation_result = postprocessing_service.response_validator.validate_response(
                adjusted_response, context or {}
            )
            
            return {
                "success": True,
                "original_response": response,
                "enhanced_response": adjusted_response,
                "safety_check": safety_result,
                "quality_score": ranking_result["scores"][0] if ranking_result["scores"] else 0,
                "persona_refinement": refined_response,
                "validation": validation_result
            }
        else:
            return {
                "success": False,
                "error": "Response failed safety check",
                "safety_check": safety_result,
                "blocked_response": response
            }
    except Exception as e:
        logger.error(f"Error in post-processing: {e}")
        raise HTTPException(status_code=500, detail="Failed to post-process response")

# Voice Service Endpoints
@enhanced_router.post("/voice/synthesize")
async def synthesize_speech(
    text: str,
    emotion: Optional[str] = "neutral",
    speaker_id: Optional[str] = None,
    voice_clone_reference: Optional[str] = None
) -> Dict[str, Any]:
    """Synthesize speech from text with emotion and voice cloning"""
    try:
        voice_service = get_voice_service()
        synthesis_result = voice_service.synthesize_speech(
            text=text,
            emotion=emotion,
            speaker_id=speaker_id,
            voice_clone_reference=voice_clone_reference
        )
        
        return {
            "success": True,
            "text": text,
            "emotion": emotion,
            "audio_data": synthesis_result["audio_data"],
            "synthesis_time": synthesis_result["processing_time"],
            "quality_score": synthesis_result.get("quality_score", 0)
        }
    except Exception as e:
        logger.error(f"Error in speech synthesis: {e}")
        raise HTTPException(status_code=500, detail="Failed to synthesize speech")

@enhanced_router.post("/voice/transcribe")
async def transcribe_speech(request: VoiceProcessingRequest) -> Dict[str, Any]:
    """Transcribe speech to text with confidence and emotion detection"""
    try:
        voice_service = get_voice_service()
        transcription_result = voice_service.transcribe_speech(
            audio_data=request.audio_data,
            detect_emotion=True
        )
        
        return {
            "success": True,
            "transcribed_text": transcription_result["text"],
            "confidence_score": transcription_result["confidence"],
            "detected_emotion": transcription_result.get("emotion", "neutral"),
            "processing_time": transcription_result["processing_time"]
        }
    except Exception as e:
        logger.error(f"Error in speech transcription: {e}")
        raise HTTPException(status_code=500, detail="Failed to transcribe speech")

# Model Optimization Endpoints
@enhanced_router.post("/optimization/load-model")
async def load_optimized_model(request: ModelOptimizationRequest) -> Dict[str, Any]:
    """Load model with optimization settings"""
    try:
        model, tokenizer = model_optimization_service.load_optimized_model(
            model_name=request.model_name,
            optimization_config=request.optimization_config
        )
        
        # Get performance metrics
        performance_stats = model_optimization_service.get_performance_analytics(request.model_name)
        
        return {
            "success": True,
            "model_name": request.model_name,
            "model_loaded": True,
            "optimization_applied": True,
            "performance_stats": performance_stats
        }
    except Exception as e:
        logger.error(f"Error loading optimized model: {e}")
        raise HTTPException(status_code=500, detail="Failed to load optimized model")

@enhanced_router.get("/optimization/cache-stats")
async def get_optimization_cache_stats() -> Dict[str, Any]:
    """Get model optimization cache statistics"""
    try:
        stats = model_optimization_service.get_cache_statistics()
        return {
            "success": True,
            "cache_statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache statistics")

@enhanced_router.post("/optimization/cleanup")
async def cleanup_model_cache(force: bool = False) -> Dict[str, Any]:
    """Clean up model cache"""
    try:
        cleanup_result = model_optimization_service.cleanup_cache(force=force)
        return {
            "success": True,
            "cleanup_result": cleanup_result
        }
    except Exception as e:
        logger.error(f"Error cleaning up cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup cache")

@enhanced_router.post("/optimization/warmup")
async def warmup_models(model_names: List[str]) -> Dict[str, Any]:
    """Warm up models for better performance"""
    try:
        warmup_result = model_optimization_service.warmup_models(model_names)
        return {
            "success": True,
            "warmup_result": warmup_result
        }
    except Exception as e:
        logger.error(f"Error warming up models: {e}")
        raise HTTPException(status_code=500, detail="Failed to warmup models")

# Validation Service Endpoints
@enhanced_router.post("/validation/validate-input")
async def validate_input_data(request: ValidationRequest) -> Dict[str, Any]:
    """Validate input data for safety and compliance"""
    try:
        if not request.input_data:
            raise HTTPException(status_code=400, detail="No input data provided")
        
        validation_results = validation_service.validate_input(
            input_data=request.input_data,
            validation_context=request.validation_context
        )
        
        return {
            "success": True,
            "validation_results": [result.to_dict() for result in validation_results],
            "passed_validations": len([r for r in validation_results if r.passed]),
            "failed_validations": len([r for r in validation_results if not r.passed]),
            "overall_safe": all(r.passed for r in validation_results)
        }
    except Exception as e:
        logger.error(f"Error validating input: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate input")

@enhanced_router.post("/validation/validate-output")
async def validate_output_data(request: ValidationRequest) -> Dict[str, Any]:
    """Validate output data for quality and safety"""
    try:
        if not request.output_data:
            raise HTTPException(status_code=400, detail="No output data provided")
        
        validation_results = validation_service.validate_output(
            output_data=request.output_data,
            input_context=request.input_data,
            validation_context=request.validation_context
        )
        
        return {
            "success": True,
            "validation_results": [result.to_dict() for result in validation_results],
            "passed_validations": len([r for r in validation_results if r.passed]),
            "failed_validations": len([r for r in validation_results if not r.passed]),
            "quality_acceptable": all(r.passed or r.level.value in ["info", "warning"] for r in validation_results)
        }
    except Exception as e:
        logger.error(f"Error validating output: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate output")

@enhanced_router.post("/validation/sanitize")
async def sanitize_input_text(text: str) -> Dict[str, Any]:
    """Sanitize input text for safety"""
    try:
        sanitized_text, validation_results = validation_service.sanitize_input(text)
        
        return {
            "success": True,
            "original_text": text,
            "sanitized_text": sanitized_text,
            "sanitization_applied": text != sanitized_text,
            "validation_results": [result.to_dict() for result in validation_results]
        }
    except Exception as e:
        logger.error(f"Error sanitizing text: {e}")
        raise HTTPException(status_code=500, detail="Failed to sanitize text")

@enhanced_router.get("/validation/stats")
async def get_validation_statistics() -> Dict[str, Any]:
    """Get validation service statistics"""
    try:
        stats = validation_service.get_validation_stats()
        return {
            "success": True,
            "validation_statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting validation stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get validation statistics")

@enhanced_router.get("/validation/report")
async def get_validation_report(timeframe_hours: int = 24) -> Dict[str, Any]:
    """Get comprehensive validation report"""
    try:
        report = validation_service.get_validation_report(timeframe_hours)
        return {
            "success": True,
            "validation_report": report
        }
    except Exception as e:
        logger.error(f"Error getting validation report: {e}")
        raise HTTPException(status_code=500, detail="Failed to get validation report")

# Integrated Enhanced Chat Endpoint
@enhanced_router.post("/chat/enhanced")
async def enhanced_chat_with_all_services(
    user_message: str,
    session_id: Optional[str] = None,
    persona_name: Optional[str] = None,
    enable_rag: bool = True,
    enable_voice: bool = False,
    validate_input: bool = True,
    validate_output: bool = True
) -> Dict[str, Any]:
    """Enhanced chat endpoint that integrates all services"""
    try:
        # Input validation
        if validate_input:
            input_validation = validation_service.validate_input({
                "message": user_message
            })
            
            if any(not r.passed and r.level.value == "error" for r in input_validation):
                return {
                    "success": False,
                    "error": "Input validation failed",
                    "validation_results": [r.to_dict() for r in input_validation]
                }
        
        # Sanitize input
        sanitized_message, sanitization_results = validation_service.sanitize_input(user_message)
        
        # Preprocessing
        preprocessing_results = await analyze_input_preprocessing(sanitized_message)
        
        # Get base response from persona or chat service
        if persona_name and session_id:
            persona_response_data = await chat_with_persona(TrainingSessionRequest(
                user_id="enhanced_user",
                message=sanitized_message,
                session_id=session_id
            ))
            base_response = persona_response_data["persona_response"]
        else:
            # Use regular chat service
            from services.chat_service import chat_service
            from services.model_service import model_service
            
            pipe = model_service.get_pipeline()
            if not pipe:
                raise HTTPException(status_code=503, detail="AI model not available")
            
            chat_response = chat_service.get_response(sanitized_message, pipe)
            base_response = chat_response["response"]
        
        # RAG enhancement
        if enable_rag:
            rag_enhancement = await enhance_response_with_rag(
                user_message=sanitized_message,
                persona_response=base_response
            )
            enhanced_response = rag_enhancement["enhanced_response"]
        else:
            enhanced_response = base_response
        
        # Post-processing
        postprocessing_results = await enhance_output_postprocessing(enhanced_response)
        
        if not postprocessing_results["success"]:
            return {
                "success": False,
                "error": "Response failed safety checks",
                "safety_details": postprocessing_results
            }
        
        final_response = postprocessing_results["enhanced_response"]
        
        # Output validation
        validation_results = []
        if validate_output:
            output_validation = validation_service.validate_output({
                "response": final_response,
                "timestamp": time.time()
            }, {"message": sanitized_message})
            validation_results = [r.to_dict() for r in output_validation]
        
        # Voice synthesis (if requested)
        voice_data = None
        if enable_voice:
            try:
                voice_synthesis = await synthesize_speech(final_response)
                voice_data = voice_synthesis["audio_data"]
            except Exception as e:
                logger.warning(f"Voice synthesis failed: {e}")
        
        return {
            "success": True,
            "response": final_response,
            "original_input": user_message,
            "sanitized_input": sanitized_message,
            "preprocessing_analysis": preprocessing_results,
            "rag_enhancement": enable_rag,
            "postprocessing_applied": True,
            "validation_results": validation_results,
            "voice_audio": voice_data,
            "processing_pipeline": {
                "input_sanitization": len(sanitization_results) > 0,
                "preprocessing": True,
                "rag_enhancement": enable_rag,
                "postprocessing": True,
                "output_validation": validate_output,
                "voice_synthesis": enable_voice and voice_data is not None
            }
        }
    except Exception as e:
        logger.error(f"Error in enhanced chat: {e}")
        raise HTTPException(status_code=500, detail="Failed to process enhanced chat request")