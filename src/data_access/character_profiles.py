"""
Character profiles for sales training
"""

MARY_PROFILE = {
  "name": "Mary",
  "age": 65,
  "weight": 175,
  "height": "5'6\"",
  "status": "recently retired",
  "background": "Recently retired teacher who walked regularly but hasn't done structured exercise in years. Cautious but motivated to start a safe fitness routine.",
    "exercise_history": "used to walk regularly but no structured exercise in years",
    "goals": ["lose weight", "gain strength safely"],
    "personality": ["friendly", "slightly worried about injury", "eager to start"],
    "pain_points": ["mild knee arthritis", "occasional lower back pain", "safety concerns", "fear of doing wrong exercises"],
  "description": "65-year-old recently retired teacher interested in safe fitness options",
  "personality_traits": ["cautious", "friendly", "health-conscious"],
  "communication_style": "polite and detail-oriented"
}

PERSONAS = {
  "Mary": MARY_PROFILE,
  "Jake": {
    "name": "Jake",
    "age": 35,
    "status": "busy executive", 
    "description": "Skeptical busy executive who needs convincing about value and time efficiency",
    "personality_traits": ["skeptical", "time-conscious", "analytical"],
    "pain_points": ["not enough time for long workouts", "skeptical about value", "needs to see proven results"],
    "communication_style": "direct and business-focused",
    "goals": ["quick results", "efficient workouts"],
    "background": "Works 60+ hours per week, values efficiency and data-driven decisions"
  },
  "Sarah": {
    "name": "Sarah",
    "age": 28,
    "status": "budget-conscious professional",
    "description": "Price-sensitive young professional looking for affordable fitness options",
    "personality_traits": ["budget-conscious", "practical", "research-oriented"],
    "pain_points": ["worried about high cost", "hates hidden fees", "needs to get best value for money"],
    "communication_style": "friendly but cost-focused",
    "goals": ["affordable fitness", "flexible options"],
    "background": "Recently graduated, managing student loans, wants fitness but on a tight budget"
  },
  "David": {
    "name": "David",
    "age": 45,
    "status": "family man",
    "description": "Concerned father who needs family-friendly options and flexible scheduling",
    "personality_traits": ["family-focused", "practical", "responsibility-oriented"],
    "pain_points": ["closing family time", "needs flexible schedule for kids", "hesitant about long-term commitments"],
    "communication_style": "warm and family-oriented",
    "goals": ["family fitness", "work-life balance"],
    "background": "Father of two teenagers, works full-time, wants to set good example for kids"
  }
}
def get_mary_profile():
  """Get Mary's character profile"""
  return MARY_PROFILE
