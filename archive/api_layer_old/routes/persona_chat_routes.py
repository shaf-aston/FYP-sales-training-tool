"""
Enhanced persona-specific chat routes with JSON context differentiation
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging

# Import persona profiles and services
from services.persona_service import persona_service
from services.chat_service import chat_service

logger = logging.getLogger(__name__)

# Create persona-specific router
persona_chat_router = APIRouter(prefix="/api/v2/personas", tags=["Persona Chat"])

class PersonaChatRequest(BaseModel):
    persona_name: str
    user_message: str
    session_id: Optional[str] = None
    context_override: Optional[Dict[str, Any]] = None

class PersonaContextRequest(BaseModel):
    persona_name: str

@persona_chat_router.get("/{persona_name}/context")
async def get_persona_context(persona_name: str) -> Dict[str, Any]:
    """Get specific JSON context for a persona"""
    try:
        p = persona_service.get_persona(persona_name)
        if not p:
            raise HTTPException(status_code=404, detail=f"Persona '{persona_name}' not found")
        
        persona = {
            "name": p.name,
            "age": p.age,
            "description": p.background,
            "goals": p.goals,
            "personality_traits": getattr(p, "personality_traits", []),
            "communication_style": getattr(p, "preferred_communication", "friendly"),
            "pain_points": getattr(p, "concerns", []),
        }
        
        # Create persona-specific context
        context = {
            "persona_info": persona,
            "conversation_style": {
                "tone": persona.get("communication_style", "friendly"),
                "personality_traits": persona.get("personality_traits", []),
                "main_concerns": persona.get("pain_points", []),
                "goals": persona.get("goals", [])
            },
            "scenario_context": {
                "setting": "fitness consultation" if persona_name.lower() == "mary" else "sales meeting",
                "relationship": "potential client",
                "decision_factors": persona.get("pain_points", []),
                "success_metrics": persona.get("goals", [])
            },
            "response_guidelines": {
                "should_express": {
                    "Mary": [
                        "Safety concerns about new exercises",
                        "Interest in gentle, age-appropriate workouts",
                        "Questions about injury prevention",
                        "Desire for clear, simple instructions"
                    ],
                    "Jake": [
                        "Skepticism about time investment",
                        "Need for proven results and data",
                        "Concerns about efficiency",
                        "Business-focused decision making"
                    ],
                    "Sarah": [
                        "Budget constraints and cost concerns",
                        "Value-for-money questions",
                        "Comparison shopping behavior",
                        "Student lifestyle considerations"
                    ],
                    "David": [
                        "Family scheduling conflicts",
                        "Work-life balance concerns",
                        "Setting good example for children",
                        "Practical family solutions"
                    ]
                }.get(persona_name, []),
                "communication_patterns": {
                    "Mary": "Polite, cautious, asks detailed questions about safety",
                    "Jake": "Direct, analytical, wants concrete data and quick results",
                    "Sarah": "Friendly but cost-focused, researches options thoroughly",
                    "David": "Warm, family-oriented, practical and responsibility-focused"
                }.get(persona_name, "Neutral and friendly"),
                "likely_objections": {
                    "Mary": [
                        "Is this safe for someone my age?",
                        "What if I get injured?",
                        "I've never done this type of exercise before",
                        "Will this be too difficult for me?"
                    ],
                    "Jake": [
                        "I don't have time for long workouts",
                        "How do I know this will actually work?",
                        "What's the ROI on this investment?",
                        "I'm too busy for complicated routines"
                    ],
                    "Sarah": [
                        "This seems expensive for my budget",
                        "Are there any hidden fees?",
                        "Can I get a better deal elsewhere?",
                        "What if I can't afford to continue?"
                    ],
                    "David": [
                        "When will I find time with my family schedule?",
                        "Will this take away from time with my kids?",
                        "Is this something my family can do together?",
                        "What about my work commitments?"
                    ]
                }.get(persona_name, [])
            }
        }
        
        return {
            "success": True,
            "persona_name": persona_name,
            "context": context
        }
        
    except Exception as e:
        logger.error(f"Error getting persona context for {persona_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve persona context")

@persona_chat_router.post("/{persona_name}/chat")
async def chat_with_specific_persona(
    persona_name: str, 
    request: PersonaChatRequest
) -> Dict[str, Any]:
    """Enhanced chat endpoint with persona-specific context and behavior"""
    try:
        p = persona_service.get_persona(persona_name)
        if not p:
            raise HTTPException(status_code=404, detail=f"Persona '{persona_name}' not found")
        
        # Get persona context
        context_response = await get_persona_context(persona_name)
        persona_context = context_response["context"]
        
        # Override with any provided context
        if request.context_override:
            persona_context.update(request.context_override)
        
        # Get AI model pipeline
        from services.model_service import model_service
        pipe = model_service.get_pipeline()
        
        if not pipe:
            raise HTTPException(status_code=503, detail="AI model not available")
        
        # Create enhanced prompt with persona context
        enhanced_prompt = create_persona_prompt(
            persona_name=persona_name,
            persona_context=persona_context,
            user_message=request.user_message
        )
        
        # Generate response using chat service
        response_data = chat_service.chat_with_persona(
            message=request.user_message,
            user_id="api_user",
            persona_name=persona_name,
            pipe=pipe,
            session_id=request.session_id
        )
        
        # Post-process response to match persona
        persona_response = post_process_persona_response(
            response=response_data["response"],
            persona_name=persona_name,
            persona_context=persona_context
        )
        
        return {
            "success": True,
            "persona_name": persona_name,
            "persona_response": persona_response,
            "context_used": persona_context["conversation_style"],
            "response_metadata": {
                "processing_time": response_data.get("processing_time", 0),
                "confidence": response_data.get("confidence", 0.8),
                "persona_consistency": calculate_persona_consistency(persona_response, persona_context)
            },
            "training_analysis": {
                "user_approach": analyze_user_approach(request.user_message, persona_context),
                "persona_reaction": analyze_persona_reaction(persona_response, persona_context),
                "suggestions": generate_improvement_suggestions(
                    request.user_message, 
                    persona_response, 
                    persona_context
                )
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in persona chat for {persona_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate persona response")

def create_persona_prompt(persona_name: str, persona_context: Dict[str, Any], user_message: str) -> str:
    """Create an enhanced prompt with persona-specific context"""
    persona_info = persona_context["persona_info"]
    style = persona_context["conversation_style"]
    scenario = persona_context["scenario_context"]
    guidelines = persona_context["response_guidelines"]
    
    prompt = f"""You are {persona_name}, a {persona_info.get('age', 'adult')}-year-old {persona_info.get('description', 'person')}.

PERSONA BACKGROUND:
{persona_info.get('background', 'Generic background')}

PERSONALITY TRAITS: {', '.join(style['personality_traits'])}
COMMUNICATION STYLE: {style['tone']}
MAIN CONCERNS: {', '.join(style['main_concerns'])}
GOALS: {', '.join(persona_info.get('goals', []))}

SCENARIO: You are in a {scenario['setting']} as a {scenario['relationship']}.

RESPONSE GUIDELINES:
- Communication Pattern: {guidelines['communication_patterns']}
- You should naturally express: {', '.join(guidelines['should_express'][:2])}
- Stay true to your personality and concerns
- Respond authentically based on your background and goals
- Keep responses conversational and realistic

USER MESSAGE: "{user_message}"

Respond as {persona_name} would, staying in character:"""

    return prompt

def post_process_persona_response(response: str, persona_name: str, persona_context: Dict[str, Any]) -> str:
    """Post-process the AI response to ensure persona consistency"""
    # Basic post-processing to ensure persona consistency
    
    # Remove any AI-like language
    response = response.replace("As an AI", "").replace("I'm an AI", "")
    response = response.replace("As a language model", "").replace("I'm a language model", "")
    
    # Add persona-specific touches based on character
    if persona_name == "Mary":
        if "exercise" in response.lower() and "safe" not in response.lower():
            response += " I just want to make sure it's safe for someone my age."
    elif persona_name == "Jake":
        if len(response) > 200:  # Jake is more concise
            sentences = response.split('. ')
            response = '. '.join(sentences[:2]) + '.'
    elif persona_name == "Sarah":
        if "cost" not in response.lower() and "price" not in response.lower() and len(response) > 100:
            response += " What would this cost me?"
    elif persona_name == "David":
        if "family" not in response.lower() and "time" not in response.lower() and len(response) > 150:
            response += " I'd need to consider my family's schedule too."
    
    return response.strip()

def calculate_persona_consistency(response: str, persona_context: Dict[str, Any]) -> float:
    """Calculate how well the response matches the persona"""
    consistency_score = 0.8  # Base score
    
    # Check for persona-specific keywords
    personality_traits = persona_context["conversation_style"]["personality_traits"]
    concerns = persona_context["conversation_style"]["main_concerns"]
    
    response_lower = response.lower()
    
    # Bonus for mentioning concerns
    for concern in concerns:
        if any(word in response_lower for word in concern.lower().split()):
            consistency_score += 0.05
    
    # Cap at 1.0
    return min(consistency_score, 1.0)

def analyze_user_approach(user_message: str, persona_context: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze the user's approach and provide feedback"""
    message_lower = user_message.lower()
    persona_concerns = persona_context["conversation_style"]["main_concerns"]
    
    analysis = {
        "addressed_concerns": [],
        "missed_opportunities": [],
        "tone_appropriateness": "neutral"
    }
    
    # Check if user addressed persona concerns
    for concern in persona_concerns:
        concern_keywords = concern.lower().split()
        if any(word in message_lower for word in concern_keywords):
            analysis["addressed_concerns"].append(concern)
    
    # Determine missed opportunities
    all_concerns = set(persona_concerns)
    addressed_concerns = set(analysis["addressed_concerns"])
    analysis["missed_opportunities"] = list(all_concerns - addressed_concerns)
    
    return analysis

def analyze_persona_reaction(persona_response: str, persona_context: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze how the persona reacted"""
    response_lower = persona_response.lower()
    
    # Determine reaction type based on response content
    if any(word in response_lower for word in ["great", "perfect", "excellent", "love"]):
        reaction_type = "positive"
    elif any(word in response_lower for word in ["concern", "worry", "not sure", "hesitant"]):
        reaction_type = "cautious"
    elif any(word in response_lower for word in ["no", "can't", "won't", "don't think"]):
        reaction_type = "resistant"
    else:
        reaction_type = "neutral"
    
    return {
        "reaction_type": reaction_type,
        "engagement_level": "high" if len(persona_response) > 100 else "medium",
        "decision_indicators": extract_decision_indicators(persona_response)
    }

def extract_decision_indicators(response: str) -> Dict[str, bool]:
    """Extract indicators of decision-making from response"""
    response_lower = response.lower()
    
    return {
        "showing_interest": any(word in response_lower for word in ["interested", "sounds good", "tell me more"]),
        "raising_objections": any(word in response_lower for word in ["but", "however", "concern", "worry"]),
        "ready_to_proceed": any(word in response_lower for word in ["let's do it", "sign me up", "when can we start"]),
        "needs_more_info": any(word in response_lower for word in ["how", "what", "when", "where", "tell me"])
    }

def generate_improvement_suggestions(
    user_message: str, 
    persona_response: str, 
    persona_context: Dict[str, Any]
) -> list:
    """Generate suggestions for improving the sales approach"""
    suggestions = []
    
    analysis = analyze_user_approach(user_message, persona_context)
    persona_reaction = analyze_persona_reaction(persona_response, persona_context)
    
    # Suggestions based on missed opportunities
    if analysis["missed_opportunities"]:
        suggestions.append({
            "category": "Address Concerns",
            "suggestion": f"Consider addressing their main concerns: {', '.join(analysis['missed_opportunities'][:2])}"
        })
    
    # Suggestions based on persona reaction
    if persona_reaction["reaction_type"] == "cautious":
        suggestions.append({
            "category": "Build Confidence",
            "suggestion": "The client seems cautious. Provide more reassurance and specific examples."
        })
    elif persona_reaction["reaction_type"] == "resistant":
        suggestions.append({
            "category": "Overcome Objections",
            "suggestion": "Address their concerns directly and provide alternative solutions."
        })
    
    # Decision indicator suggestions
    decision_indicators = persona_reaction["decision_indicators"]
    if decision_indicators["needs_more_info"]:
        suggestions.append({
            "category": "Provide Information",
            "suggestion": "They need more details. Be prepared with specific information and examples."
        })
    
    return suggestions[:3]  # Return top 3 suggestions

# Additional utility endpoints
@persona_chat_router.get("/")
async def list_all_personas() -> Dict[str, Any]:
    """List all available personas with their basic info"""
    personas = persona_service.list_personas()
    return {"success": True, "total_personas": len(personas), "personas": personas}

@persona_chat_router.post("/compare-approaches")
async def compare_sales_approaches(
    persona_name: str,
    approach_a: str,
    approach_b: str
) -> Dict[str, Any]:
    """Compare two different sales approaches for a specific persona"""
    try:
        if not persona_service.get_persona(persona_name):
            raise HTTPException(status_code=404, detail=f"Persona '{persona_name}' not found")
        
        # Get persona context
        context_response = await get_persona_context(persona_name)
        persona_context = context_response["context"]
        
        # Analyze both approaches
        analysis_a = analyze_user_approach(approach_a, persona_context)
        analysis_b = analyze_user_approach(approach_b, persona_context)
        
        return {
            "success": True,
            "persona_name": persona_name,
            "comparison": {
                "approach_a": {
                    "message": approach_a,
                    "analysis": analysis_a,
                    "score": len(analysis_a["addressed_concerns"]) * 10
                },
                "approach_b": {
                    "message": approach_b,
                    "analysis": analysis_b,
                    "score": len(analysis_b["addressed_concerns"]) * 10
                }
            },
            "recommendation": (
                "Approach A" if len(analysis_a["addressed_concerns"]) > len(analysis_b["addressed_concerns"])
                else "Approach B" if len(analysis_b["addressed_concerns"]) > len(analysis_a["addressed_concerns"])
                else "Both approaches are similar"
            )
        }
        
    except Exception as e:
        logger.error(f"Error comparing approaches for {persona_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compare approaches")