"""
Persona Management Service for AI Sales Training System
Handles persona creation, management, and response generation
"""
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from config.settings import MAX_CONTEXT_LENGTH
from . import persona_db_service

logger = logging.getLogger(__name__)

class PersonaType(Enum):
    """Types of training personas"""
    BEGINNER = "beginner"
    EXPERIENCED = "experienced"
    SKEPTICAL = "skeptical"
    BUDGET_CONSCIOUS = "budget_conscious"
    HEALTH_FOCUSED = "health_focused"
    TIME_CONSTRAINED = "time_constrained"

class DifficultyLevel(Enum):
    """Difficulty levels for training scenarios"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"

@dataclass
class Persona:
    """Training persona definition"""
    name: str
    age: int
    background: str
    personality_traits: List[str]
    goals: List[str]
    concerns: List[str]
    objections: List[str]
    budget_range: str
    decision_style: str
    expertise_level: str
    persona_type: PersonaType
    difficulty: DifficultyLevel
    health_considerations: List[str] = None
    time_constraints: List[str] = None
    preferred_communication: str = "friendly"
    industry: str = "fitness" 
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert persona to dictionary"""
        data = asdict(self)
        data['persona_type'] = self.persona_type.value
        data['difficulty'] = self.difficulty.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Persona":
        """Create a Persona object from a dictionary."""
        return cls(
            name=data["name"],
            age=data.get("age"),
            background=data.get("background"),
            personality_traits=data.get("personality_traits", []),
            goals=data.get("goals", []),
            concerns=data.get("concerns", []),
            objections=data.get("objections", []),
            budget_range=data.get("budget_range"),
            decision_style=data.get("decision_style"),
            expertise_level=data.get("expertise_level"),
            persona_type=PersonaType(data.get("persona_type")),
            difficulty=DifficultyLevel(data.get("difficulty")),
            health_considerations=data.get("health_considerations"),
            time_constraints=data.get("time_constraints"),
            preferred_communication=data.get("preferred_communication"),
            industry=data.get("industry"),
        )

class PersonaService:
    """Service for managing training personas and generating responses"""
    
    def __init__(self):
        self.personas: Dict[str, Persona] = {}
        self.active_sessions: Dict[str, Dict] = {}
        self.persona_performance: Dict[str, Dict] = {}
        persona_db_service.init_db()
        self._load_personas_from_db()
    
    def _load_personas_from_db(self):
        """Load personas from the database."""
        personas_data = persona_db_service.get_personas()
        for p_data in personas_data:
            try:
                persona = Persona.from_dict(p_data)
                self.personas[persona.name.lower()] = persona
                self.persona_performance[persona.name.lower()] = {
                    "total_sessions": 0,
                    "average_session_length": 0,
                    "successful_closes": 0,
                    "common_objections": [],
                    "trainer_feedback": []
                }
            except Exception as e:
                logger.warning(f"Skipping invalid persona from DB: {e}")
        logger.info(f"Loaded {len(self.personas)} personas from database.")

    def get_persona(self, persona_name: str) -> Optional[Persona]:
        """Get persona by name"""
        return self.personas.get(persona_name.lower())

    def add_or_update_persona(self, persona: Persona) -> None:
        """Add or update a persona and persist to the database."""
        key = persona.name.lower()
        self.personas[key] = persona
        persona_db_service.add_persona(persona.to_dict())
        self.persona_performance.setdefault(key, {
            "total_sessions": 0,
            "average_session_length": 0,
            "successful_closes": 0,
            "common_objections": [],
            "trainer_feedback": []
        })
    
    def list_personas(self) -> List[Dict[str, Any]]:
        """List all available personas"""
        return [
            {
                "name": persona.name,
                "type": persona.persona_type.value,
                "difficulty": persona.difficulty.value,
                "background": persona.background,
                "age": persona.age,
                "industry": getattr(persona, "industry", "fitness"),
            }
            for persona in self.personas.values()
        ]
    
    def get_personas_by_difficulty(self, difficulty: DifficultyLevel) -> List[Persona]:
        """Get personas filtered by difficulty level"""
        return [p for p in self.personas.values() if p.difficulty == difficulty]
    
    def get_personas_by_type(self, persona_type: PersonaType) -> List[Persona]:
        """Get personas filtered by type"""
        return [p for p in self.personas.values() if p.persona_type == persona_type]
    
    def start_training_session(self, user_id: str, persona_name: str, scenario: str = "initial_contact") -> Dict[str, Any]:
        """Start a training session with specified persona"""
        persona = self.get_persona(persona_name)
        if not persona:
            raise ValueError(f"Persona '{persona_name}' not found")
        
        session_id = f"{user_id}_{persona_name}_{int(time.time())}"
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "persona": persona.to_dict(),
            "scenario": scenario,
            "start_time": time.time(),
            "conversation_history": [],
            "performance_metrics": {
                "response_times": [],
                "objections_handled": [],
                "engagement_score": 0,
                "closing_attempts": 0,
                "success_indicators": []
            },
            "current_state": "active"
        }
        
        self.active_sessions[session_id] = session_data
        self.persona_performance[persona_name.lower()]["total_sessions"] += 1
        
        logger.info(f"Started training session {session_id} with persona {persona_name}")
        return session_data
    
    def generate_persona_response(self, session_id: str, user_message: str, pipe) -> Dict[str, Any]:
        """Generate response from persona based on their characteristics"""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.active_sessions[session_id]
        persona_data = session["persona"]
        
        prompt = self._build_persona_prompt(persona_data, user_message, session["conversation_history"])
        
        try:
            from fallback_responses import generate_ai_response
            response = generate_ai_response(prompt, pipe)
            
            if not response:
                response = self._get_fallback_response(persona_data, user_message)
            
            self._update_session_data(session_id, user_message, response)
            
            analysis = self._analyze_interaction(user_message, response, persona_data)
            
            return {
                "response": response,
                "persona_name": persona_data["name"],
                "analysis": analysis,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error generating persona response: {e}")
            return {
                "response": self._get_emergency_response(persona_data),
                "persona_name": persona_data["name"],
                "analysis": {"error": str(e)},
                "session_id": session_id
            }
    
    def _build_persona_prompt(self, persona_data: Dict, user_message: str, history: List[Dict]) -> str:
        """Build AI prompt based on persona characteristics"""
        context = ""
        if history:
            recent_history = history[-3:]
            for exchange in recent_history:
                context += f"Salesperson: {exchange['user_message']}\n{persona_data['name']}: {exchange['persona_response']}\n\n"
        
        prompt = f"""You are {persona_data['name']}, a {persona_data['age']}-year-old potential fitness customer.

CHARACTER PROFILE:
- Background: {persona_data['background']}
- Personality: {', '.join(persona_data['personality_traits'])}
- Goals: {', '.join(persona_data['goals'])}
- Main Concerns: {', '.join(persona_data['concerns'])}
- Budget Range: {persona_data['budget_range']}
- Decision Style: {persona_data['decision_style']}
- Expertise Level: {persona_data['expertise_level']}

TRAINING SCENARIO:
You are being approached by a fitness salesperson for {persona_data['persona_type']} training.
Difficulty Level: {persona_data['difficulty']}

BEHAVIORAL GUIDELINES:
- Respond naturally as {persona_data['name']} would
- Show personality traits: {', '.join(persona_data['personality_traits'])}
- Express concerns: {', '.join(persona_data['concerns'])}
- Use objections when appropriate: {', '.join(persona_data['objections'])}
- Communication style: {persona_data['preferred_communication']}
- Consider your budget: {persona_data['budget_range']}

CRITICAL PERSONALITY RULES:
- You are CAUTIOUS and UNCERTAIN about fitness - NOT confident or experienced
- You have real CONCERNS and FEARS about starting exercise (express these!)
- You're seeking HELP because you DON'T know what to do - you're not an expert
- When asked about past exercise, be HONEST about your gaps and worries
- NEVER say "I understand the benefits" - say "I've heard about benefits but I'm worried..."
- DO NOT include any labels like "{persona_data['name']}:" in your response - just speak naturally

{context}Salesperson: {user_message}

Now respond as {persona_data['name']} (speak naturally, no labels):"""
        
        return prompt
    
    def _get_fallback_response(self, persona_data: Dict, user_message: str) -> str:
        """Generate fallback response when AI fails"""
        responses = {
            "beginner": [
                "I'm new to this, so I need to understand the basics first.",
                "That sounds interesting, but I'm worried about getting started.",
                "Can you explain that in simpler terms?",
            ],
            "skeptical": [
                "I've heard that before from other gyms. How is this different?",
                "That sounds too good to be true. Do you have proof?",
                "I need to see concrete evidence before making any decisions.",
            ],
            "budget_conscious": [
                "That might be out of my budget range. Do you have cheaper options?",
                "I'm on a tight budget. What's the most affordable plan?",
                "Cost is a major factor for me. Can we discuss pricing?",
            ],
            "time_constrained": [
                "I have very limited time. How long would this take?",
                "My schedule is crazy. Do you have flexible options?",
                "Time is my biggest constraint. Can this work with a busy schedule?",
            ],
        }

        persona_type = persona_data.get("persona_type", "beginner")
        fallback_list = responses.get(persona_type, responses["beginner"])

        import random
        return random.choice(fallback_list)

    def _get_emergency_response(self, persona_data: Dict) -> str:
        """Emergency response when all else fails"""
        return f"I need a moment to think about that. Could you tell me more about what you're offering?"
    
    def _update_session_data(self, session_id: str, user_message: str, persona_response: str):
        """Update session with new interaction"""
        session = self.active_sessions[session_id]
        
        interaction = {
            "timestamp": time.time(),
            "user_message": user_message,
            "persona_response": persona_response
        }
        
        session["conversation_history"].append(interaction)
        
        if len(session["conversation_history"]) > MAX_CONTEXT_LENGTH:
            session["conversation_history"] = session["conversation_history"][-MAX_CONTEXT_LENGTH:]
    
    def _analyze_interaction(self, user_message: str, persona_response: str, persona_data: Dict) -> Dict[str, Any]:
        """Analyze interaction for training feedback"""
        analysis = {
            "interaction_type": "unknown",
            "engagement_level": "medium",
            "objections_raised": [],
            "closing_opportunity": False,
            "suggested_improvements": []
        }
        
        user_lower = user_message.lower()
        response_lower = persona_response.lower()
        
        if any(word in user_lower for word in ["price", "cost", "budget", "expensive"]):
            analysis["interaction_type"] = "pricing_discussion"
        elif any(word in user_lower for word in ["benefit", "feature", "include", "offer"]):
            analysis["interaction_type"] = "feature_presentation"
        elif any(word in user_lower for word in ["sign", "join", "start", "decide"]):
            analysis["interaction_type"] = "closing_attempt"
        elif any(word in user_lower for word in ["hello", "hi", "introduce", "tell me"]):
            analysis["interaction_type"] = "initial_contact"
        
        objection_keywords = persona_data.get('objections', [])
        for objection in objection_keywords:
            if any(word in response_lower for word in objection.lower().split()):
                analysis["objections_raised"].append(objection)
        
        if len(persona_response) > 100 or any(word in response_lower for word in ["great", "excellent", "love", "perfect"]):
            analysis["engagement_level"] = "high"
        elif len(persona_response) < 30 or any(word in response_lower for word in ["no", "not", "can't", "won't"]):
            analysis["engagement_level"] = "low"
        
        if any(phrase in response_lower for phrase in ["sounds good", "interested", "when can", "how do i"]):
            analysis["closing_opportunity"] = True
        
        return analysis
    
    def get_session_analytics(self, session_id: str) -> Dict[str, Any]:
        """Get detailed analytics for a training session"""
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
        
        session = self.active_sessions[session_id]
        history = session["conversation_history"]
        
        analytics = {
            "session_summary": {
                "session_id": session_id,
                "persona": session["persona"]["name"],
                "duration_minutes": (time.time() - session["start_time"]) / 60,
                "total_exchanges": len(history),
                "current_state": session["current_state"]
            },
            "performance_metrics": {
                "average_response_time": sum(session["performance_metrics"]["response_times"]) / max(len(session["performance_metrics"]["response_times"]), 1),
                "objections_encountered": len(session["performance_metrics"]["objections_handled"]),
                "engagement_score": session["performance_metrics"]["engagement_score"],
                "closing_attempts": session["performance_metrics"]["closing_attempts"]
            },
            "conversation_analysis": self._analyze_conversation_flow(history),
            "recommendations": self._generate_training_recommendations(history)
        }
        
        return analytics
    
    def _analyze_conversation_flow(self, history: List[Dict]) -> Dict[str, Any]:
        """Analyze the flow and quality of the conversation"""
        if not history:
            return {"error": "No conversation history"}
        
        analysis = {
            "conversation_stages": [],
            "objection_patterns": [],
            "engagement_trajectory": [],
            "missed_opportunities": []
        }
        
        for i, exchange in enumerate(history):
            user_msg = exchange["user_message"].lower()
            persona_resp = exchange["persona_response"].lower()
            
            stage = "discovery"
            if any(word in user_msg for word in ["hello", "hi", "introduce"]):
                stage = "opening"
            elif any(word in user_msg for word in ["price", "cost", "budget"]):
                stage = "pricing"
            elif any(word in user_msg for word in ["benefit", "feature", "include"]):
                stage = "presentation"
            elif any(word in user_msg for word in ["sign", "join", "decide"]):
                stage = "closing"
            
            analysis["conversation_stages"].append({
                "exchange": i + 1,
                "stage": stage,
                "timestamp": exchange.get("timestamp", 0)
            })
            
            engagement = "medium"
            if len(persona_resp) > 100:
                engagement = "high"
            elif len(persona_resp) < 30:
                engagement = "low"
            
            analysis["engagement_trajectory"].append({
                "exchange": i + 1,
                "engagement": engagement
            })
        
        return analysis
    
    def _generate_training_recommendations(self, session: Dict) -> List[str]:
        """Generate training recommendations based on session performance"""
        recommendations = []
        history = session["conversation_history"]
        persona_data = session["persona"]
        
        if len(history) < 3:
            recommendations.append("Try to engage in longer conversations to build rapport")
        
        if persona_data["persona_type"] == "skeptical":
            recommendations.append("For skeptical personas, provide more data and proof points")
        elif persona_data["persona_type"] == "budget_conscious":
            recommendations.append("Address budget concerns early and offer value-focused solutions")
        elif persona_data["persona_type"] == "time_constrained":
            recommendations.append("Emphasize efficiency and time-saving benefits")
        
        if session["performance_metrics"]["objections_handled"]:
            recommendations.append("Good job handling objections - practice different objection responses")
        else:
            recommendations.append("This persona typically raises objections - be prepared to address concerns")
        
        return recommendations
    
    def end_training_session(self, session_id: str, success_rating: int = None) -> Dict[str, Any]:
        """End a training session and generate final report"""
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
        
        session = self.active_sessions[session_id]
        session["current_state"] = "completed"
        session["end_time"] = time.time()
        
        if success_rating:
            session["success_rating"] = success_rating
        
        final_report = self.get_session_analytics(session_id)
        
        persona_name = session["persona"]["name"].lower()
        if persona_name in self.persona_performance:
            perf = self.persona_performance[persona_name]
            duration = (session["end_time"] - session["start_time"]) / 60
            
            total_sessions = perf["total_sessions"]
            perf["average_session_length"] = ((perf["average_session_length"] * (total_sessions - 1)) + duration) / total_sessions
            
            if success_rating and success_rating >= 4:
                perf["successful_closes"] += 1
        
        archived_session = self.active_sessions.pop(session_id)
        
        logger.info(f"Training session {session_id} completed")
        return {
            "session_completed": True,
            "final_report": final_report,
            "session_summary": archived_session
        }
    
    def get_persona_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics across all personas"""
        return {
            "total_active_sessions": len(self.active_sessions),
            "persona_stats": self.persona_performance,
            "overall_metrics": {
                "total_sessions_all_time": sum(p["total_sessions"] for p in self.persona_performance.values()),
                "success_rate": sum(p["successful_closes"] for p in self.persona_performance.values()) / max(sum(p["total_sessions"] for p in self.persona_performance.values()), 1) * 100
            }
        }

persona_service = PersonaService()
