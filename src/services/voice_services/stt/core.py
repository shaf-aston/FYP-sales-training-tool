"""
STT Core Models and Results
"""

import time
import logging
from typing import Dict, Optional

try:
    import jiwer
    JIWER_AVAILABLE = True
except ImportError:
    JIWER_AVAILABLE = False

logger = logging.getLogger(__name__)


class STTResult:
    """Speech-to-text result with metadata"""
    
    def __init__(self, text: str, confidence: float, language: str = "en",
                 duration: float = 0.0, processing_time: float = 0.0,
                 wer_score: float = None, backend_used: str = None):
        """
        Initialize STT result
        
        Args:
            text: Transcribed text
            confidence: Confidence score (0.0-1.0)
            language: Detected language
            duration: Audio duration in seconds
            processing_time: Processing time in seconds
            wer_score: Word Error Rate if ground truth available
            backend_used: STT backend that generated this result
        """
        self.text = text
        self.confidence = confidence
        self.language = language
        self.duration = duration
        self.processing_time = processing_time
        self.wer_score = wer_score
        self.backend_used = backend_used
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "language": self.language,
            "duration": self.duration,
            "processing_time": self.processing_time,
            "wer_score": self.wer_score,
            "backend_used": self.backend_used,
            "timestamp": self.timestamp
        }
    
    def calculate_wer(self, ground_truth: str) -> float:
        """Calculate Word Error Rate against ground truth"""
        if not JIWER_AVAILABLE:
            logger.warning("jiwer not available for WER calculation")
            return None
        
        try:
            wer = jiwer.wer(ground_truth, self.text)
            self.wer_score = wer
            return wer
        except Exception as e:
            logger.error(f"Error calculating WER: {e}")
            return None