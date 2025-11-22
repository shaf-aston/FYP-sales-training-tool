"""
TTS Quality Assessment and MOS Evaluation
"""

import time
import io
import logging
from typing import Dict, List

try:
    import soundfile as sf
    import numpy as np
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    sf = None
    np = None
    AUDIO_PROCESSING_AVAILABLE = False

logger = logging.getLogger(__name__)


class MOSEvaluator:
    """Mean Opinion Score evaluation framework for TTS quality"""
    
    def __init__(self):
        self.evaluations = []
    
    def evaluate_sample(self, audio_data: bytes, reference_text: str, 
                       persona_name: str, human_score: float = None) -> Dict:
        """Evaluate TTS sample quality
        
        Args:
            audio_data: Generated audio bytes
            reference_text: Original text
            persona_name: Persona used
            human_score: Optional human evaluation score (1-5)
        
        Returns:
            Evaluation metrics
        """
        evaluation = {
            "text": reference_text[:100],
            "persona": persona_name,
            "audio_size_bytes": len(audio_data),
            "timestamp": time.time(),
            "human_score": human_score,
            "objective_metrics": self._calculate_objective_metrics(audio_data)
        }
        
        self.evaluations.append(evaluation)
        return evaluation
    
    def _calculate_objective_metrics(self, audio_data: bytes) -> Dict:
        """Calculate objective audio quality metrics"""
        if not AUDIO_PROCESSING_AVAILABLE:
            return {"error": "Audio processing not available"}
        
        try:
            with io.BytesIO(audio_data) as audio_buffer:
                audio, sample_rate = sf.read(audio_buffer)
            
            metrics = {
                "duration": len(audio) / sample_rate,
                "sample_rate": sample_rate,
                "rms_energy": float(np.sqrt(np.mean(audio**2))),
                "peak_amplitude": float(np.max(np.abs(audio))),
                "zero_crossing_rate": float(np.mean(np.abs(np.diff(np.sign(audio))) / 2)),
                "dynamic_range_db": float(20 * np.log10(np.max(np.abs(audio)) / (np.mean(np.abs(audio)) + 1e-10)))
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating objective metrics: {e}")
            return {"error": str(e)}
    
    def get_mos_statistics(self) -> Dict:
        """Get MOS evaluation statistics"""
        if not self.evaluations:
            return {"total_evaluations": 0}
        
        human_scores = [e["human_score"] for e in self.evaluations if e["human_score"] is not None]
        
        stats = {
            "total_evaluations": len(self.evaluations),
            "human_evaluations": len(human_scores),
            "avg_human_score": np.mean(human_scores) if human_scores else None,
            "std_human_score": np.std(human_scores) if human_scores else None,
            "personas_evaluated": len(set(e["persona"] for e in self.evaluations))
        }
        
        return stats