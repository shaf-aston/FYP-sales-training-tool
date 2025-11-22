"""
Test Suite for Voice Manager
Tests orchestration of STT/TTS services with confidence tracking
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.services.voice_manager import VoiceManager
from src.models.core import (
    STTResult, TTSResult, VoiceProfile, ConversationTurn,
    ConfidenceLevel, QualityMetrics
)

class TestVoiceManager:
    """Test voice manager functionality"""
    
    @patch('src.services.voice_manager.STTService')
    @patch('src.services.voice_manager.TTSService')
    def test_voice_manager_initialization(self, mock_tts_service, mock_stt_service):
        """Test voice manager initialization"""
        mock_stt_instance = Mock()
        mock_tts_instance = Mock()
        mock_stt_service.return_value = mock_stt_instance
        mock_tts_service.return_value = mock_tts_instance
        
        voice_profile = VoiceProfile(gender="male", speed=1.2)
        confidence_thresholds = {"high": 0.85, "medium": 0.65, "low": 0.35}
        
        manager = VoiceManager(
            stt_provider="faster_whisper",
            tts_provider="coqui",
            voice_profile=voice_profile,
            confidence_thresholds=confidence_thresholds
        )
        
        assert manager.stt_service == mock_stt_instance
        assert manager.tts_service == mock_tts_instance
        assert manager.confidence_thresholds == confidence_thresholds
        assert len(manager.conversation_history) == 0
        assert manager.session_metrics["total_turns"] == 0
        
        mock_stt_service.assert_called_once_with(provider="faster_whisper")
        mock_tts_service.assert_called_once_with(provider="coqui", voice_profile=voice_profile)
    
    @patch('src.services.voice_manager.STTService')
    @patch('src.services.voice_manager.TTSService')
    def test_process_audio_input(self, mock_tts_service, mock_stt_service):
        """Test audio input processing"""
        # Mock STT service
        mock_stt_instance = Mock()
        mock_stt_result = STTResult(
            text="Hello there",
            confidence=0.85,
            language="en",
            processing_time=1.5,
            model_used="faster_whisper",
            quality_metrics=QualityMetrics(clarity=0.9, noise_level=0.1, volume=0.8)
        )
        mock_stt_instance.transcribe.return_value = mock_stt_result
        mock_stt_service.return_value = mock_stt_instance
        
        # Mock TTS service
        mock_tts_instance = Mock()
        mock_tts_service.return_value = mock_tts_instance
        
        manager = VoiceManager()
        result = manager.process_audio_input("audio_data", language="en")
        
        assert result == mock_stt_result
        assert result.text == "Hello there"
        assert result.confidence == 0.85
        mock_stt_instance.transcribe.assert_called_once_with("audio_data", "en")
    
    @patch('src.services.voice_manager.STTService')
    @patch('src.services.voice_manager.TTSService')
    def test_generate_speech_response(self, mock_tts_service, mock_stt_service):
        """Test speech response generation"""
        # Mock services
        mock_stt_instance = Mock()
        mock_tts_instance = Mock()
        mock_stt_service.return_value = mock_stt_instance
        
        mock_tts_result = TTSResult(
            success=True,
            audio_path="/tmp/response.wav",
            duration=3.0,
            processing_time=2.0,
            voice_used="coqui",
            quality_metrics=QualityMetrics(clarity=0.9, noise_level=0.1, volume=0.8)
        )
        mock_tts_instance.speak.return_value = mock_tts_result
        mock_tts_service.return_value = mock_tts_instance
        
        manager = VoiceManager()
        result = manager.generate_speech_response("Hello back!", "/tmp/output.wav")
        
        assert result == mock_tts_result
        assert result.success == True
        assert result.audio_path == "/tmp/response.wav"
        mock_tts_instance.speak.assert_called_once_with("Hello back!", "/tmp/output.wav")
    
    @patch('src.services.voice_manager.STTService')
    @patch('src.services.voice_manager.TTSService')
    def test_create_conversation_turn(self, mock_tts_service, mock_stt_service):
        """Test conversation turn creation"""
        # Mock services
        mock_stt_service.return_value = Mock()
        mock_tts_service.return_value = Mock()
        
        manager = VoiceManager()
        
        # Create test data
        stt_result = STTResult(
            text="How are you?",
            confidence=0.9,
            language="en",
            processing_time=1.0,
            model_used="test",
            quality_metrics=QualityMetrics(clarity=0.9, noise_level=0.1, volume=0.8)
        )
        
        ai_response = "I'm doing well, thank you!"
        
        tts_result = TTSResult(
            success=True,
            audio_path="/tmp/response.wav",
            duration=2.5,
            processing_time=1.5,
            voice_used="test",
            quality_metrics=QualityMetrics(clarity=0.9, noise_level=0.1, volume=0.8)
        )
        
        turn = manager.create_conversation_turn(stt_result, ai_response, tts_result)
        
        assert isinstance(turn, ConversationTurn)
        assert turn.user_input == stt_result
        assert turn.ai_response == ai_response
        assert turn.voice_output == tts_result
        assert len(manager.conversation_history) == 1
        assert manager.session_metrics["total_turns"] == 1
        assert manager.session_metrics["high_confidence_turns"] == 1  # 0.9 > 0.8
    
    @patch('src.services.voice_manager.STTService')
    @patch('src.services.voice_manager.TTSService')
    def test_conversation_feedback(self, mock_tts_service, mock_stt_service):
        """Test conversation feedback generation"""
        # Mock services
        mock_stt_service.return_value = Mock()
        mock_tts_service.return_value = Mock()
        
        manager = VoiceManager()
        
        # Create conversation turn
        stt_result = STTResult(
            text="Test message",
            confidence=0.7,
            language="en",
            processing_time=2.0,
            model_used="test",
            quality_metrics=QualityMetrics(clarity=0.7, noise_level=0.3, volume=0.6)
        )
        
        turn = manager.create_conversation_turn(stt_result, "Test response")
        
        # Get feedback
        feedback = manager.get_conversation_feedback()
        
        assert isinstance(feedback, dict)
        assert "confidence_level" in feedback
        assert "quality_score" in feedback
        assert "suggestions" in feedback
        assert "processing_time" in feedback
        assert feedback["confidence_level"] == "medium"  # 0.7 between 0.6 and 0.8
    
    @patch('src.services.voice_manager.STTService')
    @patch('src.services.voice_manager.TTSService')
    def test_session_quality_analysis(self, mock_tts_service, mock_stt_service):
        """Test session quality analysis"""
        # Mock services
        mock_stt_service.return_value = Mock()
        mock_tts_service.return_value = Mock()
        
        manager = VoiceManager()
        
        # Create multiple conversation turns with different quality
        turns_data = [
            (0.9, "High quality turn"),
            (0.85, "Another high quality turn"),
            (0.7, "Medium quality turn"),
            (0.4, "Low quality turn")
        ]
        
        for confidence, response in turns_data:
            stt_result = STTResult(
                text="Test input",
                confidence=confidence,
                language="en",
                processing_time=1.0,
                model_used="test",
                quality_metrics=QualityMetrics(
                    clarity=confidence, 
                    noise_level=1.0-confidence, 
                    volume=0.8
                )
            )
            manager.create_conversation_turn(stt_result, response)
        
        analysis = manager.analyze_session_quality()
        
        assert isinstance(analysis, dict)
        assert "session_summary" in analysis
        assert "quality_distribution" in analysis
        assert "recommendations" in analysis
        
        session = analysis["session_summary"]
        assert session["total_turns"] == 4
        assert session["high_confidence_percentage"] == 50.0  # 2 out of 4 high confidence
        assert 0.0 <= session["average_quality"] <= 1.0
        
        distribution = analysis["quality_distribution"]
        assert distribution["high"] == 2
        assert distribution["medium"] == 1
        assert distribution["low"] == 1
    
    @patch('src.services.voice_manager.STTService')
    @patch('src.services.voice_manager.TTSService')
    def test_confidence_threshold_updates(self, mock_tts_service, mock_stt_service):
        """Test confidence threshold updates"""
        # Mock services
        mock_stt_service.return_value = Mock()
        mock_tts_service.return_value = Mock()
        
        manager = VoiceManager()
        
        # Test initial thresholds
        assert manager.confidence_thresholds["high"] == 0.8
        assert manager.confidence_thresholds["medium"] == 0.6
        
        # Update thresholds
        new_thresholds = {"high": 0.85, "medium": 0.65, "low": 0.35}
        manager.update_confidence_thresholds(new_thresholds)
        
        assert manager.confidence_thresholds["high"] == 0.85
        assert manager.confidence_thresholds["medium"] == 0.65
        assert manager.confidence_thresholds["low"] == 0.35
    
    @patch('src.services.voice_manager.STTService')
    @patch('src.services.voice_manager.TTSService')
    def test_provider_switching(self, mock_tts_service, mock_stt_service):
        """Test dynamic provider switching"""
        # Mock initial services
        mock_stt_instance1 = Mock()
        mock_tts_instance1 = Mock()
        mock_stt_service.return_value = mock_stt_instance1
        mock_tts_service.return_value = mock_tts_instance1
        
        manager = VoiceManager()
        
        # Test STT provider switching
        mock_stt_instance2 = Mock()
        mock_stt_service.return_value = mock_stt_instance2
        
        manager.switch_stt_provider("whisper", "large")
        
        # Should have created new service
        assert manager.stt_service == mock_stt_instance2
        
        # Test TTS provider switching
        mock_tts_instance2 = Mock()
        mock_tts_service.return_value = mock_tts_instance2
        
        new_voice_profile = VoiceProfile(gender="male", speed=1.3)
        manager.switch_tts_provider("pyttsx3", new_voice_profile)
        
        assert manager.tts_service == mock_tts_instance2
    
    @patch('src.services.voice_manager.STTService')
    @patch('src.services.voice_manager.TTSService')
    def test_service_info_retrieval(self, mock_tts_service, mock_stt_service):
        """Test service information retrieval"""
        # Mock services with info
        mock_stt_instance = Mock()
        mock_stt_instance.get_model_info.return_value = {
            "provider": "faster_whisper",
            "model_name": "base",
            "available": True
        }
        
        mock_tts_instance = Mock()
        mock_tts_instance.get_model_info.return_value = {
            "provider": "coqui",
            "voice_profile": {"gender": "female"},
            "available": True
        }
        
        mock_stt_service.return_value = mock_stt_instance
        mock_tts_service.return_value = mock_tts_instance
        
        manager = VoiceManager()
        info = manager.get_service_info()
        
        assert isinstance(info, dict)
        assert "stt" in info
        assert "tts" in info
        assert "confidence_thresholds" in info
        assert "session_metrics" in info
        
        assert info["stt"]["provider"] == "faster_whisper"
        assert info["tts"]["provider"] == "coqui"
    
    @patch('src.services.voice_manager.STTService')
    @patch('src.services.voice_manager.TTSService')
    def test_session_data_export(self, mock_tts_service, mock_stt_service):
        """Test session data export"""
        # Mock services
        mock_stt_service.return_value = Mock()
        mock_tts_service.return_value = Mock()
        
        manager = VoiceManager()
        
        # Create some conversation data
        stt_result = STTResult(
            text="Export test",
            confidence=0.8,
            language="en",
            processing_time=1.0,
            model_used="test",
            quality_metrics=QualityMetrics()
        )
        
        manager.create_conversation_turn(stt_result, "Test response")
        
        exported_data = manager.export_session_data()
        
        assert isinstance(exported_data, dict)
        assert "conversation_history" in exported_data
        assert "session_metrics" in exported_data
        assert "service_info" in exported_data
        
        assert len(exported_data["conversation_history"]) == 1
        
        turn_data = exported_data["conversation_history"][0]
        assert "turn_id" in turn_data
        assert "timestamp" in turn_data
        assert "stt_result" in turn_data
        assert "ai_response" in turn_data
        assert "overall_quality" in turn_data
        assert "feedback" in turn_data
    
    @patch('src.services.voice_manager.STTService')
    @patch('src.services.voice_manager.TTSService')
    def test_empty_conversation_handling(self, mock_tts_service, mock_stt_service):
        """Test handling of empty conversation scenarios"""
        # Mock services
        mock_stt_service.return_value = Mock()
        mock_tts_service.return_value = Mock()
        
        manager = VoiceManager()
        
        # Test feedback with no conversation history
        feedback = manager.get_conversation_feedback()
        assert "error" in feedback
        assert feedback["error"] == "No conversation history"
        
        # Test analysis with no conversation data
        analysis = manager.analyze_session_quality()
        assert "error" in analysis
        assert analysis["error"] == "No conversation data"
    
    def test_recommendation_generation(self):
        """Test recommendation generation based on metrics"""
        manager = VoiceManager()
        
        # Test low confidence ratio
        recommendations_low_conf = manager._generate_recommendations(0.3, 0.8, 2.0)
        assert "audio_quality" in recommendations_low_conf
        assert "30.0%" in recommendations_low_conf["audio_quality"]
        
        # Test poor quality
        recommendations_low_qual = manager._generate_recommendations(0.8, 0.5, 2.0)
        assert "processing" in recommendations_low_qual
        
        # Test slow processing
        recommendations_slow = manager._generate_recommendations(0.8, 0.8, 5.0)
        assert "performance" in recommendations_slow
        assert "5.0s" in recommendations_slow["performance"]
        
        # Test excellent metrics
        recommendations_good = manager._generate_recommendations(0.9, 0.9, 1.0)
        assert "overall" in recommendations_good
        assert "excellent" in recommendations_good["overall"]