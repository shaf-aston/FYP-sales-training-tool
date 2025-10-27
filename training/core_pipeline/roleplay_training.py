"""
Roleplay Partner Training Components
Based on architectural design: Generation Components, Model Training, Feature Extraction
"""
import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
from typing import Dict, List, Optional, Tuple
import logging
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class PersonaProfile:
    """Sales persona profile for roleplay training"""
    name: str
    personality_traits: List[str]
    objection_patterns: List[str]
    buying_behaviors: List[str]
    communication_style: str
    difficulty_level: str  # 'beginner', 'intermediate', 'advanced'

class PersonaResponseGenerator:
    """Dynamic personality-consistent reply generation"""
    
    def __init__(self, model_path: str = None):
        self.model_path = model_path
        self.personas = self._load_personas()
        self.response_templates = self._load_response_templates()
    
    def _load_personas(self) -> Dict[str, PersonaProfile]:
        """Load persona profiles"""
        return {
            "skeptical_manager": PersonaProfile(
                name="Skeptical Manager",
                personality_traits=["analytical", "risk-averse", "detail-oriented"],
                objection_patterns=["budget_concerns", "roi_questions", "timeline_issues"],
                buying_behaviors=["needs_proof", "compares_options", "involves_team"],
                communication_style="formal",
                difficulty_level="intermediate"
            ),
            "busy_executive": PersonaProfile(
                name="Busy Executive",
                personality_traits=["time-pressed", "decisive", "results-focused"],
                objection_patterns=["time_constraints", "authority_questions", "priority_issues"],
                buying_behaviors=["quick_decisions", "delegates_details", "values_efficiency"],
                communication_style="direct",
                difficulty_level="advanced"
            ),
            "friendly_small_business": PersonaProfile(
                name="Friendly Small Business Owner",
                personality_traits=["personable", "cost-conscious", "relationship-focused"],
                objection_patterns=["price_sensitivity", "feature_overload", "support_concerns"],
                buying_behaviors=["builds_relationships", "seeks_value", "gradual_adoption"],
                communication_style="casual",
                difficulty_level="beginner"
            )
        }
    
    def _load_response_templates(self) -> Dict[str, List[str]]:
        """Load response templates for different scenarios"""
        return {
            "objection_responses": [
                "I understand your concern about {concern}. Many of our clients felt the same way initially.",
                "That's a great question about {topic}. Let me explain how we address that.",
                "I appreciate you bringing up {issue}. Here's how we typically handle that situation."
            ],
            "interest_responses": [
                "That sounds like exactly what we can help with. Tell me more about {topic}.",
                "I'm glad you mentioned {subject}. We've helped many companies with similar challenges.",
                "That's a perfect fit for our solution. How are you currently handling {situation}?"
            ],
            "closing_responses": [
                "Based on what you've shared, I think we have a strong fit. What would you like to do next?",
                "It sounds like this could really benefit your {business_area}. Shall we move forward?",
                "Given your {requirements}, I'm confident this is the right solution. Ready to get started?"
            ]
        }
    
    def generate_persona_response(self, persona_id: str, user_input: str, context: str = "") -> str:
        """Generate personality-consistent response"""
        persona = self.personas.get(persona_id)
        if not persona:
            return "I'm not sure I understand. Could you clarify?"
        
        # Analyze user input for intent
        intent = self._analyze_intent(user_input)
        
        # Generate response based on persona and intent
        response = self._craft_response(persona, intent, user_input, context)
        
        return response
    
    def _analyze_intent(self, user_input: str) -> str:
        """Analyze user input to determine intent"""
        user_lower = user_input.lower()
        
        # Simple intent classification
        if any(word in user_lower for word in ['price', 'cost', 'expensive', 'budget']):
            return 'price_objection'
        elif any(word in user_lower for word in ['time', 'busy', 'schedule']):
            return 'time_objection'
        elif any(word in user_lower for word in ['interested', 'sounds good', 'tell me more']):
            return 'interest'
        elif any(word in user_lower for word in ['not sure', 'doubt', 'concern']):
            return 'skepticism'
        else:
            return 'general_inquiry'
    
    def _craft_response(self, persona: PersonaProfile, intent: str, user_input: str, context: str) -> str:
        """Craft response based on persona and intent"""
        # This would use more sophisticated generation in practice
        if intent == 'price_objection':
            if persona.difficulty_level == 'advanced':
                return "Look, I get it - budget is always a concern. But let's talk ROI. What's the cost of not solving this problem?"
            else:
                return "I understand price is important. Let me show you how this pays for itself in the first quarter."
        
        elif intent == 'time_objection':
            if persona.communication_style == 'direct':
                return "I respect your time. Give me 5 minutes to show you something that could save you hours every week."
            else:
                return "I know everyone's busy these days. That's exactly why this solution is so valuable - it automates what you're doing manually."
        
        elif intent == 'interest':
            return "Great! Let me ask you - what's your biggest challenge with [current process] right now?"
        
        else:
            return "Tell me more about your current situation. What's working well, and what isn't?"

class ObjectionHandler:
    """Realistic challenge generation for sales training"""
    
    def __init__(self):
        self.objection_database = self._build_objection_database()
    
    def _build_objection_database(self) -> Dict[str, List[Dict]]:
        """Build database of common sales objections"""
        return {
            "price": [
                {"objection": "It's too expensive", "difficulty": "easy", "follow_up": "What specifically makes it feel expensive?"},
                {"objection": "I need to think about it", "difficulty": "medium", "follow_up": "What specifically do you need to think about?"},
                {"objection": "We don't have budget this year", "difficulty": "hard", "follow_up": "When does your budget year start?"}
            ],
            "authority": [
                {"objection": "I need to check with my boss", "difficulty": "easy", "follow_up": "When will you be speaking with them?"},
                {"objection": "The board needs to approve this", "difficulty": "hard", "follow_up": "What information would help you present to the board?"}
            ],
            "timing": [
                {"objection": "Now isn't a good time", "difficulty": "easy", "follow_up": "When would be a better time?"},
                {"objection": "We're too busy to implement anything new", "difficulty": "medium", "follow_up": "What if this could reduce your current workload?"}
            ],
            "need": [
                {"objection": "We're happy with our current solution", "difficulty": "medium", "follow_up": "What do you like most about it?"},
                {"objection": "We don't really need this", "difficulty": "hard", "follow_up": "Help me understand your current process"}
            ]
        }
    
    def generate_objection(self, category: str = None, difficulty: str = None) -> Dict:
        """Generate appropriate objection for training"""
        if category:
            objections = self.objection_database.get(category, [])
        else:
            # Random category
            all_objections = []
            for cat_objections in self.objection_database.values():
                all_objections.extend(cat_objections)
            objections = all_objections
        
        if difficulty:
            objections = [obj for obj in objections if obj['difficulty'] == difficulty]
        
        if objections:
            return np.random.choice(objections)
        else:
            return {"objection": "I'm not sure this is right for us", "difficulty": "medium", "follow_up": "What concerns do you have?"}

class FeatureExtraction:
    """Extract features for training analysis"""
    
    def extract_prospect_features(self, conversation_text: str) -> Dict:
        """Extract customer personality traits from conversation"""
        features = {
            'communication_style': self._analyze_communication_style(conversation_text),
            'decision_making_style': self._analyze_decision_making(conversation_text),
            'pain_points': self._extract_pain_points(conversation_text),
            'buying_signals': self._detect_buying_signals(conversation_text),
            'objection_patterns': self._identify_objection_patterns(conversation_text)
        }
        return features
    
    def _analyze_communication_style(self, text: str) -> str:
        """Analyze communication style from text"""
        text_lower = text.lower()
        
        formal_indicators = ['however', 'therefore', 'furthermore', 'nevertheless']
        casual_indicators = ['yeah', 'ok', 'cool', 'awesome', 'sure thing']
        direct_indicators = ['bottom line', 'cut to the chase', 'just tell me']
        
        formal_count = sum(1 for indicator in formal_indicators if indicator in text_lower)
        casual_count = sum(1 for indicator in casual_indicators if indicator in text_lower)
        direct_count = sum(1 for indicator in direct_indicators if indicator in text_lower)
        
        if direct_count > max(formal_count, casual_count):
            return 'direct'
        elif formal_count > casual_count:
            return 'formal'
        else:
            return 'casual'
    
    def _analyze_decision_making(self, text: str) -> str:
        """Analyze decision-making style"""
        text_lower = text.lower()
        
        if any(phrase in text_lower for phrase in ['need to think', 'discuss with team', 'get approval']):
            return 'collaborative'
        elif any(phrase in text_lower for phrase in ['let\'s do it', 'sounds good', 'move forward']):
            return 'decisive'
        else:
            return 'analytical'
    
    def _extract_pain_points(self, text: str) -> List[str]:
        """Extract mentioned pain points"""
        pain_indicators = {
            'efficiency': ['slow', 'time-consuming', 'manual', 'inefficient'],
            'cost': ['expensive', 'costly', 'budget', 'money'],
            'quality': ['errors', 'mistakes', 'inconsistent', 'poor quality'],
            'scalability': ['growing', 'scaling', 'capacity', 'volume']
        }
        
        text_lower = text.lower()
        pain_points = []
        
        for category, indicators in pain_indicators.items():
            if any(indicator in text_lower for indicator in indicators):
                pain_points.append(category)
        
        return pain_points
    
    def _detect_buying_signals(self, text: str) -> List[str]:
        """Detect buying signals in conversation"""
        buying_signals = []
        text_lower = text.lower()
        
        signals = {
            'timeline_questions': ['when can we start', 'how long does it take', 'implementation timeline'],
            'pricing_questions': ['what does it cost', 'pricing', 'how much'],
            'feature_interest': ['can it do', 'does it support', 'what about'],
            'decision_language': ['we should', 'let\'s move forward', 'sounds good']
        }
        
        for signal_type, phrases in signals.items():
            if any(phrase in text_lower for phrase in phrases):
                buying_signals.append(signal_type)
        
        return buying_signals
    
    def _identify_objection_patterns(self, text: str) -> List[str]:
        """Identify patterns in objections raised"""
        objection_patterns = []
        text_lower = text.lower()
        
        patterns = {
            'price_sensitivity': ['too expensive', 'costs too much', 'out of budget'],
            'authority_issues': ['need approval', 'check with boss', 'not my decision'],
            'timing_concerns': ['not good time', 'too busy', 'maybe later'],
            'competition_comparison': ['compared to', 'what about', 'why not']
        }
        
        for pattern_type, phrases in patterns.items():
            if any(phrase in text_lower for phrase in phrases):
                objection_patterns.append(pattern_type)
        
        return objection_patterns

def main():
    """Demo the roleplay training components"""
    logger.info("Initializing Roleplay Partner Training Components")
    
    # Initialize components
    generator = PersonaResponseGenerator()
    objection_handler = ObjectionHandler()
    feature_extractor = FeatureExtraction()
    
    # Demo persona response
    test_input = "I'm interested but the price seems high"
    response = generator.generate_persona_response("skeptical_manager", test_input)
    logger.info(f"Generated response: {response}")
    
    # Demo objection generation
    objection = objection_handler.generate_objection("price", "medium")
    logger.info(f"Generated objection: {objection}")
    
    # Demo feature extraction
    sample_conversation = "I'm really busy and this seems complicated. How much does it cost and when can we start?"
    features = feature_extractor.extract_prospect_features(sample_conversation)
    logger.info(f"Extracted features: {json.dumps(features, indent=2)}")

if __name__ == "__main__":
    main()