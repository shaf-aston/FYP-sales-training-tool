"""
Advanced Audio Analysis Service - Refactored Orchestration Layer
Coordinates modular audio analysis components for comprehensive sales training insights
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# Import modular components
from .audio_analysis_models import (
    AdvancedAudioAnalysis, TimestampedSegment, Speaker, ContextSection,
    RolePlayBlock, TrainingAnnotation, SpeakerRole, RolePlayPhase
)
from .speaker_analyzer import SpeakerAnalyzer
from .context_analyzer import ContextAnalyzer
from .roleplay_analyzer import RolePlayAnalyzer
from .training_annotator import TrainingAnnotator

logger = logging.getLogger(__name__)

# Legacy compatibility - re-export enums
SpeakerRole = SpeakerRole
RolePlayPhase = RolePlayPhase
    CHALLENGER_SALE = "challenger_sale"


@dataclass
class Speaker:
    """Speaker identification and characteristics"""
    id: str
    role: SpeakerRole
    name: Optional[str] = None
    characteristics: Dict[str, Any] = None
    confidence: float = 0.0
    speaking_time: float = 0.0
    turn_count: int = 0
    
    def __post_init__(self):
        if self.characteristics is None:
            self.characteristics = {}


@dataclass
class TimestampedSegment:
    """Timestamped audio/text segment"""
    start_time: float
    end_time: float
    text: str
    speaker_id: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class ContextSection:
    """Context section with thematic grouping"""
    id: str
    title: str
    start_time: float
    end_time: float
    phase: RolePlayPhase
    segments: List[TimestampedSegment]
    summary: str = ""
    key_points: List[str] = None
    techniques_used: List[str] = None
    effectiveness_score: float = 0.0
    
    def __post_init__(self):
        if self.key_points is None:
            self.key_points = []
        if self.techniques_used is None:
            self.techniques_used = []
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class RolePlayBlock:
    """Role-play interaction block with comprehensive metadata"""
    id: str
    title: str
    start_time: float
    end_time: float
    phase: RolePlayPhase
    participants: List[str]
    context_sections: List[ContextSection]
    training_annotations: List['TrainingAnnotation']
    performance_metrics: Dict[str, float]
    scenario_type: str = "general_sales"
    difficulty_level: str = "intermediate"
    learning_objectives: List[str] = None
    
    def __post_init__(self):
        if self.learning_objectives is None:
            self.learning_objectives = []
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class TrainingAnnotation:
    """Training point annotation with technique identification"""
    id: str
    timestamp: float
    duration: float
    technique: TrainingTechnique
    description: str
    effectiveness_score: float
    examples: List[str]
    improvement_suggestions: List[str]
    related_segments: List[str]  # Segment IDs
    confidence: float = 0.0
    
    def __post_init__(self):
        if not hasattr(self, 'examples') or self.examples is None:
            self.examples = []
        if not hasattr(self, 'improvement_suggestions') or self.improvement_suggestions is None:
            self.improvement_suggestions = []
        if not hasattr(self, 'related_segments') or self.related_segments is None:
            self.related_segments = []


@dataclass
class AdvancedAudioAnalysis:
    """Complete advanced audio analysis result"""
    session_id: str
    analysis_timestamp: datetime
    speakers: List[Speaker]
    segments: List[TimestampedSegment]
    context_sections: List[ContextSection]
    roleplay_blocks: List[RolePlayBlock]
    training_annotations: List[TrainingAnnotation]
    overall_metrics: Dict[str, float]
    qa_analysis: Dict[str, Any]  # From existing QA accuracy system
    recommendations: List[str]
    processing_time: float = 0.0


class AdvancedAudioAnalysisService:
    """Service for comprehensive advanced audio analysis"""
    
    def __init__(self):
        self.speaker_analyzer = SpeakerAnalyzer()
        self.context_analyzer = ContextAnalyzer()
        self.roleplay_analyzer = RolePlayAnalyzer()
        self.training_annotator = TrainingAnnotator()
        self.performance_calculator = PerformanceCalculator()
        
        # Training technique patterns and keywords
        self.technique_patterns = self._initialize_technique_patterns()
        
        # Context transition indicators
        self.phase_indicators = self._initialize_phase_indicators()
        
        # Performance metrics configuration
        self.metrics_config = self._initialize_metrics_config()
    
    def _initialize_technique_patterns(self) -> Dict[TrainingTechnique, Dict[str, List[str]]]:
        """Initialize patterns for training technique detection"""
        return {
            TrainingTechnique.RAPPORT_BUILDING: {
                'keywords': ['name', 'background', 'experience', 'similar', 'common', 'relationship'],
                'phrases': ['tell me about yourself', 'similar situation', 'i understand', 'that makes sense'],
                'patterns': [r'how long.*been', r'what.*background', r'similar.*experience']
            },
            TrainingTechnique.ACTIVE_LISTENING: {
                'keywords': ['understand', 'clarify', 'summarize', 'confirm', 'paraphrase'],
                'phrases': ['let me understand', 'so what you\'re saying', 'if i understand correctly', 'to clarify'],
                'patterns': [r'so you.*saying', r'let me.*understand', r'what i.*hearing']
            },
            TrainingTechnique.NEEDS_ASSESSMENT: {
                'keywords': ['need', 'requirement', 'looking', 'goal', 'objective', 'challenge'],
                'phrases': ['what are you looking for', 'what do you need', 'tell me about your goals'],
                'patterns': [r'what.*need', r'looking.*for', r'current.*situation']
            },
            TrainingTechnique.PAIN_POINT_IDENTIFICATION: {
                'keywords': ['problem', 'challenge', 'difficulty', 'struggle', 'issue', 'concern'],
                'phrases': ['biggest challenge', 'main problem', 'what concerns you', 'struggling with'],
                'patterns': [r'biggest.*challenge', r'main.*problem', r'struggling.*with']
            },
            TrainingTechnique.VALUE_PROPOSITION: {
                'keywords': ['benefit', 'advantage', 'value', 'save', 'improve', 'increase', 'roi'],
                'phrases': ['this will help you', 'the benefit is', 'you will save', 'roi on this'],
                'patterns': [r'this.*help.*you', r'benefit.*is', r'save.*money|time']
            },
            TrainingTechnique.OBJECTION_HANDLING: {
                'keywords': ['but', 'however', 'concern', 'worried', 'expensive', 'doubt'],
                'phrases': ['i understand your concern', 'that\'s a valid point', 'let me address'],
                'patterns': [r'understand.*concern', r'valid.*point', r'address.*that']
            },
            TrainingTechnique.CLOSING_TECHNIQUE: {
                'keywords': ['ready', 'start', 'proceed', 'sign', 'agreement', 'next steps'],
                'phrases': ['ready to move forward', 'shall we proceed', 'next steps would be'],
                'patterns': [r'ready.*move', r'shall.*we', r'next.*steps']
            },
            TrainingTechnique.FOLLOW_UP_COMMITMENT: {
                'keywords': ['follow up', 'schedule', 'call back', 'meeting', 'timeline'],
                'phrases': ['follow up with you', 'schedule a call', 'touch base', 'check in'],
                'patterns': [r'follow.*up', r'schedule.*call', r'touch.*base']
            },
            TrainingTechnique.CONSULTATIVE_SELLING: {
                'keywords': ['advise', 'recommend', 'suggest', 'guidance', 'expertise', 'consultant'],
                'phrases': ['i would recommend', 'based on your needs', 'my advice would be'],
                'patterns': [r'would.*recommend', r'based.*on.*your', r'advice.*would']
            },
            TrainingTechnique.CHALLENGER_SALE: {
                'keywords': ['challenge', 'different', 'perspective', 'consider', 'alternative'],
                'phrases': ['have you considered', 'different perspective', 'challenge your thinking'],
                'patterns': [r'have.*you.*considered', r'different.*perspective', r'challenge.*your']
            }
        }
    
    def _initialize_phase_indicators(self) -> Dict[RolePlayPhase, Dict[str, List[str]]]:
        """Initialize indicators for conversation phase detection"""
        return {
            RolePlayPhase.OPENING: {
                'keywords': ['hello', 'hi', 'introduction', 'name', 'pleasure', 'thanks for your time'],
                'phrases': ['nice to meet you', 'thanks for taking the time', 'i appreciate you'],
                'position_weight': 2.0  # Higher weight for early conversation
            },
            RolePlayPhase.DISCOVERY: {
                'keywords': ['tell me', 'what', 'how', 'when', 'why', 'describe', 'current'],
                'phrases': ['tell me about', 'walk me through', 'help me understand'],
                'position_weight': 1.5
            },
            RolePlayPhase.PRESENTATION: {
                'keywords': ['solution', 'product', 'service', 'features', 'benefits', 'offer'],
                'phrases': ['let me show you', 'our solution', 'this product'],
                'position_weight': 1.0
            },
            RolePlayPhase.OBJECTION_HANDLING: {
                'keywords': ['but', 'however', 'concern', 'expensive', 'doubt', 'worry'],
                'phrases': ['i\'m concerned about', 'but what about', 'however'],
                'position_weight': 1.0
            },
            RolePlayPhase.CLOSING: {
                'keywords': ['ready', 'decision', 'proceed', 'start', 'sign', 'agreement'],
                'phrases': ['ready to move forward', 'make a decision', 'get started'],
                'position_weight': 1.0
            },
            RolePlayPhase.FOLLOW_UP: {
                'keywords': ['follow up', 'next steps', 'schedule', 'timeline', 'contact'],
                'phrases': ['next steps', 'follow up', 'stay in touch'],
                'position_weight': 1.2  # Slightly higher weight for end of conversation
            }
        }
    
    def _initialize_metrics_config(self) -> Dict[str, Dict[str, Any]]:
        """Initialize performance metrics configuration"""
        return {
            'speaking_time_balance': {
                'target_salesperson_ratio': 0.4,  # Salesperson should talk ~40% of the time
                'tolerance': 0.1,
                'weight': 0.2
            },
            'question_asking_rate': {
                'target_questions_per_minute': 2.0,
                'weight': 0.15
            },
            'technique_coverage': {
                'required_techniques': ['rapport_building', 'needs_assessment', 'value_proposition'],
                'optional_techniques': ['active_listening', 'objection_handling'],
                'weight': 0.25
            },
            'conversation_flow': {
                'ideal_phase_order': ['opening', 'discovery', 'presentation', 'closing'],
                'weight': 0.15
            },
            'engagement_level': {
                'interruption_tolerance': 0.1,
                'response_time_target': 2.0,
                'weight': 0.1
            },
            'outcome_indicators': {
                'positive_indicators': ['interested', 'ready', 'sounds good', 'let\'s proceed'],
                'negative_indicators': ['not interested', 'too expensive', 'need to think'],
                'weight': 0.15
            }
        }
    
    async def analyze_audio_comprehensive(
        self,
        segments: List[TimestampedSegment],
        qa_analysis: Dict[str, Any],
        session_metadata: Dict[str, Any] = None
    ) -> AdvancedAudioAnalysis:
        """
        Perform comprehensive advanced audio analysis
        
        Args:
            segments: Timestamped audio segments from STT
            qa_analysis: Question answering analysis from preprocessing service
            session_metadata: Additional session information
        
        Returns:
            Complete advanced audio analysis
        """
        start_time = datetime.now().timestamp()
        session_id = session_metadata.get('session_id', f"session_{int(start_time)}")
        
        logger.info(f"Starting comprehensive audio analysis for session: {session_id}")
        
        # Run analysis components in parallel
        analysis_tasks = [
            self._analyze_speakers(segments),
            self._analyze_context_sections(segments),
            self._analyze_roleplay_blocks(segments),
            self._annotate_training_techniques(segments),
            self._calculate_overall_metrics(segments, qa_analysis)
        ]
        
        results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        
        # Handle any exceptions in parallel processing
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Analysis task {i} failed: {result}")
                results[i] = self._get_default_result(i)
        
        speakers, context_sections, roleplay_blocks, training_annotations, overall_metrics = results
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            speakers, context_sections, roleplay_blocks, training_annotations, overall_metrics
        )
        
        processing_time = datetime.now().timestamp() - start_time
        
        analysis = AdvancedAudioAnalysis(
            session_id=session_id,
            analysis_timestamp=datetime.now(),
            speakers=speakers,
            segments=segments,
            context_sections=context_sections,
            roleplay_blocks=roleplay_blocks,
            training_annotations=training_annotations,
            overall_metrics=overall_metrics,
            qa_analysis=qa_analysis,
            recommendations=recommendations,
            processing_time=processing_time
        )
        
        logger.info(f"Analysis completed in {processing_time:.2f}s with {len(training_annotations)} annotations")
        
        return analysis
    
    async def _analyze_speakers(self, segments: List[TimestampedSegment]) -> List[Speaker]:
        """Analyze and identify speakers with role mapping"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.speaker_analyzer.analyze, segments
        )
    
    async def _analyze_context_sections(self, segments: List[TimestampedSegment]) -> List[ContextSection]:
        """Analyze and create context sections using timestamps"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.context_analyzer.analyze, segments, self.phase_indicators
        )
    
    async def _analyze_roleplay_blocks(self, segments: List[TimestampedSegment]) -> List[RolePlayBlock]:
        """Analyze and create role-play blocks with metadata"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.roleplay_analyzer.analyze, segments, self.phase_indicators
        )
    
    async def _annotate_training_techniques(self, segments: List[TimestampedSegment]) -> List[TrainingAnnotation]:
        """Annotate training points and techniques"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.training_annotator.annotate, segments, self.technique_patterns
        )
    
    async def _calculate_overall_metrics(self, segments: List[TimestampedSegment], qa_analysis: Dict[str, Any]) -> Dict[str, float]:
        """Calculate overall performance metrics"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.performance_calculator.calculate, segments, qa_analysis, self.metrics_config
        )
    
    def _get_default_result(self, task_index: int):
        """Get default result for failed analysis tasks"""
        defaults = [
            [],  # speakers
            [],  # context_sections
            [],  # roleplay_blocks
            [],  # training_annotations
            {}   # overall_metrics
        ]
        return defaults[task_index] if task_index < len(defaults) else []
    
    def _generate_recommendations(
        self,
        speakers: List[Speaker],
        context_sections: List[ContextSection],
        roleplay_blocks: List[RolePlayBlock],
        training_annotations: List[TrainingAnnotation],
        overall_metrics: Dict[str, float]
    ) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        # Speaking time balance recommendations
        salesperson_time = sum(s.speaking_time for s in speakers if s.role == SpeakerRole.SALESPERSON)
        total_time = sum(s.speaking_time for s in speakers)
        
        if total_time > 0:
            salesperson_ratio = salesperson_time / total_time
            if salesperson_ratio > 0.6:
                recommendations.append("Consider listening more and asking more questions - you're talking too much")
            elif salesperson_ratio < 0.2:
                recommendations.append("Be more assertive in presenting your value proposition")
        
        # Question asking recommendations
        qa_metrics = overall_metrics.get('question_asking_metrics', {})
        questions_per_minute = qa_metrics.get('questions_per_minute', 0)
        
        if questions_per_minute < 1.0:
            recommendations.append("Ask more discovery questions to better understand prospect needs")
        elif questions_per_minute > 4.0:
            recommendations.append("Balance questions with value statements - avoid interrogating the prospect")
        
        # Technique coverage recommendations
        technique_scores = overall_metrics.get('technique_scores', {})
        
        if technique_scores.get('rapport_building', 0) < 0.5:
            recommendations.append("Spend more time building rapport at the beginning of the conversation")
        
        if technique_scores.get('needs_assessment', 0) < 0.5:
            recommendations.append("Conduct more thorough needs assessment before presenting solutions")
        
        if technique_scores.get('value_proposition', 0) < 0.5:
            recommendations.append("Clearly articulate the value proposition and benefits for this specific prospect")
        
        # Phase progression recommendations
        phase_flow_score = overall_metrics.get('phase_flow_score', 0)
        if phase_flow_score < 0.6:
            recommendations.append("Follow a more structured conversation flow: Opening → Discovery → Presentation → Closing")
        
        # Objection handling recommendations
        objection_score = technique_scores.get('objection_handling', 0)
        if objection_score < 0.3 and any('concern' in ann.description.lower() for ann in training_annotations):
            recommendations.append("Practice objection handling techniques - acknowledge concerns and provide evidence")
        
        return recommendations


class SpeakerAnalyzer:
    """Analyzes speakers and performs diarization mapping"""
    
    def analyze(self, segments: List[TimestampedSegment]) -> List[Speaker]:
        """Analyze speakers from segments and map to roles"""
        if not segments:
            return []
        
        # Group segments by speaker
        speaker_segments = defaultdict(list)
        for segment in segments:
            speaker_segments[segment.speaker_id].append(segment)
        
        speakers = []
        
        for speaker_id, speaker_segs in speaker_segments.items():
            # Calculate speaking characteristics
            total_time = sum(seg.duration for seg in speaker_segs)
            turn_count = len(speaker_segs)
            avg_confidence = sum(seg.confidence for seg in speaker_segs) / len(speaker_segs)
            
            # Determine role based on speaking patterns and content
            role = self._determine_speaker_role(speaker_segs)
            
            # Extract characteristics
            characteristics = self._extract_speaker_characteristics(speaker_segs)
            
            speaker = Speaker(
                id=speaker_id,
                role=role,
                characteristics=characteristics,
                confidence=avg_confidence,
                speaking_time=total_time,
                turn_count=turn_count
            )
            
            speakers.append(speaker)
        
        return sorted(speakers, key=lambda s: s.speaking_time, reverse=True)
    
    def _determine_speaker_role(self, segments: List[TimestampedSegment]) -> SpeakerRole:
        """Determine speaker role based on content analysis"""
        combined_text = ' '.join(seg.text.lower() for seg in segments)
        
        # Sales role indicators
        sales_indicators = [
            'our product', 'our service', 'our company', 'we offer', 'i can help',
            'let me show you', 'our solution', 'benefits include', 'roi'
        ]
        
        # Prospect role indicators  
        prospect_indicators = [
            'we need', 'our budget', 'our requirements', 'we\'re looking for',
            'our current', 'we use', 'our situation', 'our challenge'
        ]
        
        sales_score = sum(1 for indicator in sales_indicators if indicator in combined_text)
        prospect_score = sum(1 for indicator in prospect_indicators if indicator in combined_text)
        
        if sales_score > prospect_score:
            return SpeakerRole.SALESPERSON
        elif prospect_score > sales_score:
            return SpeakerRole.PROSPECT
        else:
            return SpeakerRole.UNKNOWN
    
    def _extract_speaker_characteristics(self, segments: List[TimestampedSegment]) -> Dict[str, Any]:
        """Extract speaker characteristics from their segments"""
        combined_text = ' '.join(seg.text for seg in segments)
        words = combined_text.split()
        
        characteristics = {
            'avg_words_per_turn': len(words) / len(segments) if segments else 0,
            'total_words': len(words),
            'avg_turn_duration': sum(seg.duration for seg in segments) / len(segments) if segments else 0,
            'speaking_pace': len(words) / sum(seg.duration for seg in segments) * 60 if segments and sum(seg.duration for seg in segments) > 0 else 0,  # words per minute
            'question_count': sum(seg.text.count('?') for seg in segments),
            'interruption_count': self._count_interruptions(segments),
            'enthusiasm_indicators': self._count_enthusiasm(combined_text),
            'professionalism_score': self._calculate_professionalism(combined_text)
        }
        
        return characteristics
    
    def _count_interruptions(self, segments: List[TimestampedSegment]) -> int:
        """Count potential interruptions (incomplete sentences, cut-offs)"""
        interruption_count = 0
        
        for segment in segments:
            text = segment.text.strip()
            # Look for incomplete sentences or cut-offs
            if text.endswith(('-', '--')) or len(text.split()) < 3:
                interruption_count += 1
        
        return interruption_count
    
    def _count_enthusiasm(self, text: str) -> int:
        """Count enthusiasm indicators in text"""
        enthusiasm_words = ['great', 'excellent', 'fantastic', 'amazing', 'wonderful', 'perfect', 'excited']
        text_lower = text.lower()
        return sum(text_lower.count(word) for word in enthusiasm_words)
    
    def _calculate_professionalism(self, text: str) -> float:
        """Calculate professionalism score based on language usage"""
        text_lower = text.lower()
        
        # Professional indicators
        professional_words = ['solution', 'benefits', 'roi', 'investment', 'partnership', 'collaborate']
        professional_score = sum(text_lower.count(word) for word in professional_words)
        
        # Unprofessional indicators (slang, filler words)
        unprofessional_words = ['um', 'uh', 'like', 'you know', 'whatever', 'yeah']
        unprofessional_score = sum(text_lower.count(word) for word in unprofessional_words)
        
        total_words = len(text.split())
        if total_words == 0:
            return 0.5
        
        # Calculate score (0-1 scale)
        net_score = (professional_score - unprofessional_score) / total_words
        return max(0, min(1, 0.5 + net_score * 10))  # Normalize to 0-1 scale


class ContextAnalyzer:
    """Analyzes context sections using timestamps and thematic grouping"""
    
    def analyze(self, segments: List[TimestampedSegment], phase_indicators: Dict) -> List[ContextSection]:
        """Analyze context sections from segments"""
        if not segments:
            return []
        
        # Group segments into context sections based on timing and content
        sections = self._create_context_sections(segments, phase_indicators)
        
        # Enhance sections with analysis
        for section in sections:
            section.summary = self._generate_section_summary(section.segments)
            section.key_points = self._extract_key_points(section.segments)
            section.techniques_used = self._identify_techniques_used(section.segments)
            section.effectiveness_score = self._calculate_section_effectiveness(section)
        
        return sections
    
    def _create_context_sections(self, segments: List[TimestampedSegment], phase_indicators: Dict) -> List[ContextSection]:
        """Create context sections based on content and timing"""
        sections = []
        current_section_segments = []
        current_phase = RolePlayPhase.OPENING
        section_id = 0
        
        for i, segment in enumerate(segments):
            # Detect phase transition
            detected_phase = self._detect_phase(segment, i, len(segments), phase_indicators)
            
            # If phase changed or we have a natural break, create new section
            if (detected_phase != current_phase and current_section_segments) or \
               (len(current_section_segments) > 10):  # Max segments per section
                
                section = self._create_section_from_segments(
                    f"section_{section_id}",
                    current_phase,
                    current_section_segments
                )
                sections.append(section)
                
                current_section_segments = []
                section_id += 1
                current_phase = detected_phase
            
            current_section_segments.append(segment)
        
        # Create final section
        if current_section_segments:
            section = self._create_section_from_segments(
                f"section_{section_id}",
                current_phase,
                current_section_segments
            )
            sections.append(section)
        
        return sections
    
    def _detect_phase(self, segment: TimestampedSegment, position: int, total: int, phase_indicators: Dict) -> RolePlayPhase:
        """Detect conversation phase for a segment"""
        text_lower = segment.text.lower()
        position_ratio = position / total if total > 0 else 0
        
        phase_scores = {}
        
        for phase, indicators in phase_indicators.items():
            score = 0.0
            
            # Keyword matching
            for keyword in indicators.get('keywords', []):
                if keyword in text_lower:
                    score += 1.0
            
            # Phrase matching
            for phrase in indicators.get('phrases', []):
                if phrase in text_lower:
                    score += 2.0
            
            # Position weighting
            position_weight = indicators.get('position_weight', 1.0)
            
            # Adjust score based on conversation position
            if phase == RolePlayPhase.OPENING and position_ratio < 0.2:
                score *= position_weight
            elif phase == RolePlayPhase.DISCOVERY and 0.1 < position_ratio < 0.5:
                score *= position_weight
            elif phase == RolePlayPhase.PRESENTATION and 0.3 < position_ratio < 0.8:
                score *= position_weight
            elif phase == RolePlayPhase.CLOSING and position_ratio > 0.7:
                score *= position_weight
            
            phase_scores[phase] = score
        
        # Return phase with highest score, default to current conversation position
        if phase_scores:
            best_phase = max(phase_scores, key=phase_scores.get)
            if phase_scores[best_phase] > 0:
                return best_phase
        
        # Fallback to position-based phase
        if position_ratio < 0.2:
            return RolePlayPhase.OPENING
        elif position_ratio < 0.5:
            return RolePlayPhase.DISCOVERY
        elif position_ratio < 0.8:
            return RolePlayPhase.PRESENTATION
        else:
            return RolePlayPhase.CLOSING
    
    def _create_section_from_segments(self, section_id: str, phase: RolePlayPhase, segments: List[TimestampedSegment]) -> ContextSection:
        """Create context section from segments"""
        if not segments:
            return None
        
        start_time = segments[0].start_time
        end_time = segments[-1].end_time
        
        # Generate title based on phase and content
        title = self._generate_section_title(phase, segments)
        
        return ContextSection(
            id=section_id,
            title=title,
            start_time=start_time,
            end_time=end_time,
            phase=phase,
            segments=segments
        )
    
    def _generate_section_title(self, phase: RolePlayPhase, segments: List[TimestampedSegment]) -> str:
        """Generate descriptive title for context section"""
        phase_titles = {
            RolePlayPhase.OPENING: "Opening & Introductions",
            RolePlayPhase.DISCOVERY: "Discovery & Needs Assessment",
            RolePlayPhase.PRESENTATION: "Solution Presentation",
            RolePlayPhase.OBJECTION_HANDLING: "Objection Handling",
            RolePlayPhase.CLOSING: "Closing & Next Steps",
            RolePlayPhase.FOLLOW_UP: "Follow-up Planning"
        }
        
        base_title = phase_titles.get(phase, "Conversation Section")
        
        # Add specific context if available
        combined_text = ' '.join(seg.text for seg in segments[:3]).lower()  # First few segments
        
        if 'price' in combined_text or 'cost' in combined_text:
            base_title += " - Pricing Discussion"
        elif 'demo' in combined_text or 'show' in combined_text:
            base_title += " - Product Demonstration"
        elif 'concern' in combined_text or 'worry' in combined_text:
            base_title += " - Addressing Concerns"
        
        return base_title
    
    def _generate_section_summary(self, segments: List[TimestampedSegment]) -> str:
        """Generate summary for context section"""
        if not segments:
            return ""
        
        # Extract key sentences (simplified approach)
        sentences = []
        for segment in segments:
            segment_sentences = [s.strip() for s in segment.text.split('.') if s.strip()]
            sentences.extend(segment_sentences[:2])  # Take first 2 sentences per segment
        
        # Return first few sentences as summary
        return '. '.join(sentences[:3]) + '.' if sentences else ""
    
    def _extract_key_points(self, segments: List[TimestampedSegment]) -> List[str]:
        """Extract key points from context section"""
        combined_text = ' '.join(seg.text for seg in segments)
        key_points = []
        
        # Look for important statements and questions
        sentences = [s.strip() for s in combined_text.split('.') if s.strip()]
        
        for sentence in sentences:
            if any(indicator in sentence.lower() for indicator in 
                   ['need', 'important', 'key', 'main', 'primary', 'benefit', 'value']):
                key_points.append(sentence)
        
        return key_points[:5]  # Return top 5 key points
    
    def _identify_techniques_used(self, segments: List[TimestampedSegment]) -> List[str]:
        """Identify sales techniques used in section"""
        combined_text = ' '.join(seg.text.lower() for seg in segments)
        techniques_used = []
        
        # Simple pattern matching for techniques
        technique_indicators = {
            'rapport_building': ['name', 'background', 'similar', 'relationship'],
            'active_listening': ['understand', 'clarify', 'so you\'re saying'],
            'needs_assessment': ['what do you need', 'tell me about', 'requirements'],
            'value_proposition': ['benefit', 'value', 'save', 'improve'],
            'objection_handling': ['understand your concern', 'valid point']
        }
        
        for technique, indicators in technique_indicators.items():
            if any(indicator in combined_text for indicator in indicators):
                techniques_used.append(technique)
        
        return techniques_used
    
    def _calculate_section_effectiveness(self, section: ContextSection) -> float:
        """Calculate effectiveness score for context section"""
        score = 0.5  # Base score
        
        # Increase score based on techniques used
        score += len(section.techniques_used) * 0.1
        
        # Increase score based on key points identified
        score += len(section.key_points) * 0.05
        
        # Increase score based on appropriate phase progression
        if section.phase in [RolePlayPhase.DISCOVERY, RolePlayPhase.PRESENTATION]:
            score += 0.1
        
        return min(1.0, score)


class RolePlayAnalyzer:
    """Analyzes role-play blocks with comprehensive metadata"""
    
    def analyze(self, segments: List[TimestampedSegment], phase_indicators: Dict) -> List[RolePlayBlock]:
        """Analyze role-play blocks from segments"""
        if not segments:
            return []
        
        # Create role-play blocks (for now, create one block per session)
        # In a more sophisticated implementation, you might detect multiple scenarios
        
        participants = list(set(seg.speaker_id for seg in segments))
        
        block = RolePlayBlock(
            id="roleplay_block_1",
            title="Sales Training Session",
            start_time=segments[0].start_time,
            end_time=segments[-1].end_time,
            phase=self._determine_primary_phase(segments, phase_indicators),
            participants=participants,
            context_sections=[],  # Will be populated by context analyzer
            training_annotations=[],  # Will be populated by training annotator
            performance_metrics={}
        )
        
        # Determine scenario type and difficulty
        block.scenario_type = self._determine_scenario_type(segments)
        block.difficulty_level = self._determine_difficulty_level(segments)
        block.learning_objectives = self._extract_learning_objectives(segments)
        
        return [block]
    
    def _determine_primary_phase(self, segments: List[TimestampedSegment], phase_indicators: Dict) -> RolePlayPhase:
        """Determine the primary phase of the role-play session"""
        phase_counts = Counter()
        
        for segment in segments:
            # Simple phase detection based on content
            text_lower = segment.text.lower()
            
            for phase, indicators in phase_indicators.items():
                score = sum(1 for keyword in indicators.get('keywords', []) if keyword in text_lower)
                if score > 0:
                    phase_counts[phase] += score
        
        return phase_counts.most_common(1)[0][0] if phase_counts else RolePlayPhase.DISCOVERY
    
    def _determine_scenario_type(self, segments: List[TimestampedSegment]) -> str:
        """Determine the type of sales scenario"""
        combined_text = ' '.join(seg.text.lower() for seg in segments)
        
        scenario_indicators = {
            'software_sales': ['software', 'platform', 'system', 'application', 'cloud'],
            'service_sales': ['service', 'consulting', 'support', 'maintenance'],
            'product_sales': ['product', 'equipment', 'device', 'hardware'],
            'b2b_sales': ['company', 'business', 'enterprise', 'organization'],
            'b2c_sales': ['personal', 'individual', 'home', 'family']
        }
        
        scenario_scores = {}
        for scenario, indicators in scenario_indicators.items():
            score = sum(1 for indicator in indicators if indicator in combined_text)
            scenario_scores[scenario] = score
        
        return max(scenario_scores, key=scenario_scores.get) if scenario_scores else "general_sales"
    
    def _determine_difficulty_level(self, segments: List[TimestampedSegment]) -> str:
        """Determine difficulty level of the role-play scenario"""
        combined_text = ' '.join(seg.text.lower() for seg in segments)
        
        # Count complexity indicators
        complexity_score = 0
        
        # Technical terms increase difficulty
        technical_terms = ['integration', 'api', 'compliance', 'security', 'scalability']
        complexity_score += sum(1 for term in technical_terms if term in combined_text)
        
        # Multiple stakeholders increase difficulty
        if any(term in combined_text for term in ['team', 'committee', 'stakeholders']):
            complexity_score += 2
        
        # Budget constraints increase difficulty
        if any(term in combined_text for term in ['budget', 'expensive', 'cost']):
            complexity_score += 1
        
        # Objections increase difficulty
        objection_terms = ['but', 'however', 'concern', 'worried', 'doubt']
        complexity_score += sum(1 for term in objection_terms if term in combined_text)
        
        if complexity_score >= 5:
            return "advanced"
        elif complexity_score >= 2:
            return "intermediate"
        else:
            return "beginner"
    
    def _extract_learning_objectives(self, segments: List[TimestampedSegment]) -> List[str]:
        """Extract learning objectives from the session"""
        objectives = []
        combined_text = ' '.join(seg.text.lower() for seg in segments)
        
        # Standard learning objectives based on content
        if any(term in combined_text for term in ['rapport', 'relationship', 'trust']):
            objectives.append("Build rapport and establish trust")
        
        if any(term in combined_text for term in ['need', 'requirement', 'challenge']):
            objectives.append("Conduct effective needs assessment")
        
        if any(term in combined_text for term in ['solution', 'benefit', 'value']):
            objectives.append("Present value proposition effectively")
        
        if any(term in combined_text for term in ['objection', 'concern', 'worry']):
            objectives.append("Handle objections professionally")
        
        if any(term in combined_text for term in ['close', 'decision', 'next steps']):
            objectives.append("Guide prospect toward decision")
        
        return objectives


class TrainingAnnotator:
    """Annotates training points and techniques using keyword dictionaries"""
    
    def annotate(self, segments: List[TimestampedSegment], technique_patterns: Dict) -> List[TrainingAnnotation]:
        """Annotate training techniques and points from segments"""
        annotations = []
        annotation_id = 0
        
        for segment in segments:
            # Analyze each segment for training techniques
            detected_techniques = self._detect_techniques(segment, technique_patterns)
            
            for technique, score, examples in detected_techniques:
                annotation = TrainingAnnotation(
                    id=f"annotation_{annotation_id}",
                    timestamp=segment.start_time,
                    duration=segment.duration,
                    technique=technique,
                    description=self._generate_technique_description(technique, segment.text, examples),
                    effectiveness_score=score,
                    examples=examples,
                    improvement_suggestions=self._generate_improvement_suggestions(technique, score, segment.text),
                    related_segments=[segment.speaker_id],
                    confidence=score
                )
                
                annotations.append(annotation)
                annotation_id += 1
        
        return annotations
    
    def _detect_techniques(self, segment: TimestampedSegment, technique_patterns: Dict) -> List[Tuple[TrainingTechnique, float, List[str]]]:
        """Detect training techniques in a segment"""
        text_lower = segment.text.lower()
        detected = []
        
        for technique, patterns in technique_patterns.items():
            score = 0.0
            examples = []
            
            # Check keywords
            for keyword in patterns.get('keywords', []):
                if keyword in text_lower:
                    score += 0.3
                    examples.append(f"Uses keyword: '{keyword}'")
            
            # Check phrases
            for phrase in patterns.get('phrases', []):
                if phrase in text_lower:
                    score += 0.6
                    examples.append(f"Uses phrase: '{phrase}'")
            
            # Check patterns
            for pattern in patterns.get('patterns', []):
                if re.search(pattern, text_lower):
                    score += 0.5
                    examples.append(f"Matches pattern: {pattern}")
            
            # Normalize score
            if score > 0:
                score = min(1.0, score)
                detected.append((technique, score, examples))
        
        return detected
    
    def _generate_technique_description(self, technique: TrainingTechnique, text: str, examples: List[str]) -> str:
        """Generate description for training technique annotation"""
        technique_descriptions = {
            TrainingTechnique.RAPPORT_BUILDING: "Building rapport and establishing connection with prospect",
            TrainingTechnique.ACTIVE_LISTENING: "Demonstrating active listening and understanding",
            TrainingTechnique.NEEDS_ASSESSMENT: "Assessing prospect's needs and requirements",
            TrainingTechnique.PAIN_POINT_IDENTIFICATION: "Identifying and exploring prospect's pain points",
            TrainingTechnique.VALUE_PROPOSITION: "Presenting value proposition and benefits",
            TrainingTechnique.OBJECTION_HANDLING: "Addressing prospect concerns and objections",
            TrainingTechnique.CLOSING_TECHNIQUE: "Attempting to close or advance the sale",
            TrainingTechnique.FOLLOW_UP_COMMITMENT: "Establishing follow-up commitment",
            TrainingTechnique.CONSULTATIVE_SELLING: "Using consultative selling approach",
            TrainingTechnique.CHALLENGER_SALE: "Challenging prospect's thinking with insights"
        }
        
        base_description = technique_descriptions.get(technique, f"Using {technique.value} technique")
        
        # Add specific context from the text
        if len(text) > 50:
            context = f" - Context: '{text[:50]}...'"
            base_description += context
        
        return base_description
    
    def _generate_improvement_suggestions(self, technique: TrainingTechnique, score: float, text: str) -> List[str]:
        """Generate improvement suggestions for training techniques"""
        suggestions = []
        
        # General suggestions based on technique and score
        if score < 0.5:
            technique_tips = {
                TrainingTechnique.RAPPORT_BUILDING: [
                    "Use the prospect's name more often",
                    "Find common ground or shared experiences",
                    "Show genuine interest in their business"
                ],
                TrainingTechnique.ACTIVE_LISTENING: [
                    "Paraphrase what the prospect said",
                    "Ask clarifying questions",
                    "Use confirmation phrases like 'I understand'"
                ],
                TrainingTechnique.NEEDS_ASSESSMENT: [
                    "Ask more open-ended questions",
                    "Dig deeper into their current situation",
                    "Explore the impact of their challenges"
                ],
                TrainingTechnique.VALUE_PROPOSITION: [
                    "Connect benefits directly to their specific needs",
                    "Use concrete examples and metrics",
                    "Focus on business impact and ROI"
                ],
                TrainingTechnique.OBJECTION_HANDLING: [
                    "Acknowledge the concern first",
                    "Ask questions to understand the root cause",
                    "Provide evidence or testimonials to address the objection"
                ]
            }
            
            suggestions.extend(technique_tips.get(technique, ["Practice this technique more in future conversations"]))
        
        elif score >= 0.8:
            suggestions.append("Great execution of this technique!")
        
        return suggestions


class PerformanceCalculator:
    """Calculates comprehensive performance metrics"""
    
    def calculate(self, segments: List[TimestampedSegment], qa_analysis: Dict[str, Any], metrics_config: Dict) -> Dict[str, float]:
        """Calculate overall performance metrics"""
        metrics = {}
        
        if not segments:
            return metrics
        
        # Speaking time balance
        metrics.update(self._calculate_speaking_time_metrics(segments, metrics_config))
        
        # Question asking metrics (from qa_analysis)
        metrics.update(self._calculate_question_metrics(qa_analysis, segments, metrics_config))
        
        # Technique coverage metrics
        metrics.update(self._calculate_technique_metrics(segments, metrics_config))
        
        # Conversation flow metrics
        metrics.update(self._calculate_flow_metrics(segments, metrics_config))
        
        # Engagement metrics
        metrics.update(self._calculate_engagement_metrics(segments, metrics_config))
        
        # Outcome metrics
        metrics.update(self._calculate_outcome_metrics(segments, metrics_config))
        
        # Overall performance score
        metrics['overall_performance_score'] = self._calculate_overall_score(metrics, metrics_config)
        
        return metrics
    
    def _calculate_speaking_time_metrics(self, segments: List[TimestampedSegment], config: Dict) -> Dict[str, float]:
        """Calculate speaking time balance metrics"""
        speaking_times = defaultdict(float)
        
        for segment in segments:
            speaking_times[segment.speaker_id] += segment.duration
        
        total_time = sum(speaking_times.values())
        
        if total_time == 0:
            return {'speaking_time_balance_score': 0.0}
        
        # Assume first speaker (by time) is salesperson
        speakers_by_time = sorted(speaking_times.items(), key=lambda x: x[1], reverse=True)
        
        if len(speakers_by_time) >= 2:
            salesperson_time = speakers_by_time[0][1]  # Assume most talkative is salesperson initially
            prospect_time = speakers_by_time[1][1]
            
            # Actually, salesperson should talk less in good sales conversations
            # So let's identify salesperson by sales language patterns
            salesperson_id = self._identify_salesperson(segments)
            if salesperson_id:
                salesperson_time = speaking_times.get(salesperson_id, 0)
            
            salesperson_ratio = salesperson_time / total_time
            target_ratio = config['speaking_time_balance']['target_salesperson_ratio']
            tolerance = config['speaking_time_balance']['tolerance']
            
            # Calculate score based on how close to target ratio
            deviation = abs(salesperson_ratio - target_ratio)
            score = max(0, 1 - (deviation / tolerance))
        else:
            score = 0.5  # Neutral score for single speaker
        
        return {
            'speaking_time_balance_score': score,
            'salesperson_speaking_ratio': salesperson_ratio if 'salesperson_ratio' in locals() else 0.5
        }
    
    def _identify_salesperson(self, segments: List[TimestampedSegment]) -> str:
        """Identify salesperson speaker ID based on content"""
        speaker_sales_scores = defaultdict(int)
        
        sales_indicators = ['our product', 'our service', 'we offer', 'i can help', 'benefits', 'solution']
        
        for segment in segments:
            text_lower = segment.text.lower()
            score = sum(1 for indicator in sales_indicators if indicator in text_lower)
            speaker_sales_scores[segment.speaker_id] += score
        
        return max(speaker_sales_scores, key=speaker_sales_scores.get) if speaker_sales_scores else None
    
    def _calculate_question_metrics(self, qa_analysis: Dict[str, Any], segments: List[TimestampedSegment], config: Dict) -> Dict[str, float]:
        """Calculate question asking metrics using QA analysis"""
        total_duration = sum(seg.duration for seg in segments) / 60  # Convert to minutes
        
        if total_duration == 0:
            return {'question_asking_score': 0.0, 'questions_per_minute': 0.0}
        
        # Extract question metrics from QA analysis
        question_count = qa_analysis.get('question_count', 0)
        questions_per_minute = question_count / total_duration
        
        target_rate = config['question_asking_rate']['target_questions_per_minute']
        
        # Score based on target rate (peak at target, declining on both sides)
        if questions_per_minute == 0:
            score = 0.0
        elif questions_per_minute <= target_rate:
            score = questions_per_minute / target_rate
        else:
            # Penalty for asking too many questions
            excess = questions_per_minute - target_rate
            score = max(0, 1 - (excess / target_rate))
        
        return {
            'question_asking_score': score,
            'questions_per_minute': questions_per_minute,
            'total_questions': question_count,
            'question_asking_metrics': {
                'questions_per_minute': questions_per_minute,
                'total_questions': question_count,
                'target_rate': target_rate
            }
        }
    
    def _calculate_technique_metrics(self, segments: List[TimestampedSegment], config: Dict) -> Dict[str, float]:
        """Calculate training technique coverage metrics"""
        technique_scores = {}
        
        # Simple technique detection (this would be more sophisticated in production)
        combined_text = ' '.join(seg.text.lower() for seg in segments)
        
        technique_indicators = {
            'rapport_building': ['name', 'background', 'similar', 'relationship'],
            'needs_assessment': ['need', 'require', 'looking for', 'challenge'],
            'value_proposition': ['benefit', 'value', 'save', 'improve', 'roi'],
            'objection_handling': ['concern', 'but', 'however', 'understand'],
            'active_listening': ['understand', 'clarify', 'so you\'re saying']
        }
        
        for technique, indicators in technique_indicators.items():
            score = sum(1 for indicator in indicators if indicator in combined_text)
            technique_scores[technique] = min(1.0, score / len(indicators))
        
        # Calculate coverage score
        required_techniques = config['technique_coverage']['required_techniques']
        required_score = sum(technique_scores.get(t, 0) for t in required_techniques) / len(required_techniques)
        
        optional_techniques = config['technique_coverage']['optional_techniques']
        optional_score = sum(technique_scores.get(t, 0) for t in optional_techniques) / len(optional_techniques) if optional_techniques else 0
        
        overall_technique_score = (required_score * 0.8) + (optional_score * 0.2)
        
        return {
            'technique_coverage_score': overall_technique_score,
            'technique_scores': technique_scores
        }
    
    def _calculate_flow_metrics(self, segments: List[TimestampedSegment], config: Dict) -> Dict[str, float]:
        """Calculate conversation flow metrics"""
        # Simplified phase detection
        phases_detected = []
        
        for i, segment in enumerate(segments):
            position_ratio = i / len(segments)
            text_lower = segment.text.lower()
            
            if position_ratio < 0.2 and any(word in text_lower for word in ['hello', 'hi', 'introduction']):
                phases_detected.append('opening')
            elif 'tell me' in text_lower or 'what' in text_lower:
                phases_detected.append('discovery')
            elif 'solution' in text_lower or 'product' in text_lower:
                phases_detected.append('presentation')
            elif 'ready' in text_lower or 'proceed' in text_lower:
                phases_detected.append('closing')
        
        # Remove duplicates while preserving order
        unique_phases = []
        for phase in phases_detected:
            if phase not in unique_phases:
                unique_phases.append(phase)
        
        ideal_order = config['conversation_flow']['ideal_phase_order']
        
        # Calculate flow score based on phase order alignment
        score = 0.0
        for i, phase in enumerate(unique_phases):
            if i < len(ideal_order) and phase == ideal_order[i]:
                score += 1.0
        
        flow_score = score / len(ideal_order) if ideal_order else 0.5
        
        return {
            'phase_flow_score': flow_score,
            'detected_phases': unique_phases
        }
    
    def _calculate_engagement_metrics(self, segments: List[TimestampedSegment], config: Dict) -> Dict[str, float]:
        """Calculate engagement level metrics"""
        # Calculate interruption rate
        short_segments = sum(1 for seg in segments if seg.duration < 2.0)  # Very short segments may indicate interruptions
        interruption_rate = short_segments / len(segments) if segments else 0
        
        tolerance = config['engagement_level']['interruption_tolerance']
        interruption_score = max(0, 1 - (interruption_rate / tolerance)) if tolerance > 0 else 0.5
        
        # Calculate response variety (different sentence lengths, structures)
        word_counts = [len(seg.text.split()) for seg in segments if seg.text.strip()]
        variety_score = 0.5
        
        if word_counts:
            avg_words = sum(word_counts) / len(word_counts)
            variance = sum((w - avg_words) ** 2 for w in word_counts) / len(word_counts)
            # Higher variance indicates more varied responses
            variety_score = min(1.0, variance / 100)  # Normalize
        
        engagement_score = (interruption_score * 0.6) + (variety_score * 0.4)
        
        return {
            'engagement_score': engagement_score,
            'interruption_rate': interruption_rate,
            'response_variety_score': variety_score
        }
    
    def _calculate_outcome_metrics(self, segments: List[TimestampedSegment], config: Dict) -> Dict[str, float]:
        """Calculate outcome indicator metrics"""
        combined_text = ' '.join(seg.text.lower() for seg in segments)
        
        positive_indicators = config['outcome_indicators']['positive_indicators']
        negative_indicators = config['outcome_indicators']['negative_indicators']
        
        positive_count = sum(1 for indicator in positive_indicators if indicator in combined_text)
        negative_count = sum(1 for indicator in negative_indicators if indicator in combined_text)
        
        # Calculate outcome score
        if positive_count + negative_count == 0:
            outcome_score = 0.5  # Neutral
        else:
            outcome_score = positive_count / (positive_count + negative_count)
        
        return {
            'outcome_score': outcome_score,
            'positive_indicators': positive_count,
            'negative_indicators': negative_count
        }
    
    def _calculate_overall_score(self, metrics: Dict[str, float], config: Dict) -> float:
        """Calculate weighted overall performance score"""
        score_components = [
            (metrics.get('speaking_time_balance_score', 0), config['speaking_time_balance']['weight']),
            (metrics.get('question_asking_score', 0), config['question_asking_rate']['weight']),
            (metrics.get('technique_coverage_score', 0), config['technique_coverage']['weight']),
            (metrics.get('phase_flow_score', 0), config['conversation_flow']['weight']),
            (metrics.get('engagement_score', 0), config['engagement_level']['weight']),
            (metrics.get('outcome_score', 0), config['outcome_indicators']['weight'])
        ]
        
        weighted_sum = sum(score * weight for score, weight in score_components)
        total_weight = sum(weight for _, weight in score_components)
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0


# Global service instance
_advanced_audio_service = None

def get_advanced_audio_service() -> AdvancedAudioAnalysisService:
    """Get singleton advanced audio analysis service instance"""
    global _advanced_audio_service
    if _advanced_audio_service is None:
        _advanced_audio_service = AdvancedAudioAnalysisService()
    return _advanced_audio_service