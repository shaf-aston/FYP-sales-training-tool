"""
Sales Process Analyzer Component
Specialized analyzer for sales methodology and process adherence
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from .feedback_models import SalesProcessAnalysis, SalesPhase

logger = logging.getLogger(__name__)

class SalesProcessAnalyzer:
    """
    Specialized analyzer for sales process methodology and effectiveness
    Focuses on sales phase identification, process adherence, and technique usage
    """
    
    def __init__(self):
        """Initialize sales process analyzer"""
        self.phase_keywords = {
            SalesPhase.OPENING: [
                "hello", "hi", "good morning", "good afternoon", "introduction",
                "my name is", "calling from", "reaching out", "how are you"
            ],
            SalesPhase.DISCOVERY: [
                "tell me about", "what are", "how do you", "current situation",
                "challenge", "problem", "need", "goal", "objective", "pain point",
                "struggle", "difficulty", "concern", "issue"
            ],
            SalesPhase.PRESENTATION: [
                "solution", "product", "service", "feature", "benefit", "advantage",
                "can help", "offer", "provide", "deliver", "recommend", "suggest"
            ],
            SalesPhase.HANDLING_OBJECTIONS: [
                "but", "however", "concern", "issue", "worry", "problem",
                "understand", "appreciate", "i see your point", "feel", "felt", "found"
            ],
            SalesPhase.CLOSING: [
                "next step", "move forward", "agreement", "contract", "sign up",
                "get started", "schedule", "meeting", "ready to", "would you like",
                "shall we", "commit", "decide", "proceed"
            ],
            SalesPhase.FOLLOW_UP: [
                "follow up", "next contact", "schedule", "reminder", "check in",
                "touch base", "circle back", "follow through"
            ]
        }
        
        self.sales_techniques = {
            "consultative_selling": [
                "understand", "help you", "based on what you've said", "sounds like",
                "it seems", "i hear that", "let me make sure i understand"
            ],
            "benefit_focused": [
                "benefit", "advantage", "save time", "save money", "improve",
                "increase", "reduce", "better", "faster", "easier"
            ],
            "objection_handling": [
                "feel, felt, found", "understand your concern", "that's a good point",
                "let me address that", "what if", "consider this", "have you thought"
            ],
            "assumptive_closing": [
                "when we get started", "once you begin", "after you sign up",
                "when would be a good time", "which option", "how many"
            ],
            "trial_closing": [
                "how does that sound", "what do you think", "make sense",
                "agree with that", "work for you", "interested in"
            ]
        }
        
        logger.info("✅ Sales Process Analyzer initialized")
    
    def analyze(self, conversation_history: List[Dict], persona_data: Optional[Dict] = None) -> SalesProcessAnalysis:
        """
        Analyze sales process adherence and effectiveness
        
        Args:
            conversation_history: List of conversation exchanges
            persona_data: Optional persona information for context
            
        Returns:
            SalesProcessAnalysis with detailed process breakdown
        """
        try:
            if not conversation_history:
                return SalesProcessAnalysis(
                    phases_covered=[],
                    phase_effectiveness={},
                    sales_techniques_used=[],
                    process_score=0.0,
                    missing_phases=list(SalesPhase),
                    recommendations=[]
                )
            
            logger.info(f"Analyzing sales process in {len(conversation_history)} exchanges")
            
            # Extract user messages
            user_messages = self._extract_user_messages(conversation_history)
            
            # Identify phases covered
            phases_covered, phase_transitions = self._identify_phases(user_messages)
            
            # Calculate phase effectiveness
            phase_effectiveness = self._calculate_phase_effectiveness(phases_covered, phase_transitions)
            
            # Identify sales techniques used
            sales_techniques_used = self._identify_techniques(user_messages)
            
            # Calculate overall process score
            process_score = self._calculate_process_score(phases_covered, phase_effectiveness, sales_techniques_used)
            
            # Identify missing phases
            missing_phases = self._identify_missing_phases(phases_covered)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(phases_covered, missing_phases, sales_techniques_used)
            
            analysis = SalesProcessAnalysis(
                phases_covered=phases_covered,
                phase_effectiveness=phase_effectiveness,
                sales_techniques_used=sales_techniques_used,
                process_score=process_score,
                missing_phases=missing_phases,
                recommendations=recommendations
            )
            
            logger.info(f"Sales process analysis complete: {len(phases_covered)} phases covered, "
                       f"process score {process_score:.1f}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Sales process analysis failed: {e}")
            return SalesProcessAnalysis(
                phases_covered=[],
                phase_effectiveness={},
                sales_techniques_used=[],
                process_score=0.0,
                missing_phases=list(SalesPhase),
                recommendations=["Analysis failed - please try again"]
            )
    
    def _extract_user_messages(self, conversation_history: List[Dict]) -> List[str]:
        """Extract user messages from conversation history"""
        user_messages = []
        
        for exchange in conversation_history:
            if 'user_message' in exchange:
                user_messages.append(exchange['user_message'])
            elif 'user' in exchange:
                user_messages.append(exchange['user'])
            elif 'human' in exchange:
                user_messages.append(exchange['human'])
        
        return [msg.strip() for msg in user_messages if msg and msg.strip()]
    
    def _identify_phases(self, user_messages: List[str]) -> Tuple[List[SalesPhase], List[Dict]]:
        """Identify sales phases covered and their transitions"""
        phases_covered = []
        phase_transitions = []
        current_phase = None
        
        for i, message in enumerate(user_messages):
            message_lower = message.lower()
            detected_phase = None
            
            # Check each phase for keywords
            for phase, keywords in self.phase_keywords.items():
                if any(keyword in message_lower for keyword in keywords):
                    detected_phase = phase
                    break
            
            # Track phase transitions
            if detected_phase and detected_phase != current_phase:
                if current_phase is not None:
                    phase_transitions.append({
                        'from': current_phase,
                        'to': detected_phase,
                        'message_index': i,
                        'transition_text': message[:100] + '...' if len(message) > 100 else message
                    })
                
                current_phase = detected_phase
                
                # Add to covered phases if not already there
                if detected_phase not in phases_covered:
                    phases_covered.append(detected_phase)
        
        # If no phases detected, try to infer from content patterns
        if not phases_covered:
            phases_covered = self._infer_phases_from_patterns(user_messages)
        
        return phases_covered, phase_transitions
    
    def _infer_phases_from_patterns(self, user_messages: List[str]) -> List[SalesPhase]:
        """Infer phases from message patterns when direct keywords aren't found"""
        phases = []
        all_text = ' '.join(user_messages).lower()
        
        # Simple pattern-based inference
        if any(word in all_text for word in ['hello', 'hi', 'introduce']):
            phases.append(SalesPhase.OPENING)
        
        if any(word in all_text for word in ['what', 'how', 'tell me', 'need', 'problem']):
            phases.append(SalesPhase.DISCOVERY)
        
        if any(word in all_text for word in ['solution', 'help', 'benefit', 'offer']):
            phases.append(SalesPhase.PRESENTATION)
        
        if any(word in all_text for word in ['but', 'however', 'concern', 'worry']):
            phases.append(SalesPhase.HANDLING_OBJECTIONS)
        
        if any(word in all_text for word in ['next', 'ready', 'start', 'sign']):
            phases.append(SalesPhase.CLOSING)
        
        return phases
    
    def _calculate_phase_effectiveness(self, phases_covered: List[SalesPhase], 
                                     phase_transitions: List[Dict]) -> Dict[str, float]:
        """Calculate effectiveness score for each phase"""
        effectiveness = {}
        
        for phase in SalesPhase:
            if phase in phases_covered:
                # Base score for covering the phase
                score = 50.0
                
                # Bonus for proper sequencing (earlier phases get higher scores)
                phase_order = list(SalesPhase)
                if phase in phase_order:
                    order_bonus = (len(phase_order) - phase_order.index(phase)) * 5
                    score += order_bonus
                
                # Bonus for smooth transitions
                transition_count = sum(1 for t in phase_transitions 
                                     if t['to'] == phase or t['from'] == phase)
                if transition_count > 0:
                    score += 10
                
                effectiveness[phase.value] = min(score, 100.0)
            else:
                effectiveness[phase.value] = 0.0
        
        return effectiveness
    
    def _identify_techniques(self, user_messages: List[str]) -> List[str]:
        """Identify sales techniques used in the conversation"""
        techniques_used = []
        all_text = ' '.join(user_messages).lower()
        
        for technique, keywords in self.sales_techniques.items():
            if any(keyword in all_text for keyword in keywords):
                techniques_used.append(technique)
        
        return techniques_used
    
    def _calculate_process_score(self, phases_covered: List[SalesPhase], 
                               phase_effectiveness: Dict[str, float],
                               techniques_used: List[str]) -> float:
        """Calculate overall sales process effectiveness score"""
        score = 0.0
        
        # Phase coverage score (40% weight)
        total_phases = len(SalesPhase)
        coverage_ratio = len(phases_covered) / total_phases
        phase_coverage_score = coverage_ratio * 40
        score += phase_coverage_score
        
        # Phase effectiveness score (35% weight)
        if phases_covered:
            avg_effectiveness = sum(phase_effectiveness[phase.value] for phase in phases_covered) / len(phases_covered)
            effectiveness_score = (avg_effectiveness / 100) * 35
            score += effectiveness_score
        
        # Technique usage score (25% weight)
        total_techniques = len(self.sales_techniques)
        technique_ratio = len(techniques_used) / total_techniques
        technique_score = technique_ratio * 25
        score += technique_score
        
        return min(score, 100.0)
    
    def _identify_missing_phases(self, phases_covered: List[SalesPhase]) -> List[SalesPhase]:
        """Identify which sales phases were not covered"""
        return [phase for phase in SalesPhase if phase not in phases_covered]
    
    def _generate_recommendations(self, phases_covered: List[SalesPhase], 
                                missing_phases: List[SalesPhase],
                                techniques_used: List[str]) -> List[str]:
        """Generate recommendations for sales process improvement"""
        recommendations = []
        
        # Missing phases recommendations
        if missing_phases:
            phase_names = [phase.value.replace('_', ' ').title() for phase in missing_phases]
            recommendations.append(f"Practice these missing phases: {', '.join(phase_names)}")
        
        # Process flow recommendations
        if len(phases_covered) < 3:
            recommendations.append("Focus on completing a full sales process cycle")
        
        # Technique recommendations
        missing_techniques = [tech for tech in self.sales_techniques.keys() if tech not in techniques_used]
        if missing_techniques:
            technique_names = [tech.replace('_', ' ').title() for tech in missing_techniques[:2]]
            recommendations.append(f"Practice these sales techniques: {', '.join(technique_names)}")
        
        # Specific recommendations based on what's missing
        if SalesPhase.CLOSING not in phases_covered:
            recommendations.append("Always attempt to close the conversation with a clear next step")
        
        if SalesPhase.DISCOVERY not in phases_covered:
            recommendations.append("Spend more time understanding customer needs before presenting solutions")
        
        if not techniques_used:
            recommendations.append("Incorporate proven sales techniques like consultative selling and benefit focus")
        
        return recommendations[:4]  # Limit to top 4 recommendations
    
    def get_process_insights(self, analysis: SalesProcessAnalysis) -> Dict[str, Any]:
        """Generate insights and detailed analysis from sales process results"""
        insights = {
            'process_completeness': f"{len(analysis.phases_covered)}/{len(SalesPhase)} phases completed",
            'process_score_interpretation': self._interpret_process_score(analysis.process_score),
            'technique_diversity': f"{len(analysis.sales_techniques_used)} techniques demonstrated",
            'strengths': [],
            'critical_gaps': []
        }
        
        # Identify strengths
        if analysis.process_score >= 70:
            insights['strengths'].append("Strong overall sales process adherence")
        
        if len(analysis.phases_covered) >= 4:
            insights['strengths'].append("Comprehensive phase coverage")
        
        if len(analysis.sales_techniques_used) >= 3:
            insights['strengths'].append("Good technique diversity")
        
        # Identify critical gaps
        if not analysis.phases_covered:
            insights['critical_gaps'].append("No sales process phases identified")
        
        if SalesPhase.CLOSING not in analysis.phases_covered:
            insights['critical_gaps'].append("Missing closing phase - no attempt to move forward")
        
        if SalesPhase.DISCOVERY not in analysis.phases_covered:
            insights['critical_gaps'].append("Missing discovery phase - insufficient customer understanding")
        
        if len(analysis.sales_techniques_used) == 0:
            insights['critical_gaps'].append("No sales techniques demonstrated")
        
        return insights
    
    def _interpret_process_score(self, score: float) -> str:
        """Interpret the process score into a descriptive rating"""
        if score >= 85:
            return "Excellent - Professional sales process execution"
        elif score >= 70:
            return "Good - Solid process with room for refinement"
        elif score >= 55:
            return "Adequate - Basic process but missing key elements"
        elif score >= 40:
            return "Needs Improvement - Significant process gaps"
        else:
            return "Poor - Sales process not followed"