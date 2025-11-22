"""
Quick Setup Example for Refactored Voice Services

This script demonstrates how to set up and use the refactored voice services
with proper dependency injection, caching, and error handling.
"""

from src.services.voice_services import (
    VoiceServiceFactory, CacheStrategyFactory, VoiceServiceManager,
    STTConfig, TTSConfig, ErrorHandler, ErrorRecoveryStrategy,
    MetricsCollector, WhisperSTTService, CoquiTTSService
)


def create_voice_manager():
    voice_factory = VoiceServiceFactory()
    cache_factory = CacheStrategyFactory()
    
    stt_config = STTConfig(
        model_config={"model_name": "openai/whisper-tiny"},
        sample_rate=16000,
        enable_chunking=True,
        max_chunk_duration=30.0
    )
    
    tts_config = TTSConfig(
        model_config={"model_name": "tts_models/en/ljspeech/tacotron2-DDC"},
        sample_rate=22050,
        enable_chunking=True,
        max_chunk_length=500
    )
    
    memory_cache = cache_factory.create_cache("memory", max_size=100, ttl=3600)
    
    whisper_stt = WhisperSTTService(stt_config)
    coqui_tts = CoquiTTSService(tts_config)
    
    manager = VoiceServiceManager(voice_factory, cache_factory)
    manager.register_stt_service("whisper", whisper_stt)
    manager.register_tts_service("coqui", coqui_tts)
    manager.register_cache_strategy("default", memory_cache)
    
    error_handler = ErrorHandler()
    metrics_collector = MetricsCollector()
    
    manager.add_metrics_observer(metrics_collector)
    
    recovery_strategy = ErrorRecoveryStrategy(error_handler)
    resilient_stt = recovery_strategy.create_resilient_stt_service([whisper_stt])
    resilient_tts = recovery_strategy.create_resilient_tts_service([coqui_tts])
    
    manager.register_stt_service("resilient_stt", resilient_stt)
    manager.register_tts_service("resilient_tts", resilient_tts)
    
    return manager


def usage_example():
    manager = create_voice_manager()
    
    try:
        with open("audio.wav", "rb") as f:
            audio_data = f.read()
        
        stt_result = manager.transcribe_audio(audio_data, service_name="resilient_stt")
        print(f"Transcription: {stt_result.text}")
        print(f"Confidence: {stt_result.confidence}")
        
        tts_result = manager.synthesize_speech(
            "Hello, this is a test message", 
            service_name="resilient_tts"
        )
        print(f"Generated {len(tts_result.audio_data)} bytes of audio")
        
        metrics = manager.get_metrics()
        print(f"Total requests: {metrics.request_count}")
        print(f"Success rate: {metrics.success_count / metrics.request_count * 100:.1f}%")
        
        health_status = manager.health_check()
        print(f"System health: {health_status['status']}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        manager.shutdown()


if __name__ == "__main__":
    usage_example()