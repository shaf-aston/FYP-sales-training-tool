"""
Test Suite for STT Service
Tests speech-to-text functionality and confidence scoring
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.services.stt_service import STTService
from src.models.core import STTResult, ConfidenceLevel, QualityMetrics

class TestSTTService:
    """Test STT service functionality"""
    
    @patch('src.services.stt_service.validate_provider')
    @patch('src.services.stt_service.WhisperModel')
    def test_faster_whisper_initialization(self, mock_whisper_model, mock_validate):
        """Test Faster Whisper initialization"""
        mock_validate.return_value = True
        mock_model_instance = Mock()
        mock_whisper_model.return_value = mock_model_instance
        
        service = STTService(provider="faster_whisper")
        
        assert service.provider == "faster_whisper"
        assert service.model == mock_model_instance
        mock_whisper_model.assert_called_once()
    
    @patch('src.services.stt_service.validate_provider')
    @patch('src.services.stt_service.whisper')
    def test_whisper_initialization(self, mock_whisper, mock_validate):
        """Test OpenAI Whisper initialization"""
        mock_validate.return_value = True
        mock_model_instance = Mock()
        mock_whisper.load_model.return_value = mock_model_instance
        
        service = STTService(provider="whisper")
        
        assert service.provider == "whisper"
        assert service.model == mock_model_instance
        mock_whisper.load_model.assert_called_once_with("base")
    
    @patch('src.services.stt_service.validate_provider')
    def test_fallback_when_provider_unavailable(self, mock_validate):
        """Test fallback when primary provider unavailable"""
        # Make primary provider unavailable, but faster_whisper available
        mock_validate.side_effect = lambda service, provider: provider == "faster_whisper"
        
        with patch('src.services.stt_service.WhisperModel') as mock_whisper:
            mock_whisper.return_value = Mock()
            service = STTService(provider="unavailable_provider")
            
            # Should fallback to faster_whisper
            assert service.provider == "faster_whisper"
    
    @patch('src.services.stt_service.validate_provider')
    def test_no_providers_available(self, mock_validate):
        """Test behavior when no providers are available"""
        mock_validate.return_value = False
        
        service = STTService(provider="whisper")
        
        assert service.provider is None
        assert service.model is None
    
    @patch('src.services.stt_service.validate_provider')
    @patch('src.services.stt_service.WhisperModel')
    @patch('tempfile.NamedTemporaryFile')
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_faster_whisper_transcription(self, mock_unlink, mock_exists, 
                                         mock_temp_file, mock_whisper_model, mock_validate):
        """Test Faster Whisper transcription"""
        mock_validate.return_value = True
        mock_exists.return_value = True
        
        # Mock temporary file
        mock_temp_file.return_value.__enter__.return_value.name = "/tmp/audio.wav"
        
        # Mock model
        mock_model = Mock()
        mock_whisper_model.return_value = mock_model
        
        # Mock transcription segments
        mock_segment1 = Mock()
        mock_segment1.text = "Hello"
        mock_segment1.avg_logprob = -0.5
        
        mock_segment2 = Mock()
        mock_segment2.text = " world"
        mock_segment2.avg_logprob = -0.3
        
        mock_info = Mock()
        mock_info.language = "en"
        
        mock_model.transcribe.return_value = ([mock_segment1, mock_segment2], mock_info)
        
        service = STTService(provider="faster_whisper")
        result = service.transcribe("dummy_audio_data")
        
        assert isinstance(result, STTResult)
        assert result.text == "Hello world"
        assert result.language == "en"
        assert result.model_used == "faster_whisper_base"
        assert 0.0 <= result.confidence <= 1.0
    
    def test_logprob_to_confidence_conversion(self):
        """Test log probability to confidence conversion"""
        service = STTService()
        
        # Test various log probabilities
        assert service._logprob_to_confidence(0.0) == 1.0  # Perfect
        assert service._logprob_to_confidence(-1.0) == 0.5  # Medium
        assert service._logprob_to_confidence(-2.0) == 0.0  # Poor
        
        # Test boundary conditions
        confidence = service._logprob_to_confidence(-0.5)
        assert 0.5 < confidence < 1.0
    
    @patch('src.services.stt_service.validate_provider')
    def test_transcription_with_no_provider(self, mock_validate):
        """Test transcription when no provider is available"""
        mock_validate.return_value = False
        
        service = STTService(provider="unavailable")
        result = service.transcribe("dummy_audio")
        
        assert isinstance(result, STTResult)
        assert result.text == ""
        assert result.confidence == 0.0
        assert result.model_used in ["none", None]
        assert isinstance(result.quality_metrics, QualityMetrics)
    
    @patch('src.services.stt_service.validate_provider')
    @patch('src.services.stt_service.WhisperModel')
    def test_transcription_error_handling(self, mock_whisper_model, mock_validate):
        """Test transcription error handling"""
        mock_validate.return_value = True
        
        # Mock model that raises exception
        mock_model = Mock()
        mock_model.transcribe.side_effect = Exception("Transcription failed")
        mock_whisper_model.return_value = mock_model
        
        service = STTService(provider="faster_whisper")
        result = service.transcribe("dummy_audio")
        
        assert isinstance(result, STTResult)
        assert result.text == ""
        assert result.confidence == 0.0
        assert result.error == "Transcription failed"
    
    def test_quality_metrics_calculation(self):
        """Test quality metrics calculation"""
        service = STTService()
        
        # Test high quality metrics
        quality = service._calculate_quality_metrics("This is a clear test sentence", 0.9)
        
        assert isinstance(quality, QualityMetrics)
        assert quality.clarity > 0.8  # High confidence should give good clarity
        assert quality.noise_level < 0.2  # Low noise for high confidence
        assert quality.volume == 0.8  # Default volume
        
        # Test low quality metrics
        quality_low = service._calculate_quality_metrics("", 0.2)
        assert quality_low.clarity < 0.5
        assert quality_low.noise_level > 0.5
    
    def test_get_model_info(self):
        """Test model information retrieval"""
        with patch('src.services.stt_service.validate_provider') as mock_validate:
            mock_validate.return_value = False
            service = STTService(provider="test")
            
            info = service.get_model_info()
            
            assert isinstance(info, dict)
            assert "provider" in info
            assert "model_name" in info
            assert "device" in info
            assert "available" in info
            assert info["available"] == False
    
    def test_device_selection(self):
        """Test device selection logic"""
        # Test auto device selection
        service = STTService(device="auto")
        assert service.device in ["cpu", "cuda"]
        
        # Test explicit device
        service_cpu = STTService(device="cpu")
        assert service_cpu.device == "cpu"

class TestSTTConfidenceScoring:
    """Test STT confidence scoring features"""
    
    @patch('src.services.stt_service.validate_provider')
    @patch('src.services.stt_service.WhisperModel')
    def test_confidence_thresholds(self, mock_whisper_model, mock_validate):
        """Test confidence level classification"""
        mock_validate.return_value = True
        mock_whisper_model.return_value = Mock()
        
        service = STTService(provider="faster_whisper")
        
        # High confidence result
        with patch.object(service, '_transcribe_faster_whisper') as mock_transcribe:
            mock_transcribe.return_value = STTResult(
                text="Clear speech",
                confidence=0.9,
                language="en",
                processing_time=1.0,
                model_used="test",
                quality_metrics=QualityMetrics()
            )
            
            result = service.transcribe("audio")
            assert result.is_high_confidence(0.8) == True
            assert result.get_confidence_level(0.8, 0.6) == ConfidenceLevel.HIGH
        
        # Medium confidence result
        with patch.object(service, '_transcribe_faster_whisper') as mock_transcribe:
            mock_transcribe.return_value = STTResult(
                text="Okay speech",
                confidence=0.7,
                language="en",
                processing_time=1.0,
                model_used="test",
                quality_metrics=QualityMetrics()
            )
            
            result = service.transcribe("audio")
            assert result.is_high_confidence(0.8) == False
            assert result.is_acceptable(0.6) == True
            assert result.get_confidence_level(0.8, 0.6) == ConfidenceLevel.MEDIUM
    
    def test_quality_score_edge_cases(self):
        """Test quality score calculation edge cases"""
        service = STTService()
        
        # Empty text
        quality_empty = service._calculate_quality_metrics("", 0.5)
        assert quality_empty.clarity <= 0.5
        
        # Very long text
        long_text = "word " * 100
        quality_long = service._calculate_quality_metrics(long_text, 0.8)
        assert isinstance(quality_long, QualityMetrics)
        
        # Single character
        quality_short = service._calculate_quality_metrics("a", 0.8)
        assert quality_short.clarity > 0.0

class TestSTTIntegration:
    """Test STT service integration scenarios"""
    
    def test_language_handling(self):
        """Test language parameter handling"""
        with patch('src.services.stt_service.validate_provider') as mock_validate:
            with patch('src.services.stt_service.WhisperModel') as mock_whisper:
                mock_validate.return_value = True
                mock_model = Mock()
                mock_whisper.return_value = mock_model
                
                # Mock transcription
                mock_segment = Mock()
                mock_segment.text = "Hola mundo"
                mock_segment.avg_logprob = -0.5
                
                mock_info = Mock()
                mock_info.language = "es"
                
                mock_model.transcribe.return_value = ([mock_segment], mock_info)
                
                service = STTService(provider="faster_whisper")
                
                with patch('tempfile.NamedTemporaryFile'):
                    with patch('os.path.exists', return_value=True):
                        with patch('os.unlink'):
                            result = service.transcribe("audio", language="es")
                
                assert result.language == "es"
                assert result.text == "Hola mundo"
    
    def test_concurrent_transcription(self):
        """Test handling multiple transcription requests"""
        with patch('src.services.stt_service.validate_provider', return_value=True):
            with patch('src.services.stt_service.WhisperModel') as mock_whisper:
                mock_model = Mock()
                mock_whisper.return_value = mock_model
                
                service = STTService(provider="faster_whisper")
                
                # Mock multiple successful transcriptions
                with patch.object(service, '_transcribe_faster_whisper') as mock_transcribe:
                    mock_transcribe.return_value = STTResult(
                        text="Test transcription",
                        confidence=0.8,
                        language="en",
                        processing_time=1.0,
                        model_used="test",
                        quality_metrics=QualityMetrics()
                    )
                    
                    # Simulate multiple requests
                    results = []
                    for i in range(5):
                        result = service.transcribe(f"audio_{i}")
                        results.append(result)
                    
                    assert len(results) == 5
                    for result in results:
                        assert isinstance(result, STTResult)
                        assert result.text == "Test transcription"