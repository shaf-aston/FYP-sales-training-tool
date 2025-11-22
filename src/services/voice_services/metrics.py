import time
import logging
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from threading import Lock
import statistics

from ..interfaces import MetricsObserver, QualityMetrics


@dataclass
class PerformanceMetrics:
    operation: str
    timestamp: datetime
    duration: float
    success: bool
    error_message: Optional[str] = None
    service_name: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class QualityAnalysis:
    timestamp: datetime
    text_length: int
    audio_duration: float
    confidence: float
    quality_score: float
    language: str
    service_name: str
    metadata: Dict[str, Any] = None


class MetricsCollector(MetricsObserver):
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self._performance_history: List[PerformanceMetrics] = []
        self._quality_history: List[QualityAnalysis] = []
        self._lock = Lock()
        self.logger = logging.getLogger(__name__)
    
    def on_event(self, event: str, data: Any):
        timestamp = datetime.now()
        
        try:
            if event == "transcription_completed":
                self._record_stt_metrics(data, timestamp, True)
            elif event == "transcription_error":
                self._record_error_metrics("transcription", data, timestamp)
            elif event == "synthesis_completed":
                self._record_tts_metrics(data, timestamp, True)
            elif event == "synthesis_error":
                self._record_error_metrics("synthesis", data, timestamp)
        except Exception as e:
            self.logger.error(f"Error recording metrics: {e}")
    
    def _record_stt_metrics(self, result, timestamp: datetime, success: bool):
        with self._lock:
            perf_metric = PerformanceMetrics(
                operation="transcription",
                timestamp=timestamp,
                duration=result.processing_time,
                success=success,
                service_name=result.metadata.get("backend", "unknown"),
                metadata=result.metadata
            )
            self._add_performance_metric(perf_metric)
            
            quality_analysis = QualityAnalysis(
                timestamp=timestamp,
                text_length=len(result.text),
                audio_duration=result.audio_duration,
                confidence=result.confidence,
                quality_score=self._calculate_stt_quality(result),
                language=result.language,
                service_name=result.metadata.get("backend", "unknown"),
                metadata=result.metadata
            )
            self._add_quality_analysis(quality_analysis)
    
    def _record_tts_metrics(self, result, timestamp: datetime, success: bool):
        with self._lock:
            perf_metric = PerformanceMetrics(
                operation="synthesis",
                timestamp=timestamp,
                duration=result.processing_time,
                success=success,
                service_name=result.metadata.get("backend", "unknown"),
                metadata=result.metadata
            )
            self._add_performance_metric(perf_metric)
            
            quality_analysis = QualityAnalysis(
                timestamp=timestamp,
                text_length=len(result.text),
                audio_duration=result.duration,
                confidence=1.0,
                quality_score=self._calculate_tts_quality(result),
                language="unknown",
                service_name=result.metadata.get("backend", "unknown"),
                metadata=result.metadata
            )
            self._add_quality_analysis(quality_analysis)
    
    def _record_error_metrics(self, operation: str, error, timestamp: datetime):
        with self._lock:
            perf_metric = PerformanceMetrics(
                operation=operation,
                timestamp=timestamp,
                duration=0.0,
                success=False,
                error_message=str(error),
                metadata={"error_type": type(error).__name__}
            )
            self._add_performance_metric(perf_metric)
    
    def _add_performance_metric(self, metric: PerformanceMetrics):
        self._performance_history.append(metric)
        if len(self._performance_history) > self.max_history:
            self._performance_history.pop(0)
    
    def _add_quality_analysis(self, analysis: QualityAnalysis):
        self._quality_history.append(analysis)
        if len(self._quality_history) > self.max_history:
            self._quality_history.pop(0)
    
    def _calculate_stt_quality(self, result) -> float:
        quality_score = result.confidence
        
        if result.metadata.get("has_timestamps", False):
            quality_score += 0.1
        
        if len(result.text) > 0:
            word_count = len(result.text.split())
            if word_count > 5:
                quality_score += 0.05
        
        if result.processing_time < 2.0:
            quality_score += 0.1
        
        return min(quality_score, 1.0)
    
    def _calculate_tts_quality(self, result) -> float:
        quality_score = 0.8
        
        if result.processing_time < result.duration * 0.5:
            quality_score += 0.1
        
        if len(result.text) > 10:
            quality_score += 0.05
        
        if result.metadata.get("chunks_count", 1) == 1:
            quality_score += 0.05
        
        return min(quality_score, 1.0)
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            recent_metrics = [m for m in self._performance_history 
                            if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return {"error": "No metrics available for the specified period"}
        
        total_requests = len(recent_metrics)
        successful_requests = len([m for m in recent_metrics if m.success])
        failed_requests = total_requests - successful_requests
        
        durations = [m.duration for m in recent_metrics if m.success and m.duration > 0]
        
        summary = {
            "period_hours": hours,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": successful_requests / total_requests if total_requests > 0 else 0,
            "average_duration": statistics.mean(durations) if durations else 0,
            "median_duration": statistics.median(durations) if durations else 0,
            "min_duration": min(durations) if durations else 0,
            "max_duration": max(durations) if durations else 0,
            "operations": {},
            "services": {}
        }
        
        operations = {}
        services = {}
        
        for metric in recent_metrics:
            op = metric.operation
            if op not in operations:
                operations[op] = {"count": 0, "success": 0, "durations": []}
            
            operations[op]["count"] += 1
            if metric.success:
                operations[op]["success"] += 1
                if metric.duration > 0:
                    operations[op]["durations"].append(metric.duration)
            
            if metric.service_name:
                if metric.service_name not in services:
                    services[metric.service_name] = {"count": 0, "success": 0, "durations": []}
                
                services[metric.service_name]["count"] += 1
                if metric.success:
                    services[metric.service_name]["success"] += 1
                    if metric.duration > 0:
                        services[metric.service_name]["durations"].append(metric.duration)
        
        for op, stats in operations.items():
            durations = stats["durations"]
            summary["operations"][op] = {
                "count": stats["count"],
                "success_rate": stats["success"] / stats["count"] if stats["count"] > 0 else 0,
                "average_duration": statistics.mean(durations) if durations else 0
            }
        
        for service, stats in services.items():
            durations = stats["durations"]
            summary["services"][service] = {
                "count": stats["count"],
                "success_rate": stats["success"] / stats["count"] if stats["count"] > 0 else 0,
                "average_duration": statistics.mean(durations) if durations else 0
            }
        
        return summary
    
    def get_quality_summary(self, hours: int = 24) -> Dict[str, Any]:
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            recent_quality = [q for q in self._quality_history 
                            if q.timestamp >= cutoff_time]
        
        if not recent_quality:
            return {"error": "No quality data available for the specified period"}
        
        quality_scores = [q.quality_score for q in recent_quality]
        confidence_scores = [q.confidence for q in recent_quality]
        text_lengths = [q.text_length for q in recent_quality]
        audio_durations = [q.audio_duration for q in recent_quality]
        
        summary = {
            "period_hours": hours,
            "total_analyses": len(recent_quality),
            "average_quality": statistics.mean(quality_scores),
            "median_quality": statistics.median(quality_scores),
            "average_confidence": statistics.mean(confidence_scores),
            "median_confidence": statistics.median(confidence_scores),
            "average_text_length": statistics.mean(text_lengths),
            "average_audio_duration": statistics.mean(audio_durations),
            "quality_distribution": self._calculate_distribution(quality_scores),
            "confidence_distribution": self._calculate_distribution(confidence_scores),
            "services": {}
        }
        
        services = {}
        for analysis in recent_quality:
            service = analysis.service_name
            if service not in services:
                services[service] = {
                    "count": 0,
                    "quality_scores": [],
                    "confidence_scores": []
                }
            
            services[service]["count"] += 1
            services[service]["quality_scores"].append(analysis.quality_score)
            services[service]["confidence_scores"].append(analysis.confidence)
        
        for service, stats in services.items():
            quality_scores = stats["quality_scores"]
            confidence_scores = stats["confidence_scores"]
            summary["services"][service] = {
                "count": stats["count"],
                "average_quality": statistics.mean(quality_scores),
                "average_confidence": statistics.mean(confidence_scores)
            }
        
        return summary
    
    def _calculate_distribution(self, values: List[float]) -> Dict[str, int]:
        if not values:
            return {}
        
        distribution = {
            "0.0-0.2": 0,
            "0.2-0.4": 0,
            "0.4-0.6": 0,
            "0.6-0.8": 0,
            "0.8-1.0": 0
        }
        
        for value in values:
            if value < 0.2:
                distribution["0.0-0.2"] += 1
            elif value < 0.4:
                distribution["0.2-0.4"] += 1
            elif value < 0.6:
                distribution["0.4-0.6"] += 1
            elif value < 0.8:
                distribution["0.6-0.8"] += 1
            else:
                distribution["0.8-1.0"] += 1
        
        return distribution
    
    def get_error_analysis(self, hours: int = 24) -> Dict[str, Any]:
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            error_metrics = [m for m in self._performance_history 
                           if m.timestamp >= cutoff_time and not m.success]
        
        if not error_metrics:
            return {"message": "No errors in the specified period"}
        
        error_types = {}
        operation_errors = {}
        
        for metric in error_metrics:
            error_type = metric.metadata.get("error_type", "Unknown") if metric.metadata else "Unknown"
            
            if error_type not in error_types:
                error_types[error_type] = 0
            error_types[error_type] += 1
            
            operation = metric.operation
            if operation not in operation_errors:
                operation_errors[operation] = 0
            operation_errors[operation] += 1
        
        return {
            "period_hours": hours,
            "total_errors": len(error_metrics),
            "error_types": error_types,
            "operation_errors": operation_errors,
            "recent_errors": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "operation": m.operation,
                    "error": m.error_message,
                    "service": m.service_name
                }
                for m in error_metrics[-10:]
            ]
        }
    
    def export_metrics(self, format: str = "json") -> str:
        with self._lock:
            data = {
                "performance_metrics": [asdict(m) for m in self._performance_history],
                "quality_analyses": [asdict(q) for q in self._quality_history],
                "export_timestamp": datetime.now().isoformat()
            }
        
        if format.lower() == "json":
            return json.dumps(data, default=str, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def clear_history(self, older_than_hours: int = None):
        if older_than_hours:
            cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
            with self._lock:
                self._performance_history = [m for m in self._performance_history 
                                           if m.timestamp >= cutoff_time]
                self._quality_history = [q for q in self._quality_history 
                                       if q.timestamp >= cutoff_time]
        else:
            with self._lock:
                self._performance_history.clear()
                self._quality_history.clear()


class RealTimeMetricsObserver(MetricsObserver):
    
    def __init__(self, callback_function=None):
        self.callback = callback_function
        self.logger = logging.getLogger(__name__)
        self._event_count = 0
        self._start_time = time.time()
    
    def on_event(self, event: str, data: Any):
        self._event_count += 1
        
        event_info = {
            "event": event,
            "timestamp": datetime.now().isoformat(),
            "event_count": self._event_count,
            "uptime": time.time() - self._start_time
        }
        
        if hasattr(data, 'processing_time'):
            event_info["processing_time"] = data.processing_time
        
        if hasattr(data, 'confidence'):
            event_info["confidence"] = data.confidence
        
        if self.callback:
            try:
                self.callback(event_info)
            except Exception as e:
                self.logger.error(f"Real-time metrics callback error: {e}")
        
        self.logger.info(f"Event: {event}, Count: {self._event_count}")


class FileMetricsLogger(MetricsObserver):
    
    def __init__(self, log_file_path: str):
        self.log_file = log_file_path
        self.logger = logging.getLogger(__name__)
    
    def on_event(self, event: str, data: Any):
        timestamp = datetime.now().isoformat()
        
        log_entry = {
            "timestamp": timestamp,
            "event": event,
            "data_summary": self._summarize_data(data)
        }
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to write metrics log: {e}")
    
    def _summarize_data(self, data) -> Dict[str, Any]:
        if hasattr(data, '__dict__'):
            return {k: str(v) for k, v in data.__dict__.items()}
        elif isinstance(data, Exception):
            return {"error": str(data), "type": type(data).__name__}
        else:
            return {"value": str(data)}