"""
Script Alignment and Buying State Analysis
Implements suitable answers tracking, buying state evaluation, and script alignment validation
"""
import json
import re
import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

class BuyingState(Enum):
    """Enum for different buying states"""
    UNAWARE = "unaware"           # Not aware of the problem
    PROBLEM_AWARE = "problem_aware"  # Aware of problem, not solution
    SOLUTION_AWARE = "solution_aware"  # Aware of solutions available
    PRODUCT_AWARE = "product_aware"    # Aware of specific products
    MOST_AWARE = "most_aware"         # Ready to buy, needs final push

@dataclass
class BuyingStateAssessment:
    """Assessment of customer's buying state"""
    current_state: BuyingState
    confidence_score: float
    state_indicators: List[str]
    progression_path: List[BuyingState]
    next_recommended_actions: List[str]

@dataclass
class ScriptAlignmentResult:
    """Result of script alignment analysis"""
    alignment_score: float
    script_adherence: float
    suitable_answers_ratio: float
    missed_opportunities: List[str]
    script_deviations: List[str]
    improvement_suggestions: List[str]

@dataclass
class SalesStageAnalysis:
    """Analysis of sales stage progression"""
    current_stage: str
    stage_completion: float
    required_elements: List[str]
    completed_elements: List[str]
    missing_elements: List[str]
    stage_effectiveness: float

class BuyingStateAnalyzer:
    """Analyzes customer buying state throughout conversation"""
    
    def __init__(self):
        self.state_indicators = self._define_buying_state_indicators()
        self.progression_rules = self._define_progression_rules()
    
    def _define_buying_state_indicators(self) -> Dict[BuyingState, Dict]:
        """Define indicators for each buying state"""
        return {
            BuyingState.UNAWARE: {
                "positive_indicators": [
                    "never thought about", "didn't realize", "wasn't aware",
                    "that's interesting", "tell me more", "how does that work"
                ],
                "negative_indicators": [
                    "we need", "looking for", "trying to solve", "have a problem"
                ],
                "questions": [
                    "what do you mean", "how is that possible", "i don't understand"
                ]
            },
            BuyingState.PROBLEM_AWARE: {
                "positive_indicators": [
                    "we have a problem", "struggling with", "need to improve",
                    "not working well", "facing challenges", "issues with"
                ],
                "negative_indicators": [
                    "looking at solutions", "evaluating options", "comparing products"
                ],
                "pain_expressions": [
                    "frustrating", "time-consuming", "expensive", "inefficient"
                ]
            },
            BuyingState.SOLUTION_AWARE: {
                "positive_indicators": [
                    "looking at solutions", "exploring options", "researching",
                    "need a system", "want to implement", "considering"
                ],
                "comparison_language": [
                    "what's different", "compared to", "better than", "why choose"
                ],
                "evaluation_criteria": [
                    "features", "pricing", "implementation", "support"
                ]
            },
            BuyingState.PRODUCT_AWARE: {
                "positive_indicators": [
                    "heard about your product", "saw your demo", "read about",
                    "colleague mentioned", "referred by", "researched your company"
                ],
                "specific_questions": [
                    "how much does it cost", "what's included", "how long to implement",
                    "what's the process", "can it integrate"
                ],
                "competitive_awareness": [
                    "compared to competitor", "also looking at", "why not"
                ]
            },
            BuyingState.MOST_AWARE: {
                "positive_indicators": [
                    "want to move forward", "ready to buy", "let's do this",
                    "when can we start", "what's the next step", "need to get approval"
                ],
                "urgency_indicators": [
                    "as soon as possible", "urgent", "need it now", "deadline"
                ],
                "commitment_language": [
                    "definitely interested", "this is exactly what we need",
                    "perfect solution", "ready to proceed"
                ]
            }
        }
    
    def _define_progression_rules(self) -> Dict[BuyingState, List[BuyingState]]:
        """Define possible progression paths between buying states"""
        return {
            BuyingState.UNAWARE: [BuyingState.PROBLEM_AWARE],
            BuyingState.PROBLEM_AWARE: [BuyingState.SOLUTION_AWARE, BuyingState.PRODUCT_AWARE],
            BuyingState.SOLUTION_AWARE: [BuyingState.PRODUCT_AWARE, BuyingState.MOST_AWARE],
            BuyingState.PRODUCT_AWARE: [BuyingState.MOST_AWARE],
            BuyingState.MOST_AWARE: []  # Final state
        }
    
    def analyze_buying_state(self, conversation_history: List[Dict]) -> BuyingStateAssessment:
        """Analyze customer's current buying state"""
        customer_responses = self._extract_customer_responses(conversation_history)
        
        if not customer_responses:
            return BuyingStateAssessment(
                current_state=BuyingState.UNAWARE,
                confidence_score=0.5,
                state_indicators=[],
                progression_path=[BuyingState.UNAWARE],
                next_recommended_actions=["Identify customer needs and pain points"]
            )
        
        # Analyze each buying state likelihood
        state_scores = {}
        all_indicators = []
        
        for state in BuyingState:
            score, indicators = self._calculate_state_score(state, customer_responses)
            state_scores[state] = score
            all_indicators.extend(indicators)
        
        # Determine current state
        current_state = max(state_scores, key=state_scores.get)
        confidence_score = state_scores[current_state]
        
        # Generate progression path
        progression_path = self._generate_progression_path(current_state, state_scores)
        
        # Generate recommendations
        recommendations = self._generate_state_recommendations(current_state, confidence_score)
        
        return BuyingStateAssessment(
            current_state=current_state,
            confidence_score=confidence_score,
            state_indicators=all_indicators,
            progression_path=progression_path,
            next_recommended_actions=recommendations
        )
    
    def _extract_customer_responses(self, conversation_history: List[Dict]) -> List[str]:
        """Extract customer responses from conversation history"""
        customer_responses = []
        
        for turn in conversation_history:
            if turn.get("role") in ["customer", "client", "prospect"]:
                customer_responses.append(turn.get("content", ""))
        
        return customer_responses
    
    def _calculate_state_score(self, state: BuyingState, responses: List[str]) -> Tuple[float, List[str]]:
        """Calculate likelihood score for a specific buying state"""
        indicators_found = []
        response_text = " ".join(responses).lower()
        
        state_data = self.state_indicators[state]
        positive_score = 0.0
        negative_score = 0.0
        
        # Check positive indicators
        for indicator_type, indicators in state_data.items():
            if indicator_type == "negative_indicators":
                continue
                
            for indicator in indicators:
                if indicator in response_text:
                    positive_score += 1.0
                    indicators_found.append(f"{indicator_type}: {indicator}")
        
        # Check negative indicators (reduce score)
        if "negative_indicators" in state_data:
            for indicator in state_data["negative_indicators"]:
                if indicator in response_text:
                    negative_score += 0.5
        
        # Calculate final score
        raw_score = max(0.0, positive_score - negative_score)
        normalized_score = min(1.0, raw_score / 3.0)  # Normalize to 0-1
        
        return normalized_score, indicators_found
    
    def _generate_progression_path(self, current_state: BuyingState, 
                                 state_scores: Dict[BuyingState, float]) -> List[BuyingState]:
        """Generate likely progression path through buying states"""
        path = [current_state]
        
        # Add likely next states based on scores and rules
        possible_next = self.progression_rules.get(current_state, [])
        
        for next_state in possible_next:
            if state_scores.get(next_state, 0.0) > 0.3:  # Some evidence for next state
                path.append(next_state)
        
        return path
    
    def _generate_state_recommendations(self, state: BuyingState, confidence: float) -> List[str]:
        """Generate recommendations based on buying state"""
        recommendations = {
            BuyingState.UNAWARE: [
                "Educate customer about the problem and its impact",
                "Use questions to help them recognize pain points",
                "Share relevant case studies or examples"
            ],
            BuyingState.PROBLEM_AWARE: [
                "Explore the full scope and impact of their problem",
                "Introduce solution categories and approaches",
                "Help them understand what's possible"
            ],
            BuyingState.SOLUTION_AWARE: [
                "Position your specific solution advantages",
                "Address their evaluation criteria",
                "Provide product demonstrations or trials"
            ],
            BuyingState.PRODUCT_AWARE: [
                "Handle specific objections and concerns",
                "Provide detailed implementation information",
                "Discuss pricing and next steps"
            ],
            BuyingState.MOST_AWARE: [
                "Focus on closing and next steps",
                "Address final concerns or obstacles",
                "Facilitate decision-making process"
            ]
        }
        
        base_recs = recommendations.get(state, ["Continue needs discovery"])
        
        # Adjust based on confidence
        if confidence < 0.6:
            base_recs.insert(0, f"Confirm buying state - confidence only {confidence:.1%}")
        
        return base_recs

class ScriptAlignmentAnalyzer:
    """Analyzes alignment with sales scripts and suitable answer delivery"""
    
    def __init__(self, script_templates_path: str = "./training/validation/script_templates.json"):
        self.script_templates_path = script_templates_path
        self.script_templates = self._load_script_templates()
        self.suitable_answer_criteria = self._define_suitable_answer_criteria()
    
    def _load_script_templates(self) -> Dict:
        """Load sales script templates"""
        if Path(self.script_templates_path).exists():
            with open(self.script_templates_path, 'r') as f:
                return json.load(f)
        else:
            return self._create_default_script_templates()
    
    def _create_default_script_templates(self) -> Dict:
        """Create default script templates"""
        templates = {
            "opening": {
                "required_elements": [
                    "greeting", "introduction", "purpose_statement", "permission_to_continue"
                ],
                "sample_scripts": [
                    "Hello [Name], this is [Your Name] from [Company]. The reason I'm calling is [Purpose]. Do you have a few minutes to chat?"
                ],
                "key_phrases": [
                    "thanks for taking the time", "reason i'm calling", "few minutes"
                ]
            },
            "discovery": {
                "required_elements": [
                    "situation_questions", "problem_questions", "implication_questions", "need_payoff_questions"
                ],
                "sample_scripts": [
                    "Help me understand your current situation with [Area]. What challenges are you facing? How is this impacting your business?"
                ],
                "key_phrases": [
                    "help me understand", "tell me about", "what challenges", "how does that impact"
                ]
            },
            "presentation": {
                "required_elements": [
                    "solution_overview", "benefit_statements", "proof_points", "customization"
                ],
                "sample_scripts": [
                    "Based on what you've shared, our solution can help by [Specific Benefit]. Here's how..."
                ],
                "key_phrases": [
                    "based on what you shared", "our solution helps", "here's how", "specifically for you"
                ]
            },
            "handling_objections": {
                "required_elements": [
                    "acknowledge", "clarify", "respond", "confirm"
                ],
                "sample_scripts": [
                    "I understand your concern about [Objection]. Many clients felt the same way. Let me address that..."
                ],
                "key_phrases": [
                    "i understand", "many clients", "let me address", "does that help"
                ]
            },
            "closing": {
                "required_elements": [
                    "summary", "confirmation", "next_steps", "commitment"
                ],
                "sample_scripts": [
                    "Based on our conversation, it sounds like this would help you [Benefit]. What would you like to do next?"
                ],
                "key_phrases": [
                    "based on our conversation", "sounds like", "what would you like to do", "next steps"
                ]
            }
        }
        
        # Save default templates
        Path(self.script_templates_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.script_templates_path, 'w') as f:
            json.dump(templates, f, indent=2)
        
        return templates
    
    def _define_suitable_answer_criteria(self) -> Dict:
        """Define criteria for suitable answers"""
        return {
            "relevance": {
                "keywords_match": 0.3,
                "context_appropriate": 0.4,
                "addresses_concern": 0.3
            },
            "completeness": {
                "answers_question": 0.5,
                "provides_details": 0.3,
                "includes_next_step": 0.2
            },
            "professionalism": {
                "appropriate_tone": 0.4,
                "clear_communication": 0.3,
                "no_filler_words": 0.3
            }
        }
    
    def analyze_script_alignment(self, sales_stage: str, user_responses: List[str],
                               customer_context: Dict = None) -> ScriptAlignmentResult:
        """Analyze alignment with sales scripts"""
        if sales_stage not in self.script_templates:
            return ScriptAlignmentResult(
                alignment_score=0.0,
                script_adherence=0.0,
                suitable_answers_ratio=0.0,
                missed_opportunities=[f"Unknown sales stage: {sales_stage}"],
                script_deviations=[],
                improvement_suggestions=["Use recognized sales stage framework"]
            )
        
        template = self.script_templates[sales_stage]
        user_text = " ".join(user_responses).lower()
        
        # Analyze script adherence
        adherence_score = self._analyze_script_adherence(template, user_text)
        
        # Analyze suitable answers
        suitable_ratio = self._analyze_suitable_answers(user_responses, customer_context)
        
        # Calculate overall alignment
        alignment_score = (adherence_score * 0.6 + suitable_ratio * 0.4)
        
        # Identify missed opportunities
        missed_opportunities = self._identify_missed_opportunities(template, user_text)
        
        # Identify script deviations
        deviations = self._identify_script_deviations(template, user_text)
        
        # Generate improvement suggestions
        suggestions = self._generate_script_improvements(
            adherence_score, suitable_ratio, missed_opportunities, deviations
        )
        
        return ScriptAlignmentResult(
            alignment_score=alignment_score,
            script_adherence=adherence_score,
            suitable_answers_ratio=suitable_ratio,
            missed_opportunities=missed_opportunities,
            script_deviations=deviations,
            improvement_suggestions=suggestions
        )
    
    def _analyze_script_adherence(self, template: Dict, user_text: str) -> float:
        """Analyze adherence to script template"""
        required_elements = template.get("required_elements", [])
        key_phrases = template.get("key_phrases", [])
        
        # Check for required elements (simplified keyword matching)
        elements_found = 0
        for element in required_elements:
            element_keywords = element.replace("_", " ").split()
            if any(keyword in user_text for keyword in element_keywords):
                elements_found += 1
        
        element_score = elements_found / len(required_elements) if required_elements else 0.0
        
        # Check for key phrases
        phrases_found = sum(1 for phrase in key_phrases if phrase in user_text)
        phrase_score = min(1.0, phrases_found / len(key_phrases)) if key_phrases else 0.0
        
        return (element_score * 0.7 + phrase_score * 0.3)
    
    def _analyze_suitable_answers(self, responses: List[str], context: Dict = None) -> float:
        """Analyze if answers are suitable for the situation"""
        if not responses:
            return 0.0
        
        suitable_count = 0
        total_responses = len(responses)
        
        for response in responses:
            suitability_score = self._assess_response_suitability(response, context)
            if suitability_score >= 0.7:  # Threshold for "suitable"
                suitable_count += 1
        
        return suitable_count / total_responses
    
    def _assess_response_suitability(self, response: str, context: Dict = None) -> float:
        """Assess suitability of a single response"""
        criteria = self.suitable_answer_criteria
        scores = []
        
        # Relevance assessment
        relevance_score = self._assess_relevance(response, context)
        scores.append(relevance_score)
        
        # Completeness assessment
        completeness_score = self._assess_completeness(response)
        scores.append(completeness_score)
        
        # Professionalism assessment
        professionalism_score = self._assess_professionalism(response)
        scores.append(professionalism_score)
        
        return np.mean(scores)
    
    def _assess_relevance(self, response: str, context: Dict = None) -> float:
        """Assess relevance of response to context"""
        if not context:
            return 0.5  # Neutral score without context
        
        response_lower = response.lower()
        
        # Check if response addresses context keywords
        context_keywords = []
        if "customer_concern" in context:
            context_keywords.extend(context["customer_concern"].lower().split())
        if "topic" in context:
            context_keywords.extend(context["topic"].lower().split())
        
        if not context_keywords:
            return 0.5
        
        matches = sum(1 for keyword in context_keywords if keyword in response_lower)
        return min(1.0, matches / len(context_keywords))
    
    def _assess_completeness(self, response: str) -> float:
        """Assess completeness of response"""
        response_lower = response.lower()
        
        # Check for question answering indicators
        answer_indicators = ["because", "the reason", "this means", "specifically"]
        has_answer = any(indicator in response_lower for indicator in answer_indicators)
        
        # Check for appropriate length
        word_count = len(response.split())
        length_appropriate = 10 <= word_count <= 100
        
        # Check for next step indicators
        next_step_indicators = ["next", "would you like", "shall we", "what do you think"]
        has_next_step = any(indicator in response_lower for indicator in next_step_indicators)
        
        scores = [
            0.5 if has_answer else 0.2,
            0.3 if length_appropriate else 0.1,
            0.2 if has_next_step else 0.0
        ]
        
        return sum(scores)
    
    def _assess_professionalism(self, response: str) -> float:
        """Assess professionalism of response"""
        response_lower = response.lower()
        
        # Check for filler words
        filler_words = ["um", "uh", "like", "you know", "basically"]
        filler_count = sum(response_lower.count(filler) for filler in filler_words)
        
        # Check for professional language
        professional_indicators = ["i understand", "certainly", "absolutely", "definitely"]
        professional_count = sum(1 for indicator in professional_indicators if indicator in response_lower)
        
        # Check for appropriate tone (not too casual)
        casual_indicators = ["yeah", "ok", "cool", "awesome"]
        casual_count = sum(1 for indicator in casual_indicators if indicator in response_lower)
        
        score = 0.5  # Base score
        score += min(0.3, professional_count * 0.1)  # Bonus for professional language
        score -= min(0.3, filler_count * 0.1)  # Penalty for filler words
        score -= min(0.2, casual_count * 0.1)  # Penalty for too casual
        
        return max(0.0, min(1.0, score))
    
    def _identify_missed_opportunities(self, template: Dict, user_text: str) -> List[str]:
        """Identify missed opportunities based on script template"""
        missed = []
        required_elements = template.get("required_elements", [])
        
        for element in required_elements:
            element_keywords = element.replace("_", " ").split()
            if not any(keyword in user_text for keyword in element_keywords):
                missed.append(f"Missing {element.replace('_', ' ')}")
        
        return missed
    
    def _identify_script_deviations(self, template: Dict, user_text: str) -> List[str]:
        """Identify deviations from recommended script"""
        deviations = []
        
        # Check for anti-patterns (things to avoid)
        anti_patterns = {
            "premature_pitch": ["our product", "we offer", "let me tell you about"],
            "leading_questions": ["don't you think", "wouldn't you agree"],
            "feature_dumping": ["feature", "capability", "function"]
        }
        
        for deviation_type, patterns in anti_patterns.items():
            if any(pattern in user_text for pattern in patterns):
                deviations.append(deviation_type.replace("_", " ").title())
        
        return deviations
    
    def _generate_script_improvements(self, adherence: float, suitable_ratio: float,
                                    missed: List[str], deviations: List[str]) -> List[str]:
        """Generate script improvement suggestions"""
        suggestions = []
        
        if adherence < 0.6:
            suggestions.append("Follow the script structure more closely")
        
        if suitable_ratio < 0.7:
            suggestions.append("Ensure answers are more relevant and complete")
        
        if missed:
            suggestions.append(f"Include missing elements: {', '.join(missed[:2])}")
        
        if deviations:
            suggestions.append(f"Avoid: {', '.join(deviations[:2])}")
        
        if not suggestions:
            suggestions.append("Good script alignment - continue current approach")
        
        return suggestions

class SalesStageProgressionAnalyzer:
    """Analyzes progression through sales stages"""
    
    def __init__(self):
        self.sales_stages = self._define_sales_stages()
    
    def _define_sales_stages(self) -> Dict[str, Dict]:
        """Define sales stages and their requirements"""
        return {
            "prospecting": {
                "required_elements": ["research", "qualification", "interest_confirmation"],
                "success_criteria": ["qualified_prospect", "interest_established"],
                "duration_range": (5, 15)  # minutes
            },
            "discovery": {
                "required_elements": ["situation_analysis", "problem_identification", "implication_development"],
                "success_criteria": ["pain_points_identified", "impact_understood"],
                "duration_range": (15, 30)
            },
            "presentation": {
                "required_elements": ["solution_demonstration", "benefit_connection", "value_proposition"],
                "success_criteria": ["solution_understood", "value_recognized"],
                "duration_range": (20, 40)
            },
            "handling_objections": {
                "required_elements": ["objection_acknowledgment", "clarification", "response"],
                "success_criteria": ["objections_resolved", "concerns_addressed"],
                "duration_range": (10, 25)
            },
            "closing": {
                "required_elements": ["decision_confirmation", "next_steps", "commitment"],
                "success_criteria": ["decision_made", "implementation_planned"],
                "duration_range": (5, 15)
            }
        }
    
    def analyze_stage_progression(self, conversation_data: Dict, current_stage: str) -> SalesStageAnalysis:
        """Analyze progression through current sales stage"""
        stage_info = self.sales_stages.get(current_stage, {})
        
        if not stage_info:
            return SalesStageAnalysis(
                current_stage=current_stage,
                stage_completion=0.0,
                required_elements=[],
                completed_elements=[],
                missing_elements=[current_stage],
                stage_effectiveness=0.0
            )
        
        user_responses = conversation_data.get("user_responses", [])
        user_text = " ".join(user_responses).lower()
        
        # Analyze element completion
        required_elements = stage_info["required_elements"]
        completed_elements = []
        
        for element in required_elements:
            if self._check_element_completion(element, user_text):
                completed_elements.append(element)
        
        missing_elements = [elem for elem in required_elements if elem not in completed_elements]
        completion_ratio = len(completed_elements) / len(required_elements) if required_elements else 0.0
        
        # Assess stage effectiveness
        effectiveness = self._assess_stage_effectiveness(
            current_stage, user_text, completion_ratio, conversation_data
        )
        
        return SalesStageAnalysis(
            current_stage=current_stage,
            stage_completion=completion_ratio,
            required_elements=required_elements,
            completed_elements=completed_elements,
            missing_elements=missing_elements,
            stage_effectiveness=effectiveness
        )
    
    def _check_element_completion(self, element: str, user_text: str) -> bool:
        """Check if a stage element has been completed"""
        element_indicators = {
            "research": ["background", "company", "industry", "researched"],
            "qualification": ["budget", "authority", "need", "timeline"],
            "situation_analysis": ["current situation", "how do you", "tell me about"],
            "problem_identification": ["challenge", "problem", "issue", "difficulty"],
            "solution_demonstration": ["our solution", "this helps", "here's how"],
            "objection_acknowledgment": ["i understand", "i hear you", "that's a concern"]
        }
        
        indicators = element_indicators.get(element, [element.replace("_", " ")])
        return any(indicator in user_text for indicator in indicators)
    
    def _assess_stage_effectiveness(self, stage: str, user_text: str, 
                                  completion: float, conversation_data: Dict) -> float:
        """Assess effectiveness of stage execution"""
        base_score = completion * 0.6  # Base score from completion
        
        # Add quality indicators
        quality_score = 0.0
        
        if stage == "discovery":
            # Count questions asked
            question_count = user_text.count("?")
            quality_score += min(0.3, question_count * 0.05)
        elif stage == "presentation":
            # Check for benefit language
            benefit_words = ["benefit", "help", "improve", "save", "increase"]
            benefit_count = sum(1 for word in benefit_words if word in user_text)
            quality_score += min(0.3, benefit_count * 0.1)
        elif stage == "closing":
            # Check for commitment language
            commitment_words = ["next step", "move forward", "ready", "decide"]
            commitment_count = sum(1 for word in commitment_words if word in user_text)
            quality_score += min(0.3, commitment_count * 0.1)
        
        # Add engagement indicators
        engagement_score = 0.0
        if len(user_text.split()) > 50:  # Adequate engagement
            engagement_score = 0.1
        
        return min(1.0, base_score + quality_score + engagement_score)

def main():
    """Demo script alignment and buying state analysis"""
    logger.info("Initializing Script Alignment and Buying State Analysis")
    
    # Initialize analyzers
    buying_state_analyzer = BuyingStateAnalyzer()
    script_analyzer = ScriptAlignmentAnalyzer()
    stage_analyzer = SalesStageProgressionAnalyzer()
    
    # Mock conversation data
    mock_conversation = [
        {"role": "salesperson", "content": "Hi, thanks for taking the time to speak today. What challenges are you facing with your current system?"},
        {"role": "customer", "content": "We're struggling with manual processes that take too much time and cause errors."},
        {"role": "salesperson", "content": "I understand that must be frustrating. Tell me more about the impact this has on your business."},
        {"role": "customer", "content": "It's affecting our customer service response times and team productivity."}
    ]
    
    mock_user_responses = [
        "Hi, thanks for taking the time to speak today. What challenges are you facing with your current system?",
        "I understand that must be frustrating. Tell me more about the impact this has on your business."
    ]
    
    # Analyze buying state
    buying_state = buying_state_analyzer.analyze_buying_state(mock_conversation)
    logger.info(f"Buying State: {buying_state.current_state.value} (confidence: {buying_state.confidence_score:.2f})")
    
    # Analyze script alignment
    script_alignment = script_analyzer.analyze_script_alignment(
        "discovery", mock_user_responses, {"customer_concern": "manual processes"}
    )
    logger.info(f"Script Alignment: {script_alignment.alignment_score:.2f}")
    logger.info(f"Suitable Answers: {script_alignment.suitable_answers_ratio:.2f}")
    
    # Analyze stage progression
    stage_analysis = stage_analyzer.analyze_stage_progression(
        {"user_responses": mock_user_responses}, "discovery"
    )
    logger.info(f"Stage Completion: {stage_analysis.stage_completion:.2f}")
    logger.info(f"Stage Effectiveness: {stage_analysis.stage_effectiveness:.2f}")

if __name__ == "__main__":
    main()