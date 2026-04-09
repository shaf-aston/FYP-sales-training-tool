import pytest
from chatbot.analytics.performance import PerformanceTracker
from chatbot.analytics.jsonl_store import JSONLWriter

@pytest.fixture
def mock_writer(tmp_path):
    """Create a JSONLWriter backed by a temporary file with test data."""
    metrics_file = tmp_path / "metrics.jsonl"
    metrics_file.write_text(
        '{"session_id": "test1", "provider": "groq", "latency_ms": 100}\n'
        '{"session_id": "test2", "provider": "sambanova", "latency_ms": 200}\n'
    )
    return JSONLWriter(str(metrics_file), max_lines=5000, keep_after_rotation=2500)

def test_get_provider_stats(mock_writer, monkeypatch):
    monkeypatch.setattr("chatbot.analytics.performance._get_writer", lambda: mock_writer)
    monkeypatch.setattr("chatbot.analytics.performance._stats_cache", {"data": {}, "ts": 0.0})
    stats = PerformanceTracker.get_provider_stats()
    assert stats["groq"]["count"] == 1
    assert stats["groq"]["total_latency"] == 100

def test_get_session_metrics(mock_writer, monkeypatch):
    monkeypatch.setattr("chatbot.analytics.performance._get_writer", lambda: mock_writer)
    metrics = PerformanceTracker.get_session_metrics("test1")
    assert len(metrics) == 1
    assert metrics[0]["provider"] == "groq"
