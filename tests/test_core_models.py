"""
Test Suite for Core Models
Tests STT confidence scoring, quality metrics, and conversation tracking
"""
import pytest
import time
from unittest.mock import Mock, patch
from datetime import datetime

from src.models.core import (
    STTResult, TTSResult, VoiceProfile, ConversationTurn,
    ConfidenceLevel, QualityMetrics
)

class TestSTTResult:
    """Test STT result model and confidence scoring"""
    
    def test_stt_result_creation(self):
        """Test basic STT result creation"""
        quality = QualityMetrics(clarity=0.9, noise_level=0.1, volume=0.8)
        result = STTResult(
            text="Hello world",
            confidence=0.85,
            language="en",
            processing_time=1.5,
            model_used="faster_whisper_base",
            quality_metrics=quality
        )
        
        assert result.text == "Hello world"
        assert result.confidence == 0.85
        assert result.language == "en"
        assert result.processing_time == 1.5
        assert result.model_used == "faster_whisper_base"
        assert result.quality_metrics.clarity == 0.9
    
    def test_confidence_level_high(self):
        """Test high confidence level detection"""
        result = STTResult(
            text="Clear speech",
            confidence=0.9,
            language="en",
            processing_time=1.0,
            model_used="test",
            quality_metrics=QualityMetrics()
        )
        
        level = result.get_confidence_level(0.8, 0.6)
        assert level == ConfidenceLevel.HIGH
        assert result.is_high_confidence(0.8) == True
        assert result.is_acceptable(0.6) == True
    
    def test_confidence_level_medium(self):
        """Test medium confidence level detection"""
        result = STTResult(
            text="Okay speech",
            confidence=0.7,
            language="en",
            processing_time=1.0,
            model_used="test",
            quality_metrics=QualityMetrics()
        )
        
        level = result.get_confidence_level(0.8, 0.6)
        assert level == ConfidenceLevel.MEDIUM
        assert result.is_high_confidence(0.8) == False
        assert result.is_acceptable(0.6) == True
    
    def test_confidence_level_low(self):
        """Test low confidence level detection"""
        result = STTResult(
            text="Poor speech",
            confidence=0.4,
            language="en",
            processing_time=1.0,
            model_used="test",
            quality_metrics=QualityMetrics()
        )
        
        level = result.get_confidence_level(0.8, 0.6)
        assert level == ConfidenceLevel.LOW
        assert result.is_high_confidence(0.8) == False
        assert result.is_acceptable(0.6) == False
        assert result.is_acceptable(0.3) == True
    
    def test_quality_score_calculation(self):
        """Test quality score calculation"""
        # High quality result
        quality_high = QualityMetrics(clarity=0.9, noise_level=0.1, volume=0.8)
        result_high = STTResult(
            text="Perfect transcription",
            confidence=0.95,
            language="en",
            processing_time=0.5,
            model_used="test",
            quality_metrics=quality_high
        )
        
        score = result_high.quality_score()
        assert score > 0.8  # Should be high quality
        
        # Low quality result
        quality_low = QualityMetrics(clarity=0.4, noise_level=0.8, volume=0.3)
        result_low = STTResult(
            text="Bad transcription",
            confidence=0.3,
            language="en",
            processing_time=5.0,
            model_used="test",
            quality_metrics=quality_low
        )
        
        score_low = result_low.quality_score()
        assert score_low < 0.5  # Should be low quality
    
    def test_error_handling(self):
        """Test STT result with error"""
        result = STTResult(
            text="",
            confidence=0.0,
            language="en",
            processing_time=0.0,
            model_used="test",
            quality_metrics=QualityMetrics(),
            error="Audio processing failed"
        )
        
        assert result.error == "Audio processing failed"
        assert result.text == ""
        assert result.confidence == 0.0

class TestTTSResult:
    """Test TTS result model and quality metrics"""
    
    def test_tts_result_creation(self):
        """Test basic TTS result creation"""
        quality = QualityMetrics(clarity=0.9, noise_level=0.1, volume=0.8)
        result = TTSResult(
            success=True,
            audio_path="/tmp/speech.wav",
            duration=3.5,
            processing_time=2.0,
            voice_used="coqui_tacotron2",
            quality_metrics=quality
        )
        
        assert result.success == True
        assert result.audio_path == "/tmp/speech.wav"
        assert result.duration == 3.5
        assert result.processing_time == 2.0
        assert result.voice_used == "coqui_tacotron2"
    
    def test_tts_failure(self):
        """Test TTS failure handling"""
        result = TTSResult(
            success=False,
            audio_path=None,
            duration=0.0,
            processing_time=1.0,
            voice_used="test",
            quality_metrics=QualityMetrics(),
            error="TTS engine failed"
        )
        
        assert result.success == False
        assert result.audio_path is None
        assert result.error == "TTS engine failed"

class TestVoiceProfile:
    """Test voice profile configuration"""
    
    def test_default_voice_profile(self):
        """Test default voice profile"""
        profile = VoiceProfile()
        
        assert profile.model_name is None
        assert profile.speaker_name is None
        assert profile.gender == "female"
        assert profile.speed == 1.0
        assert profile.volume == 0.8
        assert profile.language == "en"
    
    def test_custom_voice_profile(self):
        """Test custom voice profile"""
        profile = VoiceProfile(
            model_name="custom_model",
            speaker_name="alice",
            gender="female",
            speed=1.2,
            volume=0.9,
            language="en-US"
        )
        
        assert profile.model_name == "custom_model"
        assert profile.speaker_name == "alice"
        assert profile.speed == 1.2
        assert profile.volume == 0.9
        assert profile.language == "en-US"
    
    def test_voice_profile_string(self):
        """Test voice profile string representation"""
        profile = VoiceProfile(
            model_name="test_model",
            speaker_name="bob",
            gender="male"
        )
        
        profile_str = str(profile)
        assert "test_model" in profile_str
        assert "bob" in profile_str
        assert "male" in profile_str

class TestConversationTurn:
    """Test conversation turn with confidence tracking"""
    
    def test_conversation_turn_creation(self):
        """Test basic conversation turn creation"""
        stt_result = STTResult(
            text="How are you?",
            confidence=0.8,
            language="en",
            processing_time=1.0,
            model_used="test",
            quality_metrics=QualityMetrics(clarity=0.8, noise_level=0.2, volume=0.7)
        )
        
        ai_response = "I'm doing well, thank you!"
        
        turn = ConversationTurn(
            user_input=stt_result,
            ai_response=ai_response
        )
        
        assert turn.user_input == stt_result
        assert turn.ai_response == ai_response
        assert turn.voice_output is None
        assert isinstance(turn.timestamp, datetime)
    
    def test_conversation_turn_with_tts(self):
        """Test conversation turn with TTS output"""
        stt_result = STTResult(
            text="Hello",
            confidence=0.9,
            language="en",
            processing_time=1.0,
            model_used="test",
            quality_metrics=QualityMetrics()
        )
        
        tts_result = TTSResult(
            success=True,
            audio_path="/tmp/response.wav",
            duration=2.0,
            processing_time=1.5,
            voice_used="test",
            quality_metrics=QualityMetrics()
        )
        
        turn = ConversationTurn(
            user_input=stt_result,
            ai_response="Hi there!",
            voice_output=tts_result
        )
        
        assert turn.voice_output == tts_result
    
    def test_overall_quality_calculation(self):
        """Test overall quality calculation"""
        # High quality turn
        stt_high = STTResult(
            text="Clear input",
            confidence=0.9,
            language="en",
            processing_time=1.0,
            model_used="test",
            quality_metrics=QualityMetrics(clarity=0.9, noise_level=0.1, volume=0.8)
        )
        
        tts_high = TTSResult(
            success=True,
            audio_path="/tmp/test.wav",
            duration=2.0,
            processing_time=1.0,
            voice_used="test",
            quality_metrics=QualityMetrics(clarity=0.9, noise_level=0.1, volume=0.8)
        )
        
        turn_high = ConversationTurn(
            user_input=stt_high,
            ai_response="Good response",
            voice_output=tts_high
        )
        
        quality = turn_high.overall_quality
        assert quality > 0.8
        
        # Low quality turn
        stt_low = STTResult(
            text="Poor input",
            confidence=0.3,
            language="en",
            processing_time=5.0,
            model_used="test",
            quality_metrics=QualityMetrics(clarity=0.3, noise_level=0.8, volume=0.2)
        )
        
        turn_low = ConversationTurn(
            user_input=stt_low,
            ai_response="Response"
        )
        
        quality_low = turn_low.overall_quality
        assert quality_low < 0.5
    
    def test_feedback_generation(self):
        """Test conversation feedback generation"""
        stt_result = STTResult(
            text="Test input",
            confidence=0.75,
            language="en",
            processing_time=2.0,
            model_used="test",
            quality_metrics=QualityMetrics(clarity=0.8, noise_level=0.3, volume=0.6)
        )
        
        turn = ConversationTurn(
            user_input=stt_result,
            ai_response="Test response",
            confidence_thresholds={"high": 0.8, "medium": 0.6, "low": 0.3}
        )
        
        feedback = turn.generate_feedback()
        
        assert "confidence_level" in feedback
        assert "suggestions" in feedback
        assert "quality_score" in feedback
        assert "processing_time" in feedback
        
        # Check confidence level is correct
        assert feedback["confidence_level"] == "medium"
    
    def test_feedback_with_low_confidence(self):
        """Test feedback generation for low confidence input"""
        stt_result = STTResult(
            text="Unclear speech",
            confidence=0.4,
            language="en",
            processing_time=3.0,
            model_used="test",
            quality_metrics=QualityMetrics(clarity=0.4, noise_level=0.7, volume=0.3)
        )
        
        turn = ConversationTurn(
            user_input=stt_result,
            ai_response="I'm sorry, could you repeat that?"
        )
        
        feedback = turn.generate_feedback()
        
        assert feedback["confidence_level"] == "low"
        assert len(feedback["suggestions"]) > 0
        
        # Should have suggestions for improvement
        suggestions_text = " ".join(feedback["suggestions"])
        assert any(word in suggestions_text.lower() for word in ["microphone", "noise", "volume", "clear"])

class TestQualityMetrics:
    """Test quality metrics model"""
    
    def test_quality_metrics_creation(self):
        """Test quality metrics creation"""
        metrics = QualityMetrics(
            clarity=0.85,
            noise_level=0.15,
            volume=0.75
        )
        
        assert metrics.clarity == 0.85
        assert metrics.noise_level == 0.15
        assert metrics.volume == 0.75
    
    def test_quality_metrics_defaults(self):
        """Test default quality metrics"""
        metrics = QualityMetrics()
        
        assert metrics.clarity == 0.0
        assert metrics.noise_level == 0.0
        assert metrics.volume == 0.0