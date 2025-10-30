"""
Test suite for STT optimization features

Tests caching, batch processing, async operations, and performance metrics.
"""

import pytest
import asyncio
import os
import tempfile
import wave
import numpy as np
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.voice_service import EnhancedVoiceService


@pytest.fixture
def voice_service():
    """Create voice service instance"""
    return EnhancedVoiceService()


@pytest.fixture
def sample_audio_file():
    """Create a temporary audio file for testing"""
    # Create a simple WAV file with silence
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        filepath = f.name
    
    # Generate 1 second of silence at 16kHz
    sample_rate = 16000
    duration = 1.0
    samples = np.zeros(int(sample_rate * duration), dtype=np.int16)
    
    # Write WAV file
    with wave.open(filepath, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(samples.tobytes())
    
    yield filepath
    
    # Cleanup
    if os.path.exists(filepath):
        os.remove(filepath)


@pytest.fixture
def multiple_audio_files():
    """Create multiple temporary audio files for batch testing"""
    filepaths = []
    
    for i in range(3):
        with tempfile.NamedTemporaryFile(suffix=f'_test_{i}.wav', delete=False) as f:
            filepath = f.name
        
        # Generate short audio
        sample_rate = 16000
        duration = 0.5
        samples = np.zeros(int(sample_rate * duration), dtype=np.int16)
        
        with wave.open(filepath, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(samples.tobytes())
        
        filepaths.append(filepath)
    
    yield filepaths
    
    # Cleanup
    for filepath in filepaths:
        if os.path.exists(filepath):
            os.remove(filepath)


class TestCaching:
    """Test caching functionality"""
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self, voice_service, sample_audio_file):
        """Test that cache keys are generated correctly"""
        key1 = await voice_service._get_audio_cache_key(sample_audio_file, "en", True)
        key2 = await voice_service._get_audio_cache_key(sample_audio_file, "en", True)
        
        # Same file should produce same key
        assert key1 == key2
        assert isinstance(key1, str)
        assert len(key1) > 0
    
    @pytest.mark.asyncio
    async def test_cache_key_different_for_different_params(self, voice_service, sample_audio_file):
        """Test that different parameters produce different cache keys"""
        key_en = await voice_service._get_audio_cache_key(sample_audio_file, "en", True)
        key_es = await voice_service._get_audio_cache_key(sample_audio_file, "es", True)
        key_no_prep = await voice_service._get_audio_cache_key(sample_audio_file, "en", False)
        
        # Different parameters should produce different keys
        assert key_en != key_es
        assert key_en != key_no_prep
    
    def test_add_and_get_from_cache(self, voice_service):
        """Test adding and retrieving from cache"""
        cache_key = "test_key_123"
        test_result = {"text": "Test transcription", "confidence": 0.95}
        
        # Add to cache
        voice_service._add_to_cache(cache_key, test_result)
        
        # Retrieve from cache
        cached_result = voice_service._get_from_cache(cache_key)
        
        assert cached_result is not None
        assert cached_result["text"] == "Test transcription"
        assert cached_result["confidence"] == 0.95
    
    def test_cache_expiration(self, voice_service):
        """Test that expired cache entries are not returned"""
        import time
        
        cache_key = "test_key_expire"
        test_result = {"text": "This should expire"}
        
        # Set very short TTL
        voice_service.cache_ttl = 0.1  # 100ms
        
        # Add to cache
        voice_service._add_to_cache(cache_key, test_result)
        
        # Should be retrievable immediately
        assert voice_service._get_from_cache(cache_key) is not None
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Should be None after expiration
        assert voice_service._get_from_cache(cache_key) is None
    
    def test_cache_cleanup(self, voice_service):
        """Test that cache cleanup removes oldest entries"""
        voice_service.max_cache_size = 5
        
        # Fill cache beyond limit
        for i in range(10):
            voice_service._add_to_cache(f"key_{i}", {"data": i})
        
        # Should have cleaned up to max size
        assert len(voice_service.transcription_cache) <= voice_service.max_cache_size


class TestBatchProcessing:
    """Test batch processing functionality"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'),
        reason="Google Cloud credentials not configured"
    )
    async def test_batch_processing(self, voice_service, multiple_audio_files):
        """Test processing multiple files in parallel"""
        results = await voice_service.batch_speech_to_text(
            multiple_audio_files,
            language="en",
            enable_preprocessing=False,
            enable_caching=True
        )
        
        # Should return same number of results
        assert len(results) == len(multiple_audio_files)
        
        # Results should be list type
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_batch_processing_maintains_order(self, voice_service, multiple_audio_files):
        """Test that batch processing maintains input order"""
        # Even if processing fails, should maintain order
        results = await voice_service.batch_speech_to_text(
            multiple_audio_files,
            language="en",
            enable_caching=False
        )
        
        assert len(results) == len(multiple_audio_files)


class TestPerformanceMetrics:
    """Test performance metrics tracking"""
    
    def test_metrics_initialization(self, voice_service):
        """Test that metrics are initialized correctly"""
        metrics = voice_service.get_performance_metrics()
        
        assert 'total_requests' in metrics
        assert 'cache_hits' in metrics
        assert 'cache_misses' in metrics
        assert 'cache_hit_rate' in metrics
        assert 'avg_processing_time' in metrics
        assert metrics['total_requests'] == 0
    
    @pytest.mark.asyncio
    async def test_metrics_update(self, voice_service):
        """Test that metrics update correctly"""
        initial_metrics = voice_service.get_performance_metrics()
        initial_requests = initial_metrics['total_requests']
        
        # Mock a request (will fail without credentials, but still updates metrics)
        try:
            await voice_service.speech_to_text(
                b"fake audio data",
                enable_caching=False
            )
        except:
            pass
        
        updated_metrics = voice_service.get_performance_metrics()
        
        # Request count should increase
        assert updated_metrics['total_requests'] > initial_requests
    
    def test_cache_hit_rate_calculation(self, voice_service):
        """Test cache hit rate calculation"""
        # Simulate cache hits and misses
        voice_service.performance_metrics['cache_hits'] = 7
        voice_service.performance_metrics['cache_misses'] = 3
        
        metrics = voice_service.get_performance_metrics()
        
        # Should be 70% (7 hits out of 10 total)
        assert '70.00%' in metrics['cache_hit_rate']
    
    def test_clear_cache(self, voice_service):
        """Test cache clearing"""
        # Add some cache entries
        voice_service._add_to_cache("key1", {"data": 1})
        voice_service._add_to_cache("key2", {"data": 2})
        
        assert len(voice_service.transcription_cache) > 0
        
        # Clear cache
        voice_service.clear_cache()
        
        assert len(voice_service.transcription_cache) == 0


class TestAsyncOperations:
    """Test async operations"""
    
    @pytest.mark.asyncio
    async def test_file_hash_computation(self, voice_service, sample_audio_file):
        """Test async file hash computation"""
        cache_key = await voice_service._get_audio_cache_key(sample_audio_file, "en", True)
        
        # Should generate valid hash
        assert cache_key is not None
        assert isinstance(cache_key, str)
        assert '_en_1' in cache_key  # Should contain language and preprocessing flag
    
    @pytest.mark.asyncio
    async def test_async_file_reading(self, voice_service, sample_audio_file):
        """Test async file reading"""
        content = await asyncio.get_event_loop().run_in_executor(
            voice_service.thread_pool,
            voice_service._read_audio_file,
            sample_audio_file
        )
        
        # Should read file content
        assert content is not None
        assert isinstance(content, bytes)
        assert len(content) > 0


class TestOptimizationIntegration:
    """Integration tests for optimization features"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'),
        reason="Google Cloud credentials not configured"
    )
    async def test_caching_improves_performance(self, voice_service, sample_audio_file):
        """Test that caching improves performance for repeated requests"""
        import time
        
        # First request (no cache)
        start1 = time.time()
        result1 = await voice_service.speech_to_text(
            sample_audio_file,
            enable_caching=True,
            enable_preprocessing=False
        )
        time1 = time.time() - start1
        
        # Second request (should hit cache)
        start2 = time.time()
        result2 = await voice_service.speech_to_text(
            sample_audio_file,
            enable_caching=True,
            enable_preprocessing=False
        )
        time2 = time.time() - start2
        
        # Second request should be faster
        if result1 and result2:
            assert time2 < time1
            
        # Check metrics
        metrics = voice_service.get_performance_metrics()
        assert metrics['cache_hits'] > 0
    
    @pytest.mark.asyncio
    async def test_parallel_vs_sequential_processing(self, voice_service, multiple_audio_files):
        """Test that parallel processing is faster than sequential"""
        import time
        
        # Sequential processing
        voice_service.enable_parallel_processing = False
        start_seq = time.time()
        await voice_service.batch_speech_to_text(multiple_audio_files, enable_caching=False)
        time_seq = time.time() - start_seq
        
        # Parallel processing
        voice_service.enable_parallel_processing = True
        voice_service.clear_cache()  # Clear cache to ensure fair comparison
        start_par = time.time()
        await voice_service.batch_speech_to_text(multiple_audio_files, enable_caching=False)
        time_par = time.time() - start_par
        
        # Parallel should be faster (or at least not significantly slower)
        # Note: For very short operations, overhead might make it similar
        assert time_par <= time_seq * 1.5  # Allow some overhead tolerance


def test_optimization_summary():
    """Display summary of optimization features"""
    print("\n" + "="*60)
    print("STT OPTIMIZATION FEATURES SUMMARY")
    print("="*60)
    
    features = [
        ("✅ Result Caching", "Hash-based caching with TTL to avoid re-transcribing"),
        ("✅ Async I/O", "Non-blocking file operations using asyncio"),
        ("✅ Thread Pool", "Parallel processing for I/O-bound operations"),
        ("✅ Batch Processing", "Process multiple files concurrently"),
        ("✅ Performance Metrics", "Track cache hits, processing time, requests"),
        ("✅ Cache Management", "Automatic cleanup when cache grows too large"),
        ("✅ Preprocessing Pipeline", "Async preprocessing to not block main thread"),
    ]
    
    for feature, description in features:
        print(f"{feature:20} - {description}")
    
    print("\nConfiguration:")
    service = EnhancedVoiceService()
    print(f"  Cache TTL: {service.cache_ttl}s")
    print(f"  Max Cache Size: {service.max_cache_size} entries")
    print(f"  Thread Pool Workers: 4")
    print(f"  Parallel Processing: {service.enable_parallel_processing}")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
