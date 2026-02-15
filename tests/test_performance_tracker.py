import pytest
from chatbot.performance import PerformanceTracker

@pytest.fixture
def mock_metrics_file(tmp_path):
    """Create a temporary metrics file for testing."""
    metrics_file = tmp_path / "metrics.jsonl"
    metrics_file.write_text(
        '{"session_id": "test1", "provider": "groq", "latency_ms": 100}\n'
        '{"session_id": "test2", "provider": "ollama", "latency_ms": 200}\n'
    )
    return metrics_file

def test_get_provider_stats(mock_metrics_file, monkeypatch):
    monkeypatch.setattr("chatbot.performance.METRICS_FILE", str(mock_metrics_file))
    stats = PerformanceTracker.get_provider_stats()
    assert stats["groq"]["count"] == 1
    assert stats["groq"]["total_latency"] == 100

def test_get_session_metrics(mock_metrics_file, monkeypatch):
    monkeypatch.setattr("chatbot.performance.METRICS_FILE", str(mock_metrics_file))
    metrics = PerformanceTracker.get_session_metrics("test1")
    assert len(metrics) == 1
    assert metrics[0]["provider"] == "groq"