"""
Audio Analysis Domain Models and Enums
Shared data structures for audio analysis services
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime

class SpeakerRole(Enum):
    """Speaker roles in sales conversations"""
    SALESPERSON = "salesperson"
    PROSPECT = "prospect"
    UNKNOWN = "unknown"

class RolePlayPhase(Enum):
    """Role-play conversation phases"""
    OPENING = "opening"
    DISCOVERY = "discovery"
    PRESENTATION = "presentation"
    OBJECTION_HANDLING = "objection_handling"
    CLOSING = "closing"
    FOLLOW_UP = "follow_up"

class TrainingTechnique(Enum):
    """Sales training techniques and methodologies"""
    RAPPORT_BUILDING = "rapport_building"
    ACTIVE_LISTENING = "active_listening"
    NEEDS_ASSESSMENT = "needs_assessment"
    PAIN_POINT_IDENTIFICATION = "pain_point_identification"
    VALUE_PROPOSITION = "value_proposition"
    OBJECTION_HANDLING = "objection_handling"
    CLOSING_TECHNIQUE = "closing_technique"
    FOLLOW_UP_COMMITMENT = "follow_up_commitment"
    CONSULTATIVE_SELLING = "consultative_selling"

@dataclass
class Speaker:
    """Represents a speaker in the conversation"""
    id: str
    name: Optional[str] = None
    role: SpeakerRole = SpeakerRole.UNKNOWN
    confidence: float = 0.0
    voice_characteristics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.voice_characteristics is None:
            self.voice_characteristics = {}

@dataclass
class TimestampedSegment:
    """A segment of conversation with timing information"""
    start_time: float
    end_time: float
    text: str
    speaker_id: str
    confidence: float = 0.0
    word_level_timestamps: List[Dict] = None
    emotions: Dict[str, float] = None
    
    def __post_init__(self):
        if self.word_level_timestamps is None:
            self.word_level_timestamps = []
        if self.emotions is None:
            self.emotions = {}

@dataclass
class ContextSection:
    """A contextual section of the conversation"""
    id: str
    start_time: float
    end_time: float
    title: str
    description: str
    segments: List[TimestampedSegment]
    metadata: Dict[str, Any] = None
    importance_score: float = 0.0
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class RolePlayBlock:
    """A role-play block with specific training focus"""
    id: str
    phase: RolePlayPhase
    start_time: float
    end_time: float
    segments: List[TimestampedSegment]
    techniques_used: List[TrainingTechnique]
    effectiveness_score: float = 0.0
    feedback_points: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.feedback_points is None:
            self.feedback_points = []
        if self.metadata is None:
            self.metadata = {}

@dataclass
class TrainingAnnotation:
    """Annotation for specific training points"""
    id: str
    timestamp: float
    technique: TrainingTechnique
    description: str
    effectiveness_rating: int
    improvement_suggestions: List[str]
    related_segment_id: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class AdvancedAudioAnalysis:
    """Complete analysis result"""
    session_id: str
    timestamp: str
    speakers: List[Speaker]
    segments: List[TimestampedSegment]
    context_sections: List[ContextSection]
    roleplay_blocks: List[RolePlayBlock]
    training_annotations: List[TrainingAnnotation]
    overall_score: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}