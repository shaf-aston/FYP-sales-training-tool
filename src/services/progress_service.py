"""
Progress Tracking Service for AI Sales Training System
Tracks user learning progress, performance metrics, and generates insights
"""
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta

from config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

class SkillLevel(Enum):
    """Skill levels for training progress"""
    NOVICE = "novice"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

class TrainingMetric(Enum):
    """Key training metrics to track"""
    RAPPORT_BUILDING = "rapport_building"
    OBJECTION_HANDLING = "objection_handling"
    CLOSING_TECHNIQUES = "closing_techniques"
    PRODUCT_KNOWLEDGE = "product_knowledge"
    LISTENING_SKILLS = "listening_skills"
    PERSUASION_SKILLS = "persuasion_skills"
    TIME_MANAGEMENT = "time_management"

@dataclass
class SkillAssessment:
    """Individual skill assessment"""
    skill: TrainingMetric
    current_level: SkillLevel
    target_level: SkillLevel
    progress_percentage: float
    recent_scores: List[float]
    improvement_trend: str  # "improving", "stable", "declining"
    last_updated: float
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['skill'] = self.skill.value
        data['current_level'] = self.current_level.value
        data['target_level'] = self.target_level.value
        return data

@dataclass
class LearningGoal:
    """Individual learning goal"""
    goal_id: str
    title: str
    description: str
    target_skill: TrainingMetric
    target_level: SkillLevel
    target_date: float
    current_progress: float
    milestones: List[Dict[str, Any]]
    is_completed: bool
    created_date: float
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['target_skill'] = self.target_skill.value
        data['target_level'] = self.target_level.value
        return data

class ProgressTrackingService:
    """Service for tracking user learning progress and performance"""
    
    def __init__(self):
        self.user_profiles: Dict[str, Dict] = {}
        self.session_history: Dict[str, List[Dict]] = {}
        self.skill_assessments: Dict[str, Dict[TrainingMetric, SkillAssessment]] = {}
        self.learning_goals: Dict[str, List[LearningGoal]] = {}
        self.performance_trends: Dict[str, Dict] = {}
        self._initialize_skill_framework()
    
    def _initialize_skill_framework(self):
        """Initialize the skills framework and benchmarks"""
        self.skill_benchmarks = {
            TrainingMetric.RAPPORT_BUILDING: {
                SkillLevel.NOVICE: {"description": "Basic greeting, struggles with conversation flow", "min_score": 0},
                SkillLevel.BEGINNER: {"description": "Can engage in basic conversation, some awkward moments", "min_score": 40},
                SkillLevel.INTERMEDIATE: {"description": "Good conversation flow, finds common ground", "min_score": 60},
                SkillLevel.ADVANCED: {"description": "Excellent rapport, adapts communication style", "min_score": 80},
                SkillLevel.EXPERT: {"description": "Masterful connection, immediate trust building", "min_score": 90}
            },
            TrainingMetric.OBJECTION_HANDLING: {
                SkillLevel.NOVICE: {"description": "Defensive responses, doesn't address concerns", "min_score": 0},
                SkillLevel.BEGINNER: {"description": "Acknowledges objections, basic responses", "min_score": 35},
                SkillLevel.INTERMEDIATE: {"description": "Structured objection handling, addresses root causes", "min_score": 65},
                SkillLevel.ADVANCED: {"description": "Prevents objections, turns concerns into benefits", "min_score": 82},
                SkillLevel.EXPERT: {"description": "Masterful reframing, objections become closing opportunities", "min_score": 92}
            },
            TrainingMetric.CLOSING_TECHNIQUES: {
                SkillLevel.NOVICE: {"description": "Doesn't ask for the sale, passive approach", "min_score": 0},
                SkillLevel.BEGINNER: {"description": "Basic closing attempts, some success", "min_score": 30},
                SkillLevel.INTERMEDIATE: {"description": "Multiple closing techniques, reads buying signals", "min_score": 60},
                SkillLevel.ADVANCED: {"description": "Sophisticated closes, high success rate", "min_score": 80},
                SkillLevel.EXPERT: {"description": "Natural closing master, makes it feel inevitable", "min_score": 90}
            },
            TrainingMetric.PRODUCT_KNOWLEDGE: {
                SkillLevel.NOVICE: {"description": "Basic product awareness, limited details", "min_score": 0},
                SkillLevel.BEGINNER: {"description": "Knows main features, struggles with complex questions", "min_score": 45},
                SkillLevel.INTERMEDIATE: {"description": "Good product knowledge, handles most questions", "min_score": 70},
                SkillLevel.ADVANCED: {"description": "Comprehensive knowledge, relates features to benefits", "min_score": 85},
                SkillLevel.EXPERT: {"description": "Expert level knowledge, competitive comparisons", "min_score": 95}
            },
            TrainingMetric.LISTENING_SKILLS: {
                SkillLevel.NOVICE: {"description": "Interrupts frequently, misses key information", "min_score": 0},
                SkillLevel.BEGINNER: {"description": "Basic listening, catches main points", "min_score": 40},
                SkillLevel.INTERMEDIATE: {"description": "Active listening, asks clarifying questions", "min_score": 65},
                SkillLevel.ADVANCED: {"description": "Excellent listening, reads between the lines", "min_score": 80},
                SkillLevel.EXPERT: {"description": "Masterful listening, understands unspoken needs", "min_score": 90}
            },
            TrainingMetric.PERSUASION_SKILLS: {
                SkillLevel.NOVICE: {"description": "Pushes features without connecting to needs", "min_score": 0},
                SkillLevel.BEGINNER: {"description": "Basic benefit presentation, some persuasion", "min_score": 35},
                SkillLevel.INTERMEDIATE: {"description": "Good persuasion techniques, builds value", "min_score": 65},
                SkillLevel.ADVANCED: {"description": "Sophisticated persuasion, emotional connection", "min_score": 80},
                SkillLevel.EXPERT: {"description": "Influence master, consultative selling approach", "min_score": 90}
            },
            TrainingMetric.TIME_MANAGEMENT: {
                SkillLevel.NOVICE: {"description": "Unfocused conversations, wastes time", "min_score": 0},
                SkillLevel.BEGINNER: {"description": "Basic time awareness, some structure", "min_score": 40},
                SkillLevel.INTERMEDIATE: {"description": "Good meeting control, efficient discovery", "min_score": 65},
                SkillLevel.ADVANCED: {"description": "Excellent time management, focused conversations", "min_score": 80},
                SkillLevel.EXPERT: {"description": "Time optimization master, maximum value per minute", "min_score": 90}
            }
        }
    
    def initialize_user_profile(self, user_id: str, initial_assessment: Dict[str, Any] = None) -> Dict[str, Any]:
        """Initialize a new user profile with baseline assessments"""
        if user_id in self.user_profiles:
            return self.user_profiles[user_id]
        
        # Create user profile
        profile = {
            "user_id": user_id,
            "created_date": time.time(),
            "last_active": time.time(),
            "total_sessions": 0,
            "total_training_hours": 0.0,
            "current_tier": "novice",
            "experience_level": "beginner",
            "preferred_training_style": "guided",
            "strengths": [],
            "improvement_areas": [],
            "certifications": [],
            "custom_settings": {}
        }
        
        # Apply initial assessment if provided
        if initial_assessment:
            profile.update(initial_assessment)
        
        # Initialize skill assessments
        skill_assessments = {}
        for skill in TrainingMetric:
            assessment = SkillAssessment(
                skill=skill,
                current_level=SkillLevel.NOVICE,
                target_level=SkillLevel.INTERMEDIATE,
                progress_percentage=0.0,
                recent_scores=[],
                improvement_trend="stable",
                last_updated=time.time()
            )
            skill_assessments[skill] = assessment
        
        # Store everything
        self.user_profiles[user_id] = profile
        self.skill_assessments[user_id] = skill_assessments
        self.session_history[user_id] = []
        self.learning_goals[user_id] = []
        self.performance_trends[user_id] = {}
        
        logger.info(f"Initialized user profile for {user_id}")
        return profile
    
    def record_training_session(self, user_id: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record a completed training session and update progress"""
        if user_id not in self.user_profiles:
            self.initialize_user_profile(user_id)
        
        # Extract session metrics
        session_summary = {
            "session_id": session_data.get("session_id"),
            "persona_name": session_data.get("persona", {}).get("name"),
            "start_time": session_data.get("start_time"),
            "end_time": session_data.get("end_time", time.time()),
            "duration_minutes": (session_data.get("end_time", time.time()) - session_data.get("start_time", time.time())) / 60,
            "conversation_exchanges": len(session_data.get("conversation_history", [])),
            "success_rating": session_data.get("success_rating", 0),
            "performance_scores": {}
        }
        
        # Analyze session for skill performance
        performance_analysis = self._analyze_session_performance(session_data)
        session_summary["performance_scores"] = performance_analysis
        
        # Update user profile
        self.user_profiles[user_id]["total_sessions"] += 1
        self.user_profiles[user_id]["total_training_hours"] += session_summary["duration_minutes"] / 60
        self.user_profiles[user_id]["last_active"] = time.time()
        
        # Update skill assessments
        self._update_skill_assessments(user_id, performance_analysis)
        
        # Store session history
        self.session_history[user_id].append(session_summary)
        
        # Update performance trends
        self._update_performance_trends(user_id, session_summary)
        
        # Check for achievements and milestones
        achievements = self._check_achievements(user_id, session_summary)
        
        logger.info(f"Recorded training session for {user_id}: {session_summary['session_id']}")
        
        return {
            "session_recorded": True,
            "session_summary": session_summary,
            "updated_skills": self._get_skill_updates(user_id),
            "achievements": achievements,
            "next_recommendations": self._generate_next_steps(user_id)
        }
    
    def _analyze_session_performance(self, session_data: Dict[str, Any]) -> Dict[str, float]:
        """Analyze session data to extract performance scores for each skill"""
        conversation_history = session_data.get("conversation_history", [])
        persona_data = session_data.get("persona", {})
        success_rating = session_data.get("success_rating", 0)
        
        # Initialize scores
        scores = {skill.value: 50.0 for skill in TrainingMetric}  # Start with neutral scores
        
        if not conversation_history:
            return scores
        
        # Analyze conversation for skill indicators
        total_exchanges = len(conversation_history)
        user_responses = [exchange.get("user_message", "") for exchange in conversation_history]
        persona_responses = [exchange.get("persona_response", "") for exchange in conversation_history]
        
        # Rapport Building Analysis
        rapport_indicators = 0
        for response in user_responses:
            response_lower = response.lower()
            if any(word in response_lower for word in ["understand", "appreciate", "tell me", "share", "family", "background"]):
                rapport_indicators += 1
        
        scores[TrainingMetric.RAPPORT_BUILDING.value] = min(90, 30 + (rapport_indicators / max(total_exchanges, 1)) * 60)
        
        # Objection Handling Analysis
        objection_indicators = 0
        objection_responses = 0
        for i, persona_resp in enumerate(persona_responses):
            # Check if persona raised objections
            if any(word in persona_resp.lower() for word in ["but", "however", "concerned", "worried", "expensive", "not sure"]):
                objection_indicators += 1
                # Check if user handled it well in next response
                if i + 1 < len(user_responses):
                    user_next = user_responses[i + 1].lower()
                    if any(word in user_next for word in ["understand", "appreciate", "let me", "what if", "consider"]):
                        objection_responses += 1
        
        if objection_indicators > 0:
            scores[TrainingMetric.OBJECTION_HANDLING.value] = 20 + (objection_responses / objection_indicators) * 70
        
        # Closing Techniques Analysis
        closing_attempts = 0
        for response in user_responses:
            response_lower = response.lower()
            if any(phrase in response_lower for phrase in ["ready to", "would you like", "shall we", "can we", "let's get", "sign up"]):
                closing_attempts += 1
        
        scores[TrainingMetric.CLOSING_TECHNIQUES.value] = min(85, 20 + closing_attempts * 20 + success_rating * 10)
        
        # Product Knowledge Analysis
        knowledge_indicators = 0
        for response in user_responses:
            response_lower = response.lower()
            if any(word in response_lower for word in ["feature", "benefit", "include", "program", "equipment", "trainer", "membership"]):
                knowledge_indicators += 1
        
        scores[TrainingMetric.PRODUCT_KNOWLEDGE.value] = min(85, 25 + (knowledge_indicators / max(total_exchanges, 1)) * 60)
        
        # Listening Skills Analysis
        listening_indicators = 0
        for i, user_resp in enumerate(user_responses):
            if i > 0:  # Skip first response
                prev_persona = persona_responses[i-1].lower()
                user_resp_lower = user_resp.lower()
                # Check if user response references what persona said
                if any(word in user_resp_lower for word in ["you mentioned", "you said", "based on", "since you"]):
                    listening_indicators += 1
        
        scores[TrainingMetric.LISTENING_SKILLS.value] = min(90, 30 + (listening_indicators / max(total_exchanges-1, 1)) * 60)
        
        # Persuasion Skills Analysis
        persuasion_indicators = 0
        for response in user_responses:
            response_lower = response.lower()
            if any(phrase in response_lower for phrase in ["imagine", "picture", "think about", "benefit", "help you", "achieve"]):
                persuasion_indicators += 1
        
        scores[TrainingMetric.PERSUASION_SKILLS.value] = min(85, 25 + (persuasion_indicators / max(total_exchanges, 1)) * 60)
        
        # Time Management Analysis (based on session duration and efficiency)
        duration_minutes = (session_data.get("end_time", time.time()) - session_data.get("start_time", time.time())) / 60
        ideal_duration = 15  # Assume 15 minutes is ideal
        
        if duration_minutes <= ideal_duration * 1.2:  # Within 20% of ideal
            time_score = 80 + success_rating * 2
        elif duration_minutes <= ideal_duration * 1.5:  # Within 50% of ideal
            time_score = 60 + success_rating * 2
        else:
            time_score = 40 + success_rating * 2
        
        scores[TrainingMetric.TIME_MANAGEMENT.value] = min(90, time_score)
        
        return scores
    
    def _update_skill_assessments(self, user_id: str, performance_scores: Dict[str, float]):
        """Update skill assessments based on recent performance"""
        current_assessments = self.skill_assessments[user_id]
        
        for skill_name, score in performance_scores.items():
            skill = TrainingMetric(skill_name)
            assessment = current_assessments[skill]
            
            # Add score to recent scores
            assessment.recent_scores.append(score)
            if len(assessment.recent_scores) > 10:  # Keep only last 10 scores
                assessment.recent_scores = assessment.recent_scores[-10:]
            
            # Calculate improvement trend
            if len(assessment.recent_scores) >= 3:
                recent_avg = sum(assessment.recent_scores[-3:]) / 3
                older_avg = sum(assessment.recent_scores[-6:-3]) / 3 if len(assessment.recent_scores) >= 6 else recent_avg
                
                if recent_avg > older_avg + 5:
                    assessment.improvement_trend = "improving"
                elif recent_avg < older_avg - 5:
                    assessment.improvement_trend = "declining"
                else:
                    assessment.improvement_trend = "stable"
            
            # Update current level based on average recent performance
            avg_score = sum(assessment.recent_scores) / len(assessment.recent_scores)
            new_level = self._calculate_skill_level(skill, avg_score)
            
            if new_level != assessment.current_level:
                logger.info(f"User {user_id} skill level updated: {skill.value} from {assessment.current_level.value} to {new_level.value}")
                assessment.current_level = new_level
            
            # Update progress percentage
            current_benchmark = self.skill_benchmarks[skill][assessment.current_level]["min_score"]
            target_benchmark = self.skill_benchmarks[skill][assessment.target_level]["min_score"]
            
            if target_benchmark > current_benchmark:
                progress = ((avg_score - current_benchmark) / (target_benchmark - current_benchmark)) * 100
                assessment.progress_percentage = max(0, min(100, progress))
            else:
                assessment.progress_percentage = 100
            
            assessment.last_updated = time.time()
    
    def _calculate_skill_level(self, skill: TrainingMetric, average_score: float) -> SkillLevel:
        """Calculate skill level based on average score"""
        benchmarks = self.skill_benchmarks[skill]
        
        for level in reversed(list(SkillLevel)):  # Start from expert level
            if average_score >= benchmarks[level]["min_score"]:
                return level
        
        return SkillLevel.NOVICE
    
    def _update_performance_trends(self, user_id: str, session_summary: Dict[str, Any]):
        """Update performance trends for analytics"""
        if user_id not in self.performance_trends:
            self.performance_trends[user_id] = {
                "weekly_sessions": [],
                "skill_progression": {skill.value: [] for skill in TrainingMetric},
                "success_rate_trend": [],
                "engagement_trend": []
            }
        
        trends = self.performance_trends[user_id]
        current_time = time.time()
        
        # Weekly session tracking
        trends["weekly_sessions"].append({
            "date": current_time,
            "session_count": 1,
            "total_duration": session_summary["duration_minutes"]
        })
        
        # Skill progression tracking
        for skill_name, score in session_summary["performance_scores"].items():
            trends["skill_progression"][skill_name].append({
                "date": current_time,
                "score": score
            })
        
        # Success rate trend
        trends["success_rate_trend"].append({
            "date": current_time,
            "success_rating": session_summary.get("success_rating", 0)
        })
        
        # Clean old data (keep only last 30 days)
        cutoff_date = current_time - (30 * 24 * 3600)
        for trend_key in trends:
            if isinstance(trends[trend_key], list):
                trends[trend_key] = [item for item in trends[trend_key] if item.get("date", 0) > cutoff_date]
            elif isinstance(trends[trend_key], dict):
                for sub_key in trends[trend_key]:
                    trends[trend_key][sub_key] = [item for item in trends[trend_key][sub_key] if item.get("date", 0) > cutoff_date]
    
    def _check_achievements(self, user_id: str, session_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for new achievements and milestones"""
        achievements = []
        profile = self.user_profiles[user_id]
        
        # Session count milestones
        session_milestones = [1, 5, 10, 25, 50, 100]
        total_sessions = profile["total_sessions"]
        
        if total_sessions in session_milestones:
            achievements.append({
                "type": "milestone",
                "title": f"{total_sessions} Training Sessions",
                "description": f"Completed {total_sessions} training sessions",
                "badge": f"sessions_{total_sessions}",
                "date": time.time()
            })
        
        # Skill level achievements
        skill_assessments = self.skill_assessments[user_id]
        for skill, assessment in skill_assessments.items():
            if assessment.current_level in [SkillLevel.INTERMEDIATE, SkillLevel.ADVANCED, SkillLevel.EXPERT]:
                # Check if this is a new level (would need to store previous state)
                achievements.append({
                    "type": "skill_advancement",
                    "title": f"{skill.value.replace('_', ' ').title()} {assessment.current_level.value.title()}",
                    "description": f"Achieved {assessment.current_level.value} level in {skill.value.replace('_', ' ')}",
                    "badge": f"{skill.value}_{assessment.current_level.value}",
                    "date": time.time()
                })
        
        # Success rate achievements
        recent_sessions = self.session_history[user_id][-5:] if len(self.session_history[user_id]) >= 5 else []
        if recent_sessions:
            avg_success = sum(s.get("success_rating", 0) for s in recent_sessions) / len(recent_sessions)
            if avg_success >= 8:
                achievements.append({
                    "type": "performance",
                    "title": "High Performer",
                    "description": "Maintained high success rate over recent sessions",
                    "badge": "high_performer",
                    "date": time.time()
                })
        
        return achievements
    
    def _get_skill_updates(self, user_id: str) -> Dict[str, Any]:
        """Get recent skill level updates"""
        skill_assessments = self.skill_assessments[user_id]
        
        updates = {}
        for skill, assessment in skill_assessments.items():
            updates[skill.value] = {
                "current_level": assessment.current_level.value,
                "progress_percentage": assessment.progress_percentage,
                "improvement_trend": assessment.improvement_trend,
                "recent_average": sum(assessment.recent_scores) / len(assessment.recent_scores) if assessment.recent_scores else 0
            }
        
        return updates
    
    def _generate_next_steps(self, user_id: str) -> List[str]:
        """Generate personalized next steps and recommendations"""
        skill_assessments = self.skill_assessments[user_id]
        profile = self.user_profiles[user_id]
        
        recommendations = []
        
        # Find weakest skills
        skill_scores = {}
        for skill, assessment in skill_assessments.items():
            avg_score = sum(assessment.recent_scores) / len(assessment.recent_scores) if assessment.recent_scores else 0
            skill_scores[skill] = avg_score
        
        # Sort skills by score (weakest first)
        weakest_skills = sorted(skill_scores.items(), key=lambda x: x[1])[:3]
        
        for skill, score in weakest_skills:
            skill_name = skill.value.replace('_', ' ').title()
            if score < 50:
                recommendations.append(f"Focus on improving {skill_name} - consider additional practice scenarios")
            elif score < 70:
                recommendations.append(f"Continue developing {skill_name} skills with challenging personas")
        
        # Experience-based recommendations
        if profile["total_sessions"] < 5:
            recommendations.append("Complete more training sessions to build consistency")
        elif profile["total_sessions"] < 20:
            recommendations.append("Try training with different persona types to broaden your skills")
        else:
            recommendations.append("Consider practicing with expert-level personas for advanced challenges")
        
        return recommendations[:5]  # Return top 5 recommendations
    
    def create_learning_goal(self, user_id: str, goal_data: Dict[str, Any]) -> str:
        """Create a new learning goal for the user"""
        if user_id not in self.user_profiles:
            self.initialize_user_profile(user_id)
        
        goal_id = f"{user_id}_{int(time.time())}"
        
        goal = LearningGoal(
            goal_id=goal_id,
            title=goal_data["title"],
            description=goal_data.get("description", ""),
            target_skill=TrainingMetric(goal_data["target_skill"]),
            target_level=SkillLevel(goal_data["target_level"]),
            target_date=goal_data.get("target_date", time.time() + (30 * 24 * 3600)),  # Default 30 days
            current_progress=0.0,
            milestones=goal_data.get("milestones", []),
            is_completed=False,
            created_date=time.time()
        )
        
        self.learning_goals[user_id].append(goal)
        logger.info(f"Created learning goal {goal_id} for user {user_id}")
        
        return goal_id
    
    def get_user_progress_dashboard(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive progress dashboard for user"""
        if user_id not in self.user_profiles:
            # If user not found, initialize with empty profile
            self.initialize_user_profile(user_id)
        
        profile = self.user_profiles[user_id]
        skill_assessments = self.skill_assessments[user_id]
        recent_sessions = self.session_history[user_id][-10:] if self.session_history[user_id] else []
        
        # Calculate overall progress
        total_progress = sum(assessment.progress_percentage for assessment in skill_assessments.values()) / len(skill_assessments)
        
        # Get skill breakdown
        skills_breakdown = {}
        for skill, assessment in skill_assessments.items():
            skills_breakdown[skill.value] = {
                "current_level": assessment.current_level.value,
                "target_level": assessment.target_level.value,
                "progress_percentage": assessment.progress_percentage,
                "recent_average": sum(assessment.recent_scores) / len(assessment.recent_scores) if assessment.recent_scores else 0,
                "trend": assessment.improvement_trend,
                "benchmark_description": self.skill_benchmarks[skill][assessment.current_level]["description"]
            }
        
        # Calculate session statistics
        session_stats = {
            "total_sessions": len(self.session_history[user_id]),
            "total_hours": profile["total_training_hours"],
            "average_session_length": profile["total_training_hours"] / max(profile["total_sessions"], 1) * 60,
            "sessions_this_week": len([s for s in recent_sessions if s["start_time"] > time.time() - 7*24*3600]),
            "average_success_rating": sum(s.get("success_rating", 0) for s in recent_sessions) / max(len(recent_sessions), 1)
        }
        
        # Get active learning goals
        active_goals = [goal.to_dict() for goal in self.learning_goals[user_id] if not goal.is_completed]
        
        dashboard = {
            "user_profile": {
                "user_id": user_id,
                "experience_level": profile["experience_level"],
                "current_tier": profile["current_tier"],
                "member_since": profile["created_date"],
                "last_active": profile["last_active"]
            },
            "overall_progress": {
                "completion_percentage": total_progress,
                "skills_mastered": sum(1 for a in skill_assessments.values() if a.current_level in [SkillLevel.ADVANCED, SkillLevel.EXPERT]),
                "skills_in_progress": sum(1 for a in skill_assessments.values() if a.current_level in [SkillLevel.BEGINNER, SkillLevel.INTERMEDIATE]),
                "improvement_trend": self._calculate_overall_trend(user_id)
            },
            "skills_breakdown": skills_breakdown,
            "session_statistics": session_stats,
            "recent_performance": [
                {
                    "session_id": s["session_id"],
                    "persona": s["persona_name"],
                    "date": s["start_time"],
                    "success_rating": s.get("success_rating", 0),
                    "duration": s["duration_minutes"]
                }
                for s in recent_sessions[-5:]
            ],
            "active_goals": active_goals,
            "next_recommendations": self._generate_next_steps(user_id),
            "achievements_summary": {
                "total_badges": len(profile.get("certifications", [])),
                "recent_achievements": []  # Would be populated from achievement system
            }
        }
        
        return dashboard
    
    def _calculate_overall_trend(self, user_id: str) -> str:
        """Calculate overall improvement trend across all skills"""
        skill_assessments = self.skill_assessments[user_id]
        
        trends = [assessment.improvement_trend for assessment in skill_assessments.values()]
        improving_count = trends.count("improving")
        declining_count = trends.count("declining")
        
        if improving_count > declining_count:
            return "improving"
        elif declining_count > improving_count:
            return "declining"
        else:
            return "stable"
    
    def get_leaderboard(self, timeframe: str = "all_time", skill: str = None) -> List[Dict[str, Any]]:
        """Get leaderboard for user rankings"""
        # This would typically query a database in production
        # For now, return a simplified version based on current data
        
        user_rankings = []
        
        for user_id, profile in self.user_profiles.items():
            skill_assessments = self.skill_assessments[user_id]
            
            if skill and skill in [s.value for s in TrainingMetric]:
                # Specific skill leaderboard
                target_skill = TrainingMetric(skill)
                assessment = skill_assessments[target_skill]
                score = sum(assessment.recent_scores) / len(assessment.recent_scores) if assessment.recent_scores else 0
            else:
                # Overall leaderboard
                scores = []
                for assessment in skill_assessments.values():
                    if assessment.recent_scores:
                        scores.append(sum(assessment.recent_scores) / len(assessment.recent_scores))
                score = sum(scores) / len(scores) if scores else 0
            
            user_rankings.append({
                "user_id": user_id,
                "score": score,
                "total_sessions": profile["total_sessions"],
                "total_hours": profile["total_training_hours"],
                "rank": 0  # Will be calculated after sorting
            })
        
        # Sort by score descending
        user_rankings.sort(key=lambda x: x["score"], reverse=True)
        
        # Assign ranks
        for i, user in enumerate(user_rankings):
            user["rank"] = i + 1
        
        return user_rankings[:20]  # Top 20
    
    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Export all user data for analysis or backup"""
        if user_id not in self.user_profiles:
            # If user not found, create a new profile
            self.initialize_user_profile(user_id)
        
        return {
            "profile": self.user_profiles[user_id],
            "skill_assessments": {skill.value: assessment.to_dict() for skill, assessment in self.skill_assessments[user_id].items()},
            "session_history": self.session_history[user_id],
            "learning_goals": [goal.to_dict() for goal in self.learning_goals[user_id]],
            "performance_trends": self.performance_trends.get(user_id, {}),
            "export_date": time.time()
        }

# Global progress tracking service instance
progress_service = ProgressTrackingService()