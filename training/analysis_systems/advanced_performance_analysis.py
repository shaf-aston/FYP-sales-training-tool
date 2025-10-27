"""
Advanced Performance Analysis System
Implements NEPQ selling techniques, active listening evaluation, and advanced questioning assessment
"""
import json
import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from collections import Counter

logger = logging.getLogger(__name__)

@dataclass
class NEPQAssessment:
    """NEPQ (Needs, Emotions, Pain, Qualification) selling technique assessment"""
    needs_discovery_score: float
    emotion_recognition_score: float
    pain_identification_score: float
    qualification_score: float
    overall_nepq_score: float
    specific_findings: List[str]

@dataclass
class QuestionQualityAssessment:
    """Assessment of question quality and effectiveness"""
    open_question_ratio: float
    probing_depth_score: float
    question_relevance_score: float
    follow_up_effectiveness: float
    overall_quality_score: float
    question_breakdown: Dict[str, int]
    improvement_suggestions: List[str]

@dataclass
class ActiveListeningAssessment:
    """Assessment of active listening behaviors"""
    acknowledgment_frequency: float
    paraphrasing_usage: float
    clarification_seeking: float
    emotional_recognition: float
    silence_utilization: float
    overall_listening_score: float
    listening_behaviors: List[str]

class NEPQAnalyzer:
    """Analyzes conversations for NEPQ selling technique implementation"""
    
    def __init__(self):
        self.nepq_indicators = self._define_nepq_indicators()
        self.scoring_weights = {
            "needs": 0.3,
            "emotions": 0.2,
            "pain": 0.3,
            "qualification": 0.2
        }
    
    def _define_nepq_indicators(self) -> Dict[str, Dict]:
        """Define indicators for each NEPQ component"""
        return {
            "needs": {
                "discovery_phrases": [
                    "what are you looking for", "what do you need", "tell me about your requirements",
                    "what's important to you", "what are your goals", "what would you like to achieve",
                    "help me understand", "walk me through", "describe your situation"
                ],
                "questioning_patterns": [
                    "what", "how", "why", "when", "where", "which", "who"
                ],
                "negative_indicators": [
                    "let me tell you about", "our product has", "we offer"
                ]
            },
            "emotions": {
                "emotion_recognition": [
                    "sounds like you're", "i can hear that you", "you seem", "it feels like",
                    "i understand you're", "that must be", "i sense that"
                ],
                "empathy_phrases": [
                    "i understand", "that makes sense", "i can see why", "i appreciate",
                    "that's understandable", "i hear you", "i get it"
                ],
                "emotional_words": [
                    "frustrated", "excited", "concerned", "worried", "hopeful", 
                    "confident", "uncertain", "pleased", "disappointed"
                ]
            },
            "pain": {
                "pain_discovery": [
                    "what's your biggest challenge", "what keeps you up at night", 
                    "what's not working", "where are you struggling", "what's frustrating",
                    "what problems are you facing", "what's the impact of"
                ],
                "pain_amplification": [
                    "how does that affect", "what's the cost of", "what happens if",
                    "how long has this been", "how much time do you spend"
                ],
                "consequence_exploration": [
                    "what's the consequence", "what's at stake", "what's the risk",
                    "what would happen if", "how does this impact your business"
                ]
            },
            "qualification": {
                "budget_qualification": [
                    "what's your budget", "what range are you thinking", "what have you allocated",
                    "what would you invest", "what's your investment level"
                ],
                "authority_qualification": [
                    "who makes the decision", "who else is involved", "what's your process",
                    "who would need to approve", "what's the approval process"
                ],
                "timeline_qualification": [
                    "when are you looking to", "what's your timeline", "when do you need",
                    "how soon", "what's your deadline"
                ],
                "need_qualification": [
                    "how important is this", "what's the priority", "on a scale of",
                    "how critical", "what's driving this"
                ]
            }
        }
    
    def analyze_nepq_implementation(self, conversation_text: str, user_responses: List[str]) -> NEPQAssessment:
        """Analyze NEPQ implementation in conversation"""
        user_text = " ".join(user_responses).lower()
        conversation_lower = conversation_text.lower()
        
        # Analyze each NEPQ component
        needs_score = self._analyze_needs_discovery(user_text, conversation_lower)
        emotions_score = self._analyze_emotion_handling(user_text, conversation_lower)
        pain_score = self._analyze_pain_identification(user_text, conversation_lower)
        qualification_score = self._analyze_qualification(user_text, conversation_lower)
        
        # Calculate overall NEPQ score
        overall_score = (
            needs_score * self.scoring_weights["needs"] +
            emotions_score * self.scoring_weights["emotions"] +
            pain_score * self.scoring_weights["pain"] +
            qualification_score * self.scoring_weights["qualification"]
        )
        
        # Generate specific findings
        findings = self._generate_nepq_findings(
            needs_score, emotions_score, pain_score, qualification_score, user_text
        )
        
        return NEPQAssessment(
            needs_discovery_score=needs_score,
            emotion_recognition_score=emotions_score,
            pain_identification_score=pain_score,
            qualification_score=qualification_score,
            overall_nepq_score=overall_score,
            specific_findings=findings
        )
    
    def _analyze_needs_discovery(self, user_text: str, conversation_text: str) -> float:
        """Analyze needs discovery implementation"""
        indicators = self.nepq_indicators["needs"]
        score = 0.0
        
        # Check for discovery phrases
        discovery_count = sum(1 for phrase in indicators["discovery_phrases"] if phrase in user_text)
        if discovery_count > 0:
            score += 0.4
        
        # Check for questioning patterns
        question_words = sum(1 for word in indicators["questioning_patterns"] if word in user_text)
        if question_words >= 3:
            score += 0.3
        elif question_words >= 1:
            score += 0.2
        
        # Penalty for product-focused language
        negative_count = sum(1 for phrase in indicators["negative_indicators"] if phrase in user_text)
        if negative_count > 0:
            score -= 0.2
        
        # Bonus for customer responses indicating needs discovery
        if any(phrase in conversation_text for phrase in ["i need", "we're looking for", "our requirement"]):
            score += 0.3
        
        return max(0.0, min(1.0, score))
    
    def _analyze_emotion_handling(self, user_text: str, conversation_text: str) -> float:
        """Analyze emotion recognition and handling"""
        indicators = self.nepq_indicators["emotions"]
        score = 0.0
        
        # Check for emotion recognition phrases
        recognition_count = sum(1 for phrase in indicators["emotion_recognition"] if phrase in user_text)
        if recognition_count > 0:
            score += 0.4
        
        # Check for empathy phrases
        empathy_count = sum(1 for phrase in indicators["empathy_phrases"] if phrase in user_text)
        if empathy_count >= 2:
            score += 0.3
        elif empathy_count >= 1:
            score += 0.2
        
        # Check for emotional words in conversation
        emotion_words = sum(1 for word in indicators["emotional_words"] if word in conversation_text)
        if emotion_words > 0:
            score += 0.3
        
        return max(0.0, min(1.0, score))
    
    def _analyze_pain_identification(self, user_text: str, conversation_text: str) -> float:
        """Analyze pain point identification and exploration"""
        indicators = self.nepq_indicators["pain"]
        score = 0.0
        
        # Check for pain discovery questions
        discovery_count = sum(1 for phrase in indicators["pain_discovery"] if phrase in user_text)
        if discovery_count > 0:
            score += 0.4
        
        # Check for pain amplification
        amplification_count = sum(1 for phrase in indicators["pain_amplification"] if phrase in user_text)
        if amplification_count > 0:
            score += 0.3
        
        # Check for consequence exploration
        consequence_count = sum(1 for phrase in indicators["consequence_exploration"] if phrase in user_text)
        if consequence_count > 0:
            score += 0.3
        
        return max(0.0, min(1.0, score))
    
    def _analyze_qualification(self, user_text: str, conversation_text: str) -> float:
        """Analyze qualification efforts (BANT)"""
        indicators = self.nepq_indicators["qualification"]
        score = 0.0
        qualification_areas = 0
        
        # Check each qualification area
        for area, phrases in indicators.items():
            if any(phrase in user_text for phrase in phrases):
                qualification_areas += 1
        
        # Score based on qualification coverage
        if qualification_areas >= 3:
            score = 1.0
        elif qualification_areas == 2:
            score = 0.7
        elif qualification_areas == 1:
            score = 0.4
        
        return score
    
    def _generate_nepq_findings(self, needs: float, emotions: float, pain: float, 
                               qualification: float, user_text: str) -> List[str]:
        """Generate specific findings for NEPQ assessment"""
        findings = []
        
        if needs < 0.5:
            findings.append("Low needs discovery - ask more open-ended questions about customer requirements")
        if emotions < 0.5:
            findings.append("Limited emotion recognition - acknowledge customer feelings and concerns")
        if pain < 0.5:
            findings.append("Insufficient pain identification - probe deeper into customer challenges")
        if qualification < 0.5:
            findings.append("Weak qualification - explore budget, authority, need, and timeline (BANT)")
        
        # Positive findings
        if needs > 0.8:
            findings.append("Excellent needs discovery with strong questioning technique")
        if emotions > 0.8:
            findings.append("Strong emotional intelligence and empathy demonstrated")
        if pain > 0.8:
            findings.append("Effective pain point identification and amplification")
        if qualification > 0.8:
            findings.append("Thorough qualification across multiple dimensions")
        
        return findings

class QuestionQualityAnalyzer:
    """Analyzes question quality and effectiveness"""
    
    def __init__(self):
        self.question_patterns = self._define_question_patterns()
    
    def _define_question_patterns(self) -> Dict[str, List[str]]:
        """Define patterns for different question types"""
        return {
            "open_ended": [
                r"what.*", r"how.*", r"why.*", r"when.*", r"where.*", 
                r"which.*", r"who.*", r"tell me about.*", r"describe.*",
                r"explain.*", r"walk me through.*", r"help me understand.*"
            ],
            "closed_ended": [
                r"do you.*", r"are you.*", r"is it.*", r"can you.*", 
                r"will you.*", r"would you.*", r"have you.*"
            ],
            "probing": [
                r"what else.*", r"anything else.*", r"what about.*", 
                r"how specifically.*", r"what happens when.*", r"give me an example.*"
            ],
            "leading": [
                r"don't you think.*", r"wouldn't you agree.*", r"isn't it true.*"
            ]
        }
    
    def analyze_question_quality(self, user_responses: List[str]) -> QuestionQualityAssessment:
        """Analyze quality of questions asked"""
        user_text = " ".join(user_responses).lower()
        
        # Extract questions
        questions = self._extract_questions(user_responses)
        
        if not questions:
            return QuestionQualityAssessment(
                open_question_ratio=0.0,
                probing_depth_score=0.0,
                question_relevance_score=0.0,
                follow_up_effectiveness=0.0,
                overall_quality_score=0.0,
                question_breakdown={"total": 0},
                improvement_suggestions=["Ask more questions to engage the customer"]
            )
        
        # Categorize questions
        question_breakdown = self._categorize_questions(questions)
        
        # Calculate metrics
        open_ratio = question_breakdown.get("open_ended", 0) / len(questions)
        probing_score = min(1.0, question_breakdown.get("probing", 0) / max(1, len(questions) * 0.3))
        relevance_score = self._assess_question_relevance(questions, user_text)
        follow_up_score = self._assess_follow_up_effectiveness(questions)
        
        # Calculate overall score
        overall_score = (open_ratio * 0.3 + probing_score * 0.3 + 
                        relevance_score * 0.2 + follow_up_score * 0.2)
        
        # Generate improvement suggestions
        suggestions = self._generate_question_improvements(
            question_breakdown, open_ratio, probing_score, relevance_score
        )
        
        return QuestionQualityAssessment(
            open_question_ratio=open_ratio,
            probing_depth_score=probing_score,
            question_relevance_score=relevance_score,
            follow_up_effectiveness=follow_up_score,
            overall_quality_score=overall_score,
            question_breakdown=question_breakdown,
            improvement_suggestions=suggestions
        )
    
    def _extract_questions(self, responses: List[str]) -> List[str]:
        """Extract questions from responses"""
        questions = []
        for response in responses:
            # Split by sentences and find questions
            sentences = re.split(r'[.!]', response)
            for sentence in sentences:
                if '?' in sentence:
                    questions.append(sentence.strip())
        return questions
    
    def _categorize_questions(self, questions: List[str]) -> Dict[str, int]:
        """Categorize questions by type"""
        breakdown = {"total": len(questions)}
        
        for question_type, patterns in self.question_patterns.items():
            count = 0
            for question in questions:
                question_lower = question.lower()
                if any(re.match(pattern, question_lower) for pattern in patterns):
                    count += 1
            breakdown[question_type] = count
        
        return breakdown
    
    def _assess_question_relevance(self, questions: List[str], context: str) -> float:
        """Assess relevance of questions to sales context"""
        if not questions:
            return 0.0
        
        sales_keywords = [
            "need", "problem", "challenge", "goal", "budget", "timeline",
            "decision", "process", "current", "solution", "improvement"
        ]
        
        relevant_count = 0
        for question in questions:
            question_lower = question.lower()
            if any(keyword in question_lower for keyword in sales_keywords):
                relevant_count += 1
        
        return relevant_count / len(questions)
    
    def _assess_follow_up_effectiveness(self, questions: List[str]) -> float:
        """Assess effectiveness of follow-up questions"""
        if len(questions) < 2:
            return 0.0
        
        follow_up_indicators = ["what else", "tell me more", "how specifically", "what about"]
        follow_up_count = 0
        
        for question in questions:
            question_lower = question.lower()
            if any(indicator in question_lower for indicator in follow_up_indicators):
                follow_up_count += 1
        
        return min(1.0, follow_up_count / (len(questions) * 0.3))
    
    def _generate_question_improvements(self, breakdown: Dict, open_ratio: float,
                                      probing_score: float, relevance_score: float) -> List[str]:
        """Generate improvement suggestions for questioning"""
        suggestions = []
        
        if open_ratio < 0.6:
            suggestions.append("Use more open-ended questions (what, how, why) to encourage detailed responses")
        
        if probing_score < 0.5:
            suggestions.append("Ask more probing follow-up questions to dig deeper into customer responses")
        
        if relevance_score < 0.7:
            suggestions.append("Focus questions more on sales-relevant topics (needs, challenges, goals)")
        
        if breakdown.get("leading", 0) > breakdown.get("open_ended", 0):
            suggestions.append("Avoid leading questions; let customers share their own thoughts")
        
        if breakdown.get("closed_ended", 0) > breakdown.get("open_ended", 0):
            suggestions.append("Balance closed questions with more open-ended exploration")
        
        return suggestions[:3]  # Top 3 suggestions

class ActiveListeningAnalyzer:
    """Analyzes active listening behaviors"""
    
    def __init__(self):
        self.listening_indicators = self._define_listening_indicators()
    
    def _define_listening_indicators(self) -> Dict[str, List[str]]:
        """Define indicators of active listening"""
        return {
            "acknowledgment": [
                "i hear you", "i understand", "that makes sense", "i see",
                "right", "okay", "yes", "absolutely", "exactly", "sure"
            ],
            "paraphrasing": [
                "so what you're saying is", "if i understand correctly", "let me make sure",
                "so you're telling me", "in other words", "to summarize", "what i hear is"
            ],
            "clarification": [
                "can you clarify", "what do you mean by", "help me understand",
                "could you elaborate", "tell me more about", "give me an example"
            ],
            "emotional_recognition": [
                "you sound", "it seems like you", "i can hear that", "you feel",
                "that must be", "i sense", "sounds frustrating", "sounds exciting"
            ],
            "reflection": [
                "reflecting on what you said", "based on what you shared", 
                "you mentioned", "earlier you said", "going back to"
            ]
        }
    
    def analyze_active_listening(self, user_responses: List[str], 
                               conversation_context: str = "") -> ActiveListeningAssessment:
        """Analyze active listening behaviors"""
        user_text = " ".join(user_responses).lower()
        
        # Analyze each listening behavior
        acknowledgment_score = self._analyze_acknowledgment(user_text)
        paraphrasing_score = self._analyze_paraphrasing(user_text)
        clarification_score = self._analyze_clarification(user_text)
        emotional_score = self._analyze_emotional_recognition(user_text)
        silence_score = self._analyze_silence_utilization(user_responses)
        
        # Calculate overall listening score
        overall_score = np.mean([
            acknowledgment_score, paraphrasing_score, clarification_score,
            emotional_score, silence_score
        ])
        
        # Identify demonstrated behaviors
        behaviors = self._identify_listening_behaviors(user_text)
        
        return ActiveListeningAssessment(
            acknowledgment_frequency=acknowledgment_score,
            paraphrasing_usage=paraphrasing_score,
            clarification_seeking=clarification_score,
            emotional_recognition=emotional_score,
            silence_utilization=silence_score,
            overall_listening_score=overall_score,
            listening_behaviors=behaviors
        )
    
    def _analyze_acknowledgment(self, user_text: str) -> float:
        """Analyze use of acknowledgment phrases"""
        indicators = self.listening_indicators["acknowledgment"]
        acknowledgment_count = sum(1 for phrase in indicators if phrase in user_text)
        
        # Score based on frequency (normalized)
        word_count = len(user_text.split())
        if word_count == 0:
            return 0.0
        
        ratio = acknowledgment_count / (word_count / 50)  # Per 50 words
        return min(1.0, ratio)
    
    def _analyze_paraphrasing(self, user_text: str) -> float:
        """Analyze use of paraphrasing techniques"""
        indicators = self.listening_indicators["paraphrasing"]
        paraphrasing_count = sum(1 for phrase in indicators if phrase in user_text)
        
        return min(1.0, paraphrasing_count / 2)  # Expect at least 2 instances
    
    def _analyze_clarification(self, user_text: str) -> float:
        """Analyze clarification-seeking behavior"""
        indicators = self.listening_indicators["clarification"]
        clarification_count = sum(1 for phrase in indicators if phrase in user_text)
        
        return min(1.0, clarification_count / 3)  # Expect some clarification
    
    def _analyze_emotional_recognition(self, user_text: str) -> float:
        """Analyze emotional recognition and acknowledgment"""
        indicators = self.listening_indicators["emotional_recognition"]
        emotion_count = sum(1 for phrase in indicators if phrase in user_text)
        
        return min(1.0, emotion_count / 2)
    
    def _analyze_silence_utilization(self, responses: List[str]) -> float:
        """Analyze appropriate use of silence (response length variation)"""
        if len(responses) < 2:
            return 0.5
        
        response_lengths = [len(response.split()) for response in responses]
        
        # Good listening involves varied response lengths
        length_variance = np.var(response_lengths)
        mean_length = np.mean(response_lengths)
        
        if mean_length == 0:
            return 0.0
        
        # Normalized variance score
        normalized_variance = length_variance / (mean_length ** 2)
        return min(1.0, normalized_variance * 2)
    
    def _identify_listening_behaviors(self, user_text: str) -> List[str]:
        """Identify specific listening behaviors demonstrated"""
        behaviors = []
        
        for behavior_type, indicators in self.listening_indicators.items():
            if any(indicator in user_text for indicator in indicators):
                behavior_name = behavior_type.replace("_", " ").title()
                behaviors.append(behavior_name)
        
        return behaviors

class AdvancedPerformanceAnalyzer:
    """Comprehensive performance analyzer combining all advanced techniques"""
    
    def __init__(self):
        self.nepq_analyzer = NEPQAnalyzer()
        self.question_analyzer = QuestionQualityAnalyzer()
        self.listening_analyzer = ActiveListeningAnalyzer()
    
    def comprehensive_analysis(self, conversation_data: Dict) -> Dict:
        """Perform comprehensive advanced performance analysis"""
        conversation_text = conversation_data.get("transcript", "")
        user_responses = conversation_data.get("user_responses", [])
        
        if not user_responses:
            # Extract user responses from transcript if not provided
            user_responses = self._extract_user_responses(conversation_text)
        
        # Perform all analyses
        nepq_assessment = self.nepq_analyzer.analyze_nepq_implementation(
            conversation_text, user_responses
        )
        
        question_assessment = self.question_analyzer.analyze_question_quality(
            user_responses
        )
        
        listening_assessment = self.listening_analyzer.analyze_active_listening(
            user_responses, conversation_text
        )
        
        # Calculate overall advanced performance score
        overall_score = np.mean([
            nepq_assessment.overall_nepq_score,
            question_assessment.overall_quality_score,
            listening_assessment.overall_listening_score
        ])
        
        # Generate comprehensive recommendations
        recommendations = self._generate_comprehensive_recommendations(
            nepq_assessment, question_assessment, listening_assessment
        )
        
        return {
            "conversation_id": conversation_data.get("id", "unknown"),
            "analysis_timestamp": datetime.now().isoformat(),
            "nepq_assessment": nepq_assessment.__dict__,
            "question_quality": question_assessment.__dict__,
            "active_listening": listening_assessment.__dict__,
            "overall_advanced_score": overall_score,
            "performance_level": self._determine_performance_level(overall_score),
            "comprehensive_recommendations": recommendations
        }
    
    def _extract_user_responses(self, conversation_text: str) -> List[str]:
        """Extract user responses from conversation transcript"""
        # Simple extraction - look for salesperson indicators
        lines = conversation_text.split('\n')
        user_responses = []
        
        for line in lines:
            line = line.strip()
            if line and not any(indicator in line.lower() for indicator in 
                              ['customer:', 'client:', 'prospect:']):
                user_responses.append(line)
        
        return user_responses
    
    def _determine_performance_level(self, score: float) -> str:
        """Determine performance level based on score"""
        if score >= 0.9:
            return "Expert"
        elif score >= 0.8:
            return "Advanced"
        elif score >= 0.7:
            return "Proficient"
        elif score >= 0.6:
            return "Developing"
        else:
            return "Beginner"
    
    def _generate_comprehensive_recommendations(self, nepq: NEPQAssessment,
                                             questions: QuestionQualityAssessment,
                                             listening: ActiveListeningAssessment) -> List[str]:
        """Generate comprehensive improvement recommendations"""
        recommendations = []
        
        # Add NEPQ recommendations
        recommendations.extend(nepq.specific_findings[:2])
        
        # Add question quality recommendations
        recommendations.extend(questions.improvement_suggestions[:2])
        
        # Add listening recommendations
        if listening.overall_listening_score < 0.7:
            recommendations.append("Improve active listening with more acknowledgment and paraphrasing")
        
        # Overall recommendations based on weakest area
        scores = {
            "NEPQ Selling": nepq.overall_nepq_score,
            "Question Quality": questions.overall_quality_score,
            "Active Listening": listening.overall_listening_score
        }
        
        weakest_area = min(scores, key=scores.get)
        if scores[weakest_area] < 0.6:
            recommendations.insert(0, f"Priority focus area: {weakest_area}")
        
        return recommendations[:5]  # Top 5 recommendations

def main():
    """Demo advanced performance analysis"""
    logger.info("Initializing Advanced Performance Analysis System")
    
    analyzer = AdvancedPerformanceAnalyzer()
    
    # Mock conversation data
    mock_conversation = {
        "id": "advanced_test_001",
        "transcript": """
        Salesperson: Hello! Thanks for taking the time to speak with me today. How are you doing?
        Customer: Good, thanks. I'm interested in learning more about your solution.
        Salesperson: That's great to hear. Before I tell you about what we offer, help me understand your current situation. What challenges are you facing with your current process?
        Customer: Well, we're spending too much time on manual data entry, and it's causing delays.
        Salesperson: I can see how that would be frustrating. Tell me more about these delays - how is this impacting your business?
        Customer: It's affecting our customer service response times and team morale is low.
        Salesperson: That sounds really challenging. What have you tried to address this so far?
        """,
        "user_responses": [
            "Hello! Thanks for taking the time to speak with me today. How are you doing?",
            "That's great to hear. Before I tell you about what we offer, help me understand your current situation. What challenges are you facing with your current process?",
            "I can see how that would be frustrating. Tell me more about these delays - how is this impacting your business?",
            "That sounds really challenging. What have you tried to address this so far?"
        ]
    }
    
    # Run comprehensive analysis
    results = analyzer.comprehensive_analysis(mock_conversation)
    
    logger.info("Analysis Results:")
    logger.info(f"- Overall Score: {results['overall_advanced_score']:.2f}")
    logger.info(f"- Performance Level: {results['performance_level']}")
    logger.info(f"- NEPQ Score: {results['nepq_assessment']['overall_nepq_score']:.2f}")
    logger.info(f"- Question Quality: {results['question_quality']['overall_quality_score']:.2f}")
    logger.info(f"- Active Listening: {results['active_listening']['overall_listening_score']:.2f}")
    
    logger.info("Top Recommendations:")
    for i, rec in enumerate(results['comprehensive_recommendations'], 1):
        logger.info(f"  {i}. {rec}")

if __name__ == "__main__":
    main()