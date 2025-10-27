"""
Enhanced Validation & Quality Control System
Implements comprehensive validation methods and expert comparison features
"""
import json
import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from pathlib import Path
import logging
from datetime import datetime
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import re

logger = logging.getLogger(__name__)

@dataclass
class ExpertExample:
    """Expert sales conversation example for comparison"""
    conversation_id: str
    scenario_type: str  # 'objection_handling', 'needs_discovery', etc.
    expert_response: str
    context: str
    techniques_used: List[str]
    effectiveness_score: float
    persona_type: str

@dataclass
class ValidationResult:
    """Result of validation process"""
    data_id: str
    validation_type: str
    score: float
    passed: bool
    issues: List[str]
    recommendations: List[str]
    expert_comparison: Optional[Dict] = None

class ExpertComparisonValidator:
    """Validates conversations against expert examples"""
    
    def __init__(self, expert_examples_path: str = "./training/validation/expert_examples.json"):
        self.expert_examples_path = expert_examples_path
        self.expert_examples = self._load_expert_examples()
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self._prepare_expert_vectors()
    
    def _load_expert_examples(self) -> List[ExpertExample]:
        """Load expert conversation examples"""
        if not Path(self.expert_examples_path).exists():
            return self._create_default_expert_examples()
        
        with open(self.expert_examples_path, 'r') as f:
            data = json.load(f)
        
        examples = []
        for item in data:
            examples.append(ExpertExample(**item))
        
        return examples
    
    def _create_default_expert_examples(self) -> List[ExpertExample]:
        """Create default expert examples"""
        examples = [
            ExpertExample(
                conversation_id="expert_001",
                scenario_type="objection_handling",
                expert_response="I understand your concern about the price. Many of our clients felt the same way initially. Let me show you how this investment pays for itself within the first quarter through increased efficiency and reduced manual work. What specific budget constraints are you working with?",
                context="Customer objects to price being too high",
                techniques_used=["empathy", "social_proof", "roi_demonstration", "question_redirect"],
                effectiveness_score=0.95,
                persona_type="skeptical_manager"
            ),
            ExpertExample(
                conversation_id="expert_002",
                scenario_type="needs_discovery",
                expert_response="That's really interesting. Tell me more about your current process for handling customer inquiries. How much time does your team spend on this daily, and what's the biggest challenge you're facing?",
                context="Customer mentions current solution limitations",
                techniques_used=["active_listening", "open_ended_questions", "pain_discovery"],
                effectiveness_score=0.92,
                persona_type="busy_executive"
            ),
            ExpertExample(
                conversation_id="expert_003",
                scenario_type="value_presentation",
                expert_response="Based on what you've shared about handling 200 inquiries per day manually, our automation solution would save your team approximately 4 hours daily. That's 20 hours per week your staff could focus on higher-value activities. How would that impact your business?",
                context="Presenting solution value after needs discovery",
                techniques_used=["quantified_value", "time_savings", "impact_question"],
                effectiveness_score=0.94,
                persona_type="friendly_small_business"
            )
        ]
        
        # Save default examples
        Path(self.expert_examples_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.expert_examples_path, 'w') as f:
            json.dump([example.__dict__ for example in examples], f, indent=2)
        
        return examples
    
    def _prepare_expert_vectors(self):
        """Prepare TF-IDF vectors for expert examples"""
        if not self.expert_examples:
            logger.warning("No expert examples available for comparison")
            return
        
        expert_texts = [example.expert_response for example in self.expert_examples]
        self.expert_vectors = self.vectorizer.fit_transform(expert_texts)
    
    def compare_to_expert(self, user_response: str, scenario_type: str, persona_type: str = None) -> Dict:
        """Compare user response to expert examples"""
        if not self.expert_examples:
            return {"similarity_score": 0.0, "best_match": None, "suggestions": []}
        
        # Filter expert examples by scenario and persona
        relevant_experts = [
            example for example in self.expert_examples
            if example.scenario_type == scenario_type and
            (persona_type is None or example.persona_type == persona_type)
        ]
        
        if not relevant_experts:
            # Fall back to scenario-only matching
            relevant_experts = [
                example for example in self.expert_examples
                if example.scenario_type == scenario_type
            ]
        
        if not relevant_experts:
            return {"similarity_score": 0.0, "best_match": None, "suggestions": []}
        
        # Vectorize user response
        user_vector = self.vectorizer.transform([user_response])
        
        # Calculate similarities
        best_similarity = 0.0
        best_match = None
        
        for expert in relevant_experts:
            expert_idx = self.expert_examples.index(expert)
            similarity = cosine_similarity(user_vector, self.expert_vectors[expert_idx:expert_idx+1])[0][0]
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = expert
        
        # Generate suggestions based on best match
        suggestions = self._generate_improvement_suggestions(user_response, best_match)
        
        return {
            "similarity_score": best_similarity,
            "best_match": best_match.__dict__ if best_match else None,
            "suggestions": suggestions,
            "techniques_gap": self._identify_technique_gaps(user_response, best_match)
        }
    
    def _generate_improvement_suggestions(self, user_response: str, expert_example: ExpertExample) -> List[str]:
        """Generate improvement suggestions based on expert comparison"""
        if not expert_example:
            return ["No expert example available for comparison"]
        
        suggestions = []
        user_lower = user_response.lower()
        
        # Check for missing techniques
        missing_techniques = []
        if "empathy" in expert_example.techniques_used and not any(
            phrase in user_lower for phrase in ["understand", "feel", "appreciate", "relate"]
        ):
            missing_techniques.append("empathy")
            suggestions.append("Add empathetic language: 'I understand your concern...' or 'I can appreciate that...'")
        
        if "question_redirect" in expert_example.techniques_used and "?" not in user_response:
            missing_techniques.append("questioning")
            suggestions.append("End with a question to maintain engagement and gather more information")
        
        if "quantified_value" in expert_example.techniques_used and not any(
            word in user_lower for word in ["save", "reduce", "increase", "hours", "percent", "%"]
        ):
            missing_techniques.append("quantification")
            suggestions.append("Include specific numbers and quantifiable benefits")
        
        if "social_proof" in expert_example.techniques_used and not any(
            phrase in user_lower for phrase in ["clients", "customers", "companies", "others"]
        ):
            missing_techniques.append("social_proof")
            suggestions.append("Reference other clients or companies: 'Many of our clients...'")
        
        # Length and structure suggestions
        if len(user_response.split()) < 20:
            suggestions.append("Expand your response with more detail and context")
        elif len(user_response.split()) > 80:
            suggestions.append("Consider making your response more concise and focused")
        
        return suggestions[:3]  # Limit to top 3 suggestions
    
    def _identify_technique_gaps(self, user_response: str, expert_example: ExpertExample) -> List[str]:
        """Identify missing sales techniques compared to expert"""
        if not expert_example:
            return []
        
        user_techniques = self._extract_techniques(user_response)
        expert_techniques = set(expert_example.techniques_used)
        
        return list(expert_techniques - set(user_techniques))
    
    def _extract_techniques(self, response: str) -> List[str]:
        """Extract sales techniques used in response"""
        techniques = []
        response_lower = response.lower()
        
        technique_patterns = {
            "empathy": ["understand", "feel", "appreciate", "relate to"],
            "questioning": ["?"],
            "social_proof": ["clients", "customers", "companies", "others"],
            "quantified_value": ["save", "reduce", "increase", "hours", "%", "percent"],
            "active_listening": ["what you said", "mentioned", "shared"],
            "roi_demonstration": ["return", "investment", "roi", "pays for itself"]
        }
        
        for technique, patterns in technique_patterns.items():
            if any(pattern in response_lower for pattern in patterns):
                techniques.append(technique)
        
        return techniques

class AdvancedQualityValidator:
    """Advanced validation methods beyond basic thresholds"""
    
    def __init__(self):
        self.validation_rules = self._define_validation_rules()
    
    def _define_validation_rules(self) -> Dict:
        """Define comprehensive validation rules"""
        return {
            "conversation_flow": {
                "min_turns": 3,
                "max_turns": 20,
                "balanced_participation": 0.3  # Minimum participation ratio for each speaker
            },
            "content_quality": {
                "min_words_per_turn": 5,
                "max_words_per_turn": 100,
                "coherence_threshold": 0.7,
                "relevant_keywords_ratio": 0.1
            },
            "sales_structure": {
                "required_phases": ["greeting", "discovery", "presentation"],
                "objection_handling_present": True,
                "closing_attempt_present": True
            },
            "language_quality": {
                "professionalism_score": 0.8,
                "clarity_score": 0.7,
                "grammar_issues_max": 3
            }
        }
    
    def comprehensive_validation(self, conversation_data: Dict) -> ValidationResult:
        """Run comprehensive validation on conversation data"""
        validation_issues = []
        recommendations = []
        overall_score = 0.0
        validation_scores = []
        
        # Validate conversation flow
        flow_score = self._validate_conversation_flow(conversation_data, validation_issues, recommendations)
        validation_scores.append(flow_score)
        
        # Validate content quality
        content_score = self._validate_content_quality(conversation_data, validation_issues, recommendations)
        validation_scores.append(content_score)
        
        # Validate sales structure
        structure_score = self._validate_sales_structure(conversation_data, validation_issues, recommendations)
        validation_scores.append(structure_score)
        
        # Validate language quality
        language_score = self._validate_language_quality(conversation_data, validation_issues, recommendations)
        validation_scores.append(language_score)
        
        # Calculate overall score
        overall_score = np.mean(validation_scores)
        passed = overall_score >= 0.7 and len(validation_issues) <= 2
        
        return ValidationResult(
            data_id=conversation_data.get("id", "unknown"),
            validation_type="comprehensive",
            score=overall_score,
            passed=passed,
            issues=validation_issues,
            recommendations=recommendations
        )
    
    def _validate_conversation_flow(self, data: Dict, issues: List, recommendations: List) -> float:
        """Validate conversation flow and structure"""
        score = 1.0
        transcript = data.get("transcript", "")
        
        # Count conversation turns (simplified)
        turns = len([line for line in transcript.split('\n') if line.strip()])
        
        if turns < self.validation_rules["conversation_flow"]["min_turns"]:
            issues.append(f"Too few conversation turns: {turns}")
            recommendations.append("Include more back-and-forth dialogue")
            score -= 0.3
        elif turns > self.validation_rules["conversation_flow"]["max_turns"]:
            issues.append(f"Too many conversation turns: {turns}")
            recommendations.append("Focus on more concise, effective exchanges")
            score -= 0.2
        
        return max(score, 0.0)
    
    def _validate_content_quality(self, data: Dict, issues: List, recommendations: List) -> float:
        """Validate content quality and coherence"""
        score = 1.0
        transcript = data.get("transcript", "")
        
        # Check for relevant sales keywords
        sales_keywords = [
            "solution", "benefit", "value", "price", "cost", "save", "improve",
            "help", "problem", "challenge", "need", "requirement", "goal"
        ]
        
        keyword_count = sum(1 for keyword in sales_keywords if keyword in transcript.lower())
        keyword_ratio = keyword_count / len(sales_keywords)
        
        if keyword_ratio < self.validation_rules["content_quality"]["relevant_keywords_ratio"]:
            issues.append("Low sales-relevant keyword density")
            recommendations.append("Include more sales-focused language and terminology")
            score -= 0.2
        
        return max(score, 0.0)
    
    def _validate_sales_structure(self, data: Dict, issues: List, recommendations: List) -> float:
        """Validate sales conversation structure"""
        score = 1.0
        transcript = data.get("transcript", "").lower()
        
        # Check for sales phases
        phase_indicators = {
            "greeting": ["hello", "hi", "good morning", "nice to meet"],
            "discovery": ["tell me", "what", "how", "why", "explain"],
            "presentation": ["our solution", "this helps", "benefit", "feature"]
        }
        
        missing_phases = []
        for phase, indicators in phase_indicators.items():
            if not any(indicator in transcript for indicator in indicators):
                missing_phases.append(phase)
        
        if missing_phases:
            issues.append(f"Missing sales phases: {', '.join(missing_phases)}")
            recommendations.append(f"Include {missing_phases[0]} elements in the conversation")
            score -= 0.3 * len(missing_phases)
        
        return max(score, 0.0)
    
    def _validate_language_quality(self, data: Dict, issues: List, recommendations: List) -> float:
        """Validate language quality and professionalism"""
        score = 1.0
        transcript = data.get("transcript", "")
        
        # Check for filler words
        filler_words = ["um", "uh", "er", "like", "you know", "basically"]
        filler_count = sum(transcript.lower().count(filler) for filler in filler_words)
        
        if filler_count > 5:
            issues.append(f"Too many filler words: {filler_count}")
            recommendations.append("Reduce filler words for more professional communication")
            score -= 0.2
        
        # Check for appropriate length
        word_count = len(transcript.split())
        if word_count < 50:
            issues.append("Conversation too short")
            recommendations.append("Develop more detailed conversations")
            score -= 0.3
        
        return max(score, 0.0)

class ValidationOrchestrator:
    """Orchestrates all validation methods"""
    
    def __init__(self):
        self.expert_validator = ExpertComparisonValidator()
        self.quality_validator = AdvancedQualityValidator()
        self.validation_history = []
    
    def validate_training_data(self, conversation_data: Dict, scenario_type: str = None) -> Dict:
        """Run complete validation on training data"""
        validation_results = {
            "data_id": conversation_data.get("id", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "validations": {}
        }
        
        # Run comprehensive quality validation
        quality_result = self.quality_validator.comprehensive_validation(conversation_data)
        validation_results["validations"]["quality"] = quality_result.__dict__
        
        # Run expert comparison if applicable
        if scenario_type and "user_responses" in conversation_data:
            user_responses = conversation_data["user_responses"]
            if user_responses:
                expert_comparison = self.expert_validator.compare_to_expert(
                    user_responses[0], scenario_type
                )
                validation_results["validations"]["expert_comparison"] = expert_comparison
        
        # Calculate overall validation score
        scores = []
        if quality_result.score:
            scores.append(quality_result.score)
        
        validation_results["overall_score"] = np.mean(scores) if scores else 0.0
        validation_results["passed"] = validation_results["overall_score"] >= 0.7
        
        # Store validation history
        self.validation_history.append(validation_results)
        
        return validation_results
    
    def get_validation_statistics(self) -> Dict:
        """Get statistics on validation results"""
        if not self.validation_history:
            return {"message": "No validation history available"}
        
        passed_count = sum(1 for result in self.validation_history if result["passed"])
        total_count = len(self.validation_history)
        
        avg_score = np.mean([result["overall_score"] for result in self.validation_history])
        
        return {
            "total_validated": total_count,
            "passed_count": passed_count,
            "pass_rate": passed_count / total_count,
            "average_score": avg_score,
            "latest_validations": self.validation_history[-5:]  # Last 5 validations
        }

def main():
    """Demo validation system"""
    logger.info("Initializing Enhanced Validation System")
    
    # Initialize orchestrator
    orchestrator = ValidationOrchestrator()
    
    # Mock conversation data
    mock_conversation = {
        "id": "test_001",
        "transcript": "Hello, I'm interested in your product but I'm concerned about the price. Our solution helps companies save 30% on operational costs. Many of our clients felt the same way initially. What specific budget constraints are you working with?",
        "user_responses": ["I understand your concern about the price. Let me show you the ROI."],
        "scenario_type": "objection_handling"
    }
    
    # Run validation
    results = orchestrator.validate_training_data(mock_conversation, "objection_handling")
    
    logger.info(f"Validation completed:")
    logger.info(f"- Overall Score: {results['overall_score']:.2f}")
    logger.info(f"- Passed: {results['passed']}")
    logger.info(f"- Expert Similarity: {results['validations'].get('expert_comparison', {}).get('similarity_score', 'N/A')}")
    
    # Show statistics
    stats = orchestrator.get_validation_statistics()
    logger.info(f"Validation Statistics: Pass rate {stats['pass_rate']:.1%}")

if __name__ == "__main__":
    main()