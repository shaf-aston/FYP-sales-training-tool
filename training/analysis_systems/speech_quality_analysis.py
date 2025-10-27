"""
Speech Quality Analysis System
Implements speech clarity, murmuring/stuttering detection, and questioning style evaluation
"""
import json
import re
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import wave
import struct
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class SpeechClarityAssessment:
    """Assessment of speech clarity"""
    clarity_score: float
    articulation_score: float
    pace_score: float
    volume_consistency: float
    enunciation_quality: float
    clarity_issues: List[str]
    improvement_suggestions: List[str]

@dataclass
class DisfluencyAssessment:
    """Assessment of speech disfluencies (murmuring, stuttering)"""
    overall_fluency_score: float
    stuttering_frequency: float
    filler_word_ratio: float
    hesitation_count: int
    repetition_count: int
    prolongation_count: int
    disfluency_patterns: List[str]
    fluency_recommendations: List[str]

@dataclass
class QuestioningStyleAssessment:
    """Assessment of questioning style and effectiveness"""
    questioning_effectiveness: float
    intonation_appropriateness: float
    question_pacing: float
    emphasis_usage: float
    questioning_confidence: float
    style_characteristics: List[str]
    vocal_improvement_tips: List[str]

class SpeechClarityAnalyzer:
    """Analyzes speech clarity from audio and text"""
    
    def __init__(self):
        self.clarity_indicators = self._define_clarity_indicators()
        self.pace_thresholds = {"too_fast": 180, "optimal_min": 140, "optimal_max": 160, "too_slow": 120}
    
    def _define_clarity_indicators(self) -> Dict:
        """Define indicators for speech clarity assessment"""
        return {
            "clear_articulation": {
                "positive_patterns": [
                    r"\b\w+\b",  # Complete words
                    r"[.!?]",    # Clear sentence endings
                ],
                "negative_patterns": [
                    r"\w*'m\b",   # Contractions indicating rushed speech
                    r"\w*n't\b",  # More contractions
                    r"gonna", r"wanna", r"gotta"  # Informal contractions
                ]
            },
            "enunciation_quality": {
                "problem_patterns": [
                    r"th[^e]",     # Dropped 'th' sounds
                    r"\bda\b",     # 'da' instead of 'the'
                    r"\ban\b.*\ban\b",  # Repeated articles (sign of unclear speech)
                ],
                "quality_indicators": [
                    r"[aeiou]{2,}",  # Proper vowel sounds
                    r"consonant clusters"  # Well-pronounced consonants
                ]
            },
            "volume_consistency": {
                "inconsistency_markers": [
                    r"[A-Z]{2,}",     # All caps might indicate shouting
                    r"\.\.\.",        # Trailing off
                    r"whisper", r"loud", r"quiet"  # Volume descriptors
                ]
            }
        }
    
    def analyze_speech_clarity(self, transcript: str, audio_features: Dict = None) -> SpeechClarityAssessment:
        """Analyze speech clarity from transcript and optional audio features"""
        
        # Analyze articulation from transcript
        articulation_score = self._analyze_articulation(transcript)
        
        # Analyze pace from transcript and audio features
        pace_score = self._analyze_pace(transcript, audio_features)
        
        # Analyze volume consistency
        volume_score = self._analyze_volume_consistency(transcript, audio_features)
        
        # Analyze enunciation quality
        enunciation_score = self._analyze_enunciation(transcript)
        
        # Calculate overall clarity score
        clarity_score = np.mean([articulation_score, pace_score, volume_score, enunciation_score])
        
        # Identify specific issues
        clarity_issues = self._identify_clarity_issues(
            transcript, articulation_score, pace_score, volume_score, enunciation_score
        )
        
        # Generate improvement suggestions
        suggestions = self._generate_clarity_suggestions(clarity_issues, clarity_score)
        
        return SpeechClarityAssessment(
            clarity_score=clarity_score,
            articulation_score=articulation_score,
            pace_score=pace_score,
            volume_consistency=volume_score,
            enunciation_quality=enunciation_score,
            clarity_issues=clarity_issues,
            improvement_suggestions=suggestions
        )
    
    def _analyze_articulation(self, transcript: str) -> float:
        """Analyze articulation quality from transcript"""
        indicators = self.clarity_indicators["clear_articulation"]
        
        # Count clear word patterns
        clear_words = len(re.findall(r'\b[a-zA-Z]{3,}\b', transcript))
        total_words = len(transcript.split())
        
        if total_words == 0:
            return 0.0
        
        # Count problematic patterns
        negative_patterns = sum(
            len(re.findall(pattern, transcript, re.IGNORECASE))
            for pattern in indicators["negative_patterns"]
        )
        
        # Calculate score
        base_score = clear_words / total_words
        penalty = min(0.3, negative_patterns / total_words)
        
        return max(0.0, min(1.0, base_score - penalty))
    
    def _analyze_pace(self, transcript: str, audio_features: Dict = None) -> float:
        """Analyze speaking pace"""
        if audio_features and "speaking_rate" in audio_features:
            # Use actual speaking rate if available
            rate = audio_features["speaking_rate"]  # words per minute
            
            if rate < self.pace_thresholds["too_slow"]:
                return 0.4  # Too slow
            elif rate > self.pace_thresholds["too_fast"]:
                return 0.5  # Too fast
            elif self.pace_thresholds["optimal_min"] <= rate <= self.pace_thresholds["optimal_max"]:
                return 1.0  # Optimal
            else:
                return 0.7  # Acceptable
        
        # Estimate pace from transcript patterns
        word_count = len(transcript.split())
        
        # Look for pace indicators in text
        pace_indicators = {
            "rushed": [r"[.]{2,}", r"[,]{2,}", r"\w+\w+", r"quick", r"fast"],
            "slow": [r"\.\.\.", r"um+", r"uh+", r"slow", r"pause"]
        }
        
        rushed_count = sum(
            len(re.findall(pattern, transcript, re.IGNORECASE))
            for pattern in pace_indicators["rushed"]
        )
        
        slow_count = sum(
            len(re.findall(pattern, transcript, re.IGNORECASE))
            for pattern in pace_indicators["slow"]
        )
        
        if rushed_count > slow_count and rushed_count > word_count * 0.1:
            return 0.5  # Appears rushed
        elif slow_count > rushed_count and slow_count > word_count * 0.1:
            return 0.6  # Appears slow
        else:
            return 0.8  # Appears normal
    
    def _analyze_volume_consistency(self, transcript: str, audio_features: Dict = None) -> float:
        """Analyze volume consistency"""
        if audio_features and "volume_variance" in audio_features:
            variance = audio_features["volume_variance"]
            # Lower variance indicates better consistency
            return max(0.0, 1.0 - variance)
        
        # Analyze from transcript markers
        indicators = self.clarity_indicators["volume_consistency"]["inconsistency_markers"]
        
        inconsistency_count = sum(
            len(re.findall(pattern, transcript))
            for pattern in indicators
        )
        
        word_count = len(transcript.split())
        if word_count == 0:
            return 0.5
        
        inconsistency_ratio = inconsistency_count / word_count
        return max(0.0, 1.0 - inconsistency_ratio * 3)
    
    def _analyze_enunciation(self, transcript: str) -> float:
        """Analyze enunciation quality"""
        indicators = self.clarity_indicators["enunciation_quality"]
        
        # Count problematic patterns
        problem_count = sum(
            len(re.findall(pattern, transcript, re.IGNORECASE))
            for pattern in indicators["problem_patterns"]
        )
        
        word_count = len(transcript.split())
        if word_count == 0:
            return 0.5
        
        # Calculate score (fewer problems = better enunciation)
        problem_ratio = problem_count / word_count
        return max(0.0, 1.0 - problem_ratio * 2)
    
    def _identify_clarity_issues(self, transcript: str, articulation: float, pace: float,
                               volume: float, enunciation: float) -> List[str]:
        """Identify specific clarity issues"""
        issues = []
        
        if articulation < 0.6:
            issues.append("Poor articulation - words not clearly pronounced")
        if pace < 0.6:
            issues.append("Inappropriate speaking pace - too fast or too slow")
        if volume < 0.6:
            issues.append("Inconsistent volume levels")
        if enunciation < 0.6:
            issues.append("Poor enunciation - sounds not clearly formed")
        
        # Specific pattern-based issues
        if "gonna" in transcript.lower() or "wanna" in transcript.lower():
            issues.append("Casual contractions affecting clarity")
        
        if len(re.findall(r'[.]{3,}', transcript)) > 2:
            issues.append("Frequent trailing off or incomplete thoughts")
        
        return issues
    
    def _generate_clarity_suggestions(self, issues: List[str], overall_score: float) -> List[str]:
        """Generate improvement suggestions for clarity"""
        suggestions = []
        
        if overall_score < 0.5:
            suggestions.append("Focus on fundamental speech clarity exercises")
        
        for issue in issues:
            if "articulation" in issue.lower():
                suggestions.append("Practice pronunciation exercises and speak more deliberately")
            elif "pace" in issue.lower():
                suggestions.append("Practice controlling speaking speed - aim for 140-160 words per minute")
            elif "volume" in issue.lower():
                suggestions.append("Practice maintaining consistent volume throughout conversation")
            elif "enunciation" in issue.lower():
                suggestions.append("Focus on clearly forming each sound and syllable")
        
        if not suggestions:
            suggestions.append("Good speech clarity - continue current speaking style")
        
        return suggestions[:3]  # Limit to top 3 suggestions

class DisfluencyAnalyzer:
    """Analyzes speech disfluencies including stuttering and murmuring"""
    
    def __init__(self):
        self.filler_words = ["um", "uh", "er", "ah", "like", "you know", "basically", "actually"]
        self.disfluency_patterns = self._define_disfluency_patterns()
    
    def _define_disfluency_patterns(self) -> Dict:
        """Define patterns for different types of disfluencies"""
        return {
            "stuttering": {
                "sound_repetition": [r'\b(\w)\1{2,}', r'\b(\w{2})\1+'],  # Repeated sounds/syllables
                "word_repetition": [r'\b(\w+)\s+\1\b'],  # Repeated words
                "prolongation": [r'\b\w*[aeiou]{3,}\w*\b']  # Prolonged vowel sounds
            },
            "hesitation": {
                "filled_pauses": self.filler_words,
                "unfilled_pauses": [r'\.{2,}', r'-{2,}', r'\s{2,}'],
                "false_starts": [r'\b\w+\s+\.\.\.\s+\w+']  # Started word then restart
            },
            "revision": {
                "word_revision": [r'\b\w+\s+I mean\s+\w+', r'\b\w+\s+or rather\s+\w+'],
                "phrase_revision": [r'let me rephrase', r'what I meant was']
            }
        }
    
    def analyze_disfluency(self, transcript: str, audio_features: Dict = None) -> DisfluencyAssessment:
        """Analyze speech disfluencies"""
        
        # Count different types of disfluencies
        stuttering_freq = self._analyze_stuttering(transcript)
        filler_ratio = self._analyze_filler_words(transcript)
        hesitation_count = self._count_hesitations(transcript)
        repetition_count = self._count_repetitions(transcript)
        prolongation_count = self._count_prolongations(transcript)
        
        # Calculate overall fluency score
        fluency_score = self._calculate_fluency_score(
            stuttering_freq, filler_ratio, hesitation_count, repetition_count, prolongation_count
        )
        
        # Identify disfluency patterns
        patterns = self._identify_disfluency_patterns(
            transcript, stuttering_freq, filler_ratio, hesitation_count
        )
        
        # Generate recommendations
        recommendations = self._generate_fluency_recommendations(patterns, fluency_score)
        
        return DisfluencyAssessment(
            overall_fluency_score=fluency_score,
            stuttering_frequency=stuttering_freq,
            filler_word_ratio=filler_ratio,
            hesitation_count=hesitation_count,
            repetition_count=repetition_count,
            prolongation_count=prolongation_count,
            disfluency_patterns=patterns,
            fluency_recommendations=recommendations
        )
    
    def _analyze_stuttering(self, transcript: str) -> float:
        """Analyze stuttering frequency"""
        patterns = self.disfluency_patterns["stuttering"]
        
        total_stutters = 0
        for category, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.findall(pattern, transcript, re.IGNORECASE)
                total_stutters += len(matches)
        
        word_count = len(transcript.split())
        if word_count == 0:
            return 0.0
        
        return total_stutters / word_count  # Frequency as ratio
    
    def _analyze_filler_words(self, transcript: str) -> float:
        """Analyze filler word usage"""
        transcript_lower = transcript.lower()
        
        filler_count = sum(
            transcript_lower.count(filler) for filler in self.filler_words
        )
        
        word_count = len(transcript.split())
        if word_count == 0:
            return 0.0
        
        return filler_count / word_count
    
    def _count_hesitations(self, transcript: str) -> int:
        """Count hesitation markers"""
        patterns = self.disfluency_patterns["hesitation"]
        
        hesitation_count = 0
        
        # Count filled pauses (already counted in filler words)
        # Count unfilled pauses
        for pattern in patterns["unfilled_pauses"]:
            hesitation_count += len(re.findall(pattern, transcript))
        
        # Count false starts
        for pattern in patterns["false_starts"]:
            hesitation_count += len(re.findall(pattern, transcript))
        
        return hesitation_count
    
    def _count_repetitions(self, transcript: str) -> int:
        """Count word/phrase repetitions"""
        repetition_patterns = self.disfluency_patterns["stuttering"]["word_repetition"]
        
        repetition_count = 0
        for pattern in repetition_patterns:
            repetition_count += len(re.findall(pattern, transcript, re.IGNORECASE))
        
        return repetition_count
    
    def _count_prolongations(self, transcript: str) -> int:
        """Count sound prolongations"""
        prolongation_patterns = self.disfluency_patterns["stuttering"]["prolongation"]
        
        prolongation_count = 0
        for pattern in prolongation_patterns:
            prolongation_count += len(re.findall(pattern, transcript, re.IGNORECASE))
        
        return prolongation_count
    
    def _calculate_fluency_score(self, stuttering: float, filler_ratio: float,
                               hesitations: int, repetitions: int, prolongations: int) -> float:
        """Calculate overall fluency score"""
        # Start with perfect score and deduct for disfluencies
        score = 1.0
        
        # Penalties for different disfluency types
        score -= min(0.3, stuttering * 10)  # Stuttering penalty
        score -= min(0.3, filler_ratio * 5)  # Filler word penalty
        score -= min(0.2, hesitations * 0.05)  # Hesitation penalty
        score -= min(0.1, repetitions * 0.1)  # Repetition penalty
        score -= min(0.1, prolongations * 0.1)  # Prolongation penalty
        
        return max(0.0, score)
    
    def _identify_disfluency_patterns(self, transcript: str, stuttering: float,
                                    filler_ratio: float, hesitations: int) -> List[str]:
        """Identify specific disfluency patterns"""
        patterns = []
        
        if stuttering > 0.02:  # More than 2% stuttering
            patterns.append("Frequent stuttering or sound repetitions")
        
        if filler_ratio > 0.05:  # More than 5% filler words
            patterns.append("Excessive use of filler words (um, uh, like)")
        
        if hesitations > 3:
            patterns.append("Frequent hesitations and false starts")
        
        # Check for specific patterns
        if "you know" in transcript.lower():
            patterns.append("Overuse of 'you know' as filler")
        
        if len(re.findall(r'like\s+', transcript.lower())) > 2:
            patterns.append("Overuse of 'like' as filler")
        
        return patterns
    
    def _generate_fluency_recommendations(self, patterns: List[str], fluency_score: float) -> List[str]:
        """Generate fluency improvement recommendations"""
        recommendations = []
        
        if fluency_score < 0.6:
            recommendations.append("Practice fluency exercises to reduce overall disfluencies")
        
        for pattern in patterns:
            if "stuttering" in pattern.lower():
                recommendations.append("Practice slow, controlled speech to reduce stuttering")
            elif "filler" in pattern.lower():
                recommendations.append("Practice pausing silently instead of using filler words")
            elif "hesitation" in pattern.lower():
                recommendations.append("Prepare key points in advance to reduce hesitations")
        
        if not recommendations:
            recommendations.append("Good speech fluency - maintain current speaking style")
        
        return recommendations[:3]

class QuestioningStyleAnalyzer:
    """Analyzes questioning style and vocal effectiveness"""
    
    def __init__(self):
        self.questioning_patterns = self._define_questioning_patterns()
        self.intonation_markers = self._define_intonation_markers()
    
    def _define_questioning_patterns(self) -> Dict:
        """Define patterns for effective questioning"""
        return {
            "open_ended": {
                "starters": ["what", "how", "why", "when", "where", "which", "who"],
                "phrases": ["tell me about", "describe", "explain", "help me understand"]
            },
            "probing": {
                "follow_ups": ["what else", "tell me more", "how specifically", "what about"],
                "clarification": ["what do you mean", "can you elaborate", "give me an example"]
            },
            "leading": {
                "patterns": ["don't you think", "wouldn't you agree", "isn't it true"],
                "assumptive": ["when you", "after you", "once you"]
            }
        }
    
    def _define_intonation_markers(self) -> Dict:
        """Define markers for intonation patterns in text"""
        return {
            "rising_intonation": [r'\?', r'right\?', r'okay\?'],  # Questions
            "emphatic": [r'[A-Z]{2,}', r'really\s+\w+', r'very\s+\w+'],  # Emphasis
            "uncertain": [r'maybe', r'I think', r'perhaps', r'possibly'],
            "confident": [r'definitely', r'absolutely', r'certainly', r'clearly']
        }
    
    def analyze_questioning_style(self, transcript: str, user_responses: List[str]) -> QuestioningStyleAssessment:
        """Analyze questioning style effectiveness"""
        
        user_text = " ".join(user_responses).lower()
        
        # Extract questions from responses
        questions = self._extract_questions(user_responses)
        
        # Analyze different aspects
        effectiveness = self._analyze_questioning_effectiveness(questions, user_text)
        intonation = self._analyze_intonation_appropriateness(questions, user_text)
        pacing = self._analyze_question_pacing(questions, user_responses)
        emphasis = self._analyze_emphasis_usage(user_text)
        confidence = self._analyze_questioning_confidence(user_text)
        
        # Identify style characteristics
        characteristics = self._identify_style_characteristics(questions, user_text)
        
        # Generate improvement tips
        tips = self._generate_vocal_tips(effectiveness, intonation, confidence, characteristics)
        
        return QuestioningStyleAssessment(
            questioning_effectiveness=effectiveness,
            intonation_appropriateness=intonation,
            question_pacing=pacing,
            emphasis_usage=emphasis,
            questioning_confidence=confidence,
            style_characteristics=characteristics,
            vocal_improvement_tips=tips
        )
    
    def _extract_questions(self, responses: List[str]) -> List[str]:
        """Extract questions from responses"""
        questions = []
        for response in responses:
            sentences = re.split(r'[.!]', response)
            for sentence in sentences:
                if '?' in sentence:
                    questions.append(sentence.strip())
        return questions
    
    def _analyze_questioning_effectiveness(self, questions: List[str], user_text: str) -> float:
        """Analyze overall questioning effectiveness"""
        if not questions:
            return 0.0
        
        effectiveness_score = 0.0
        
        # Analyze question types
        open_ended_count = 0
        probing_count = 0
        leading_count = 0
        
        for question in questions:
            question_lower = question.lower()
            
            # Check for open-ended questions
            open_patterns = self.questioning_patterns["open_ended"]
            if any(starter in question_lower for starter in open_patterns["starters"]) or \
               any(phrase in question_lower for phrase in open_patterns["phrases"]):
                open_ended_count += 1
            
            # Check for probing questions
            probing_patterns = self.questioning_patterns["probing"]
            if any(phrase in question_lower for phrase in probing_patterns["follow_ups"]) or \
               any(phrase in question_lower for phrase in probing_patterns["clarification"]):
                probing_count += 1
            
            # Check for leading questions (negative)
            leading_patterns = self.questioning_patterns["leading"]
            if any(pattern in question_lower for pattern in leading_patterns["patterns"]):
                leading_count += 1
        
        total_questions = len(questions)
        
        # Calculate effectiveness based on question mix
        open_ratio = open_ended_count / total_questions
        probing_ratio = probing_count / total_questions
        leading_ratio = leading_count / total_questions
        
        effectiveness_score = (open_ratio * 0.4 + probing_ratio * 0.3 + 
                             max(0, 0.3 - leading_ratio))  # Penalty for leading questions
        
        return min(1.0, effectiveness_score)
    
    def _analyze_intonation_appropriateness(self, questions: List[str], user_text: str) -> float:
        """Analyze appropriateness of intonation patterns"""
        markers = self.intonation_markers
        
        # Count intonation markers
        rising_count = sum(
            len(re.findall(pattern, user_text))
            for pattern in markers["rising_intonation"]
        )
        
        emphatic_count = sum(
            len(re.findall(pattern, user_text))
            for pattern in markers["emphatic"]
        )
        
        # Score based on appropriate use
        word_count = len(user_text.split())
        if word_count == 0:
            return 0.5
        
        # Good intonation has moderate use of emphasis and appropriate question markers
        rising_ratio = rising_count / word_count
        emphatic_ratio = emphatic_count / word_count
        
        # Ideal ratios
        ideal_rising = 0.05  # About 5% question markers
        ideal_emphatic = 0.02  # About 2% emphasis
        
        rising_score = 1.0 - abs(rising_ratio - ideal_rising) / ideal_rising
        emphatic_score = 1.0 - abs(emphatic_ratio - ideal_emphatic) / ideal_emphatic
        
        return max(0.0, (rising_score + emphatic_score) / 2)
    
    def _analyze_question_pacing(self, questions: List[str], responses: List[str]) -> float:
        """Analyze pacing of questions within responses"""
        if not questions or not responses:
            return 0.5
        
        # Calculate questions per response
        questions_per_response = len(questions) / len(responses)
        
        # Ideal pacing: 1-2 questions per response
        if 1.0 <= questions_per_response <= 2.0:
            return 1.0
        elif 0.5 <= questions_per_response < 1.0 or 2.0 < questions_per_response <= 3.0:
            return 0.7
        else:
            return 0.4
    
    def _analyze_emphasis_usage(self, user_text: str) -> float:
        """Analyze appropriate use of emphasis"""
        markers = self.intonation_markers
        
        emphatic_count = sum(
            len(re.findall(pattern, user_text))
            for pattern in markers["emphatic"]
        )
        
        word_count = len(user_text.split())
        if word_count == 0:
            return 0.5
        
        emphasis_ratio = emphatic_count / word_count
        
        # Appropriate emphasis: 1-3% of words
        if 0.01 <= emphasis_ratio <= 0.03:
            return 1.0
        elif 0.005 <= emphasis_ratio < 0.01 or 0.03 < emphasis_ratio <= 0.05:
            return 0.7
        else:
            return 0.4
    
    def _analyze_questioning_confidence(self, user_text: str) -> float:
        """Analyze confidence in questioning"""
        markers = self.intonation_markers
        
        confident_count = sum(
            len(re.findall(pattern, user_text))
            for pattern in markers["confident"]
        )
        
        uncertain_count = sum(
            len(re.findall(pattern, user_text))
            for pattern in markers["uncertain"]
        )
        
        # Calculate confidence ratio
        total_confidence_markers = confident_count + uncertain_count
        if total_confidence_markers == 0:
            return 0.7  # Neutral confidence
        
        confidence_ratio = confident_count / total_confidence_markers
        return confidence_ratio
    
    def _identify_style_characteristics(self, questions: List[str], user_text: str) -> List[str]:
        """Identify specific questioning style characteristics"""
        characteristics = []
        
        if not questions:
            characteristics.append("Limited questioning approach")
            return characteristics
        
        # Analyze question distribution
        open_ended = sum(1 for q in questions if any(starter in q.lower() 
                        for starter in self.questioning_patterns["open_ended"]["starters"]))
        
        if open_ended / len(questions) > 0.7:
            characteristics.append("Strong open-ended questioning style")
        elif open_ended / len(questions) < 0.3:
            characteristics.append("Relies heavily on closed questions")
        
        # Check for probing depth
        probing_indicators = ["tell me more", "what else", "how specifically"]
        if any(indicator in user_text for indicator in probing_indicators):
            characteristics.append("Good probing and follow-up technique")
        
        # Check for confidence markers
        if "definitely" in user_text or "certainly" in user_text:
            characteristics.append("Confident questioning style")
        elif "maybe" in user_text or "perhaps" in user_text:
            characteristics.append("Tentative questioning approach")
        
        return characteristics
    
    def _generate_vocal_tips(self, effectiveness: float, intonation: float,
                           confidence: float, characteristics: List[str]) -> List[str]:
        """Generate vocal improvement tips"""
        tips = []
        
        if effectiveness < 0.6:
            tips.append("Use more open-ended questions to encourage detailed responses")
        
        if intonation < 0.6:
            tips.append("Work on vocal intonation - use rising tone for questions")
        
        if confidence < 0.6:
            tips.append("Speak with more confidence - avoid uncertain language")
        
        # Specific tips based on characteristics
        for char in characteristics:
            if "closed questions" in char:
                tips.append("Balance closed questions with more exploratory open questions")
            elif "tentative" in char:
                tips.append("Project more authority and confidence in your questioning")
        
        if not tips:
            tips.append("Good questioning style - continue developing vocal variety")
        
        return tips[:3]

class ComprehensiveSpeechAnalyzer:
    """Comprehensive speech quality analyzer combining all components"""
    
    def __init__(self):
        self.clarity_analyzer = SpeechClarityAnalyzer()
        self.disfluency_analyzer = DisfluencyAnalyzer()
        self.questioning_analyzer = QuestioningStyleAnalyzer()
    
    def comprehensive_speech_analysis(self, conversation_data: Dict) -> Dict:
        """Perform comprehensive speech quality analysis"""
        transcript = conversation_data.get("transcript", "")
        user_responses = conversation_data.get("user_responses", [])
        audio_features = conversation_data.get("audio_features", {})
        
        # Perform all analyses
        clarity_assessment = self.clarity_analyzer.analyze_speech_clarity(transcript, audio_features)
        disfluency_assessment = self.disfluency_analyzer.analyze_disfluency(transcript, audio_features)
        questioning_assessment = self.questioning_analyzer.analyze_questioning_style(transcript, user_responses)
        
        # Calculate overall speech quality score
        overall_score = np.mean([
            clarity_assessment.clarity_score,
            disfluency_assessment.overall_fluency_score,
            questioning_assessment.questioning_effectiveness
        ])
        
        # Generate comprehensive recommendations
        all_recommendations = []
        all_recommendations.extend(clarity_assessment.improvement_suggestions)
        all_recommendations.extend(disfluency_assessment.fluency_recommendations)
        all_recommendations.extend(questioning_assessment.vocal_improvement_tips)
        
        # Remove duplicates and prioritize
        unique_recommendations = list(dict.fromkeys(all_recommendations))[:5]
        
        return {
            "conversation_id": conversation_data.get("id", "unknown"),
            "analysis_timestamp": datetime.now().isoformat(),
            "speech_clarity": clarity_assessment.__dict__,
            "disfluency_analysis": disfluency_assessment.__dict__,
            "questioning_style": questioning_assessment.__dict__,
            "overall_speech_score": overall_score,
            "speech_quality_level": self._determine_speech_level(overall_score),
            "comprehensive_recommendations": unique_recommendations
        }
    
    def _determine_speech_level(self, score: float) -> str:
        """Determine speech quality level"""
        if score >= 0.9:
            return "Excellent"
        elif score >= 0.8:
            return "Very Good"
        elif score >= 0.7:
            return "Good"
        elif score >= 0.6:
            return "Fair"
        else:
            return "Needs Improvement"

def main():
    """Demo speech quality analysis"""
    logger.info("Initializing Speech Quality Analysis System")
    
    analyzer = ComprehensiveSpeechAnalyzer()
    
    # Mock conversation data
    mock_conversation = {
        "id": "speech_test_001",
        "transcript": "Um, hello there. Thanks for, uh, taking the time today. What challenges are you facing? Tell me more about that. How specifically does that impact your business?",
        "user_responses": [
            "Um, hello there. Thanks for, uh, taking the time today.",
            "What challenges are you facing? Tell me more about that.",
            "How specifically does that impact your business?"
        ],
        "audio_features": {
            "speaking_rate": 145,  # words per minute
            "volume_variance": 0.2
        }
    }
    
    # Run comprehensive analysis
    results = analyzer.comprehensive_speech_analysis(mock_conversation)
    
    logger.info("Speech Quality Analysis Results:")
    logger.info(f"- Overall Score: {results['overall_speech_score']:.2f}")
    logger.info(f"- Speech Level: {results['speech_quality_level']}")
    logger.info(f"- Clarity Score: {results['speech_clarity']['clarity_score']:.2f}")
    logger.info(f"- Fluency Score: {results['disfluency_analysis']['overall_fluency_score']:.2f}")
    logger.info(f"- Questioning Score: {results['questioning_style']['questioning_effectiveness']:.2f}")
    
    logger.info("Top Recommendations:")
    for i, rec in enumerate(results['comprehensive_recommendations'], 1):
        logger.info(f"  {i}. {rec}")

if __name__ == "__main__":
    main()