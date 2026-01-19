"""
Fuzzy matching module for intent recognition and objection detection.
Uses rapidfuzz for typo-tolerant keyword matching.
"""

from typing import Dict, List, Optional, Tuple
from rapidfuzz import fuzz


class FuzzyMatcher:
    """Handles fuzzy matching for intent recognition and objection signals."""
    
    # Objection signal patterns
    OBJECTION_PATTERNS = {
        'price_sensitivity': ['expensive', 'cost', 'price', 'budget', 'afford', 'cheap'],
        'time_objection': ['time', 'busy', 'later', 'not now', 'schedule', 'timing'],
        'authority': ['decision maker', 'boss', 'manager', 'need approval', 'authority'],
        'competitor': ['already using', 'competitor', 'current provider', 'switched'],
        'skepticism': ['doubt', 'unsure', 'skeptical', 'not convinced', 'prove']
    }
    
    # Transition readiness signals
    TRANSITION_SIGNALS = {
        'intent_to_logical': ['understand', 'clear', 'got it', 'makes sense'],
        'logical_to_emotional': ['see the value', 'appreciate', 'understand benefits'],
        'emotional_to_future': ['excited', 'interested', 'want to know more'],
        'future_to_consequences': ['what if', 'concerned about', 'worried'],
        'consequences_to_close': ['ready', 'move forward', 'next steps']
    }
    
    def __init__(self, mode: str = "simple"):
        """
        Initialize fuzzy matcher.
        
        Args:
            mode: Matching mode ('simple' or 'advanced')
        """
        self.mode = mode
        self.threshold = 70  # Minimum similarity score for matches
    
    def match_intent(self, user_input: str, intents: Dict[str, List[str]]) -> Optional[str]:
        """
        Match user input to an intent using fuzzy matching.
        
        Args:
            user_input: User's message
            intents: Dict mapping intent names to keyword lists
            
        Returns:
            Matched intent name or None if no match
        """
        if not user_input or not intents:
            return None
        
        input_lower = user_input.lower()
        best_intent = None
        best_score = 0
        
        for intent_name, keywords in intents.items():
            intent_score = 0
            matches = 0
            
            for keyword in keywords:
                # Use partial_ratio for substring matching with typo tolerance
                score = fuzz.partial_ratio(keyword.lower(), input_lower)
                
                if score >= self.threshold:
                    intent_score += score
                    matches += 1
            
            # Average score of matched keywords only
            if matches > 0:
                avg_score = intent_score / matches
                # Boost score if multiple keywords matched
                boosted_score = avg_score * (1 + (matches - 1) * 0.1)
                
                if boosted_score > best_score:
                    best_score = boosted_score
                    best_intent = intent_name
        
        return best_intent if best_intent else None
    
    def detect_objection_signals(self, user_input: str) -> List[Dict[str, any]]:
        """
        Detect objection signals in user input.
        
        Args:
            user_input: User's message
            
        Returns:
            List of detected objections with type and confidence
        """
        if not user_input:
            return []
        
        input_lower = user_input.lower()
        detected = []
        
        for objection_type, patterns in self.OBJECTION_PATTERNS.items():
            max_confidence = 0
            
            for pattern in patterns:
                score = fuzz.partial_ratio(pattern.lower(), input_lower)
                confidence = score / 100.0
                
                if confidence >= 0.7:  # 70% threshold
                    max_confidence = max(max_confidence, confidence)
            
            if max_confidence > 0:
                detected.append({
                    'type': objection_type,
                    'confidence': max_confidence
                })
        
        return detected
    
    def detect_transition_readiness(
        self, 
        user_input: str, 
        current_phase: str, 
        target_phase: str
    ) -> Tuple[bool, float]:
        """
        Detect if user is ready to transition between phases.
        
        Args:
            user_input: User's message
            current_phase: Current conversation phase
            target_phase: Target phase to transition to
            
        Returns:
            Tuple of (is_ready, confidence_score)
        """
        if not user_input:
            return False, 0.0
        
        # Create transition key
        transition_key = f"{current_phase}_to_{target_phase}"
        
        # Check if this transition exists
        if transition_key not in self.TRANSITION_SIGNALS:
            return False, 0.0
        
        input_lower = user_input.lower()
        signals = self.TRANSITION_SIGNALS[transition_key]
        
        max_confidence = 0.0
        for signal in signals:
            score = fuzz.partial_ratio(signal.lower(), input_lower)
            confidence = score / 100.0
            max_confidence = max(max_confidence, confidence)
        
        is_ready = max_confidence >= 0.7
        return is_ready, max_confidence
