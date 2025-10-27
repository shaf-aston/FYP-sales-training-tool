"""
Continuous Improvement Loop Implementation
Automated feedback integration and iterative model enhancement
"""
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict, deque
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class ImprovementMetric:
    """Metric for tracking improvement"""
    metric_name: str
    current_value: float
    target_value: float
    trend: str  # 'improving', 'declining', 'stable'
    priority: str  # 'high', 'medium', 'low'
    last_updated: str

@dataclass
class FeedbackPattern:
    """Pattern identified from user feedback"""
    pattern_id: str
    description: str
    frequency: int
    impact_score: float
    suggested_action: str
    examples: List[str]

@dataclass
class ModelPerformanceSnapshot:
    """Snapshot of model performance at a point in time"""
    timestamp: str
    model_version: str
    performance_metrics: Dict[str, float]
    user_satisfaction: float
    training_data_size: int
    validation_scores: Dict[str, float]

class ContinuousImprovementEngine:
    """Engine for continuous model improvement"""
    
    def __init__(self, improvement_config_path: str = "./training/validation/improvement_config.json"):
        self.config_path = improvement_config_path
        self.config = self._load_improvement_config()
        self.performance_history = deque(maxlen=100)  # Last 100 snapshots
        self.feedback_patterns = {}
        self.improvement_metrics = {}
        self.scheduled_improvements = []
        
    def _load_improvement_config(self) -> Dict:
        """Load improvement configuration"""
        default_config = {
            "improvement_thresholds": {
                "user_satisfaction_min": 0.8,
                "performance_decline_threshold": 0.05,
                "feedback_frequency_threshold": 10,
                "retraining_interval_days": 30
            },
            "monitoring_metrics": [
                "conversation_quality",
                "objection_handling_effectiveness", 
                "closing_success_rate",
                "user_engagement",
                "response_relevance"
            ],
            "improvement_actions": {
                "retrain_model": {"trigger_threshold": 0.1, "priority": "high"},
                "update_training_data": {"trigger_threshold": 0.05, "priority": "medium"},
                "adjust_parameters": {"trigger_threshold": 0.03, "priority": "low"}
            },
            "feedback_integration": {
                "auto_apply_threshold": 0.9,
                "review_required_threshold": 0.7,
                "batch_size": 50
            }
        }
        
        if Path(self.config_path).exists():
            with open(self.config_path, 'r') as f:
                loaded_config = json.load(f)
                # Merge with defaults
                for key, value in loaded_config.items():
                    if isinstance(value, dict) and key in default_config:
                        default_config[key].update(value)
                    else:
                        default_config[key] = value
        else:
            # Save default config
            Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
        
        return default_config
    
    def record_performance_snapshot(self, model_version: str, performance_data: Dict):
        """Record current model performance"""
        snapshot = ModelPerformanceSnapshot(
            timestamp=datetime.now().isoformat(),
            model_version=model_version,
            performance_metrics=performance_data.get("metrics", {}),
            user_satisfaction=performance_data.get("user_satisfaction", 0.0),
            training_data_size=performance_data.get("training_data_size", 0),
            validation_scores=performance_data.get("validation_scores", {})
        )
        
        self.performance_history.append(snapshot)
        
        # Update improvement metrics
        self._update_improvement_metrics(snapshot)
        
        # Check for improvement triggers
        self._check_improvement_triggers()
        
        logger.info(f"Recorded performance snapshot for model {model_version}")
    
    def _update_improvement_metrics(self, snapshot: ModelPerformanceSnapshot):
        """Update improvement metrics based on new snapshot"""
        for metric_name in self.config["monitoring_metrics"]:
            current_value = snapshot.performance_metrics.get(metric_name, 0.0)
            
            if metric_name not in self.improvement_metrics:
                # Initialize metric
                self.improvement_metrics[metric_name] = ImprovementMetric(
                    metric_name=metric_name,
                    current_value=current_value,
                    target_value=self._get_target_value(metric_name),
                    trend='stable',
                    priority='medium',
                    last_updated=snapshot.timestamp
                )
            else:
                # Update existing metric
                metric = self.improvement_metrics[metric_name]
                old_value = metric.current_value
                metric.current_value = current_value
                metric.last_updated = snapshot.timestamp
                
                # Determine trend
                if current_value > old_value * 1.02:  # 2% improvement
                    metric.trend = 'improving'
                elif current_value < old_value * 0.98:  # 2% decline
                    metric.trend = 'declining'
                else:
                    metric.trend = 'stable'
                
                # Update priority based on gap from target
                gap = abs(metric.target_value - current_value) / metric.target_value
                if gap > 0.2:
                    metric.priority = 'high'
                elif gap > 0.1:
                    metric.priority = 'medium'
                else:
                    metric.priority = 'low'
    
    def _get_target_value(self, metric_name: str) -> float:
        """Get target value for improvement metric"""
        targets = {
            "conversation_quality": 0.9,
            "objection_handling_effectiveness": 0.85,
            "closing_success_rate": 0.8,
            "user_engagement": 0.9,
            "response_relevance": 0.95
        }
        return targets.get(metric_name, 0.8)
    
    def analyze_feedback_patterns(self, feedback_data: List[Dict]) -> List[FeedbackPattern]:
        """Analyze patterns in user feedback"""
        patterns = []
        
        # Group feedback by type/category
        feedback_groups = defaultdict(list)
        for feedback in feedback_data:
            category = feedback.get("category", "general")
            feedback_groups[category].append(feedback)
        
        # Analyze each group for patterns
        for category, feedbacks in feedback_groups.items():
            if len(feedbacks) >= 3:  # Minimum threshold for pattern
                pattern = self._extract_feedback_pattern(category, feedbacks)
                if pattern:
                    patterns.append(pattern)
                    self.feedback_patterns[pattern.pattern_id] = pattern
        
        return patterns
    
    def _extract_feedback_pattern(self, category: str, feedbacks: List[Dict]) -> Optional[FeedbackPattern]:
        """Extract pattern from similar feedback items"""
        if not feedbacks:
            return None
        
        # Calculate frequency and impact
        frequency = len(feedbacks)
        impact_scores = [f.get("impact_score", 0.5) for f in feedbacks]
        avg_impact = np.mean(impact_scores)
        
        # Generate description and action
        common_issues = self._identify_common_issues(feedbacks)
        description = f"Recurring {category} issues: {', '.join(common_issues[:3])}"
        
        suggested_action = self._suggest_improvement_action(category, common_issues, avg_impact)
        
        # Get examples
        examples = [f["text"][:100] + "..." for f in feedbacks[:3] if "text" in f]
        
        pattern_id = f"{category}_{datetime.now().strftime('%Y%m%d')}"
        
        return FeedbackPattern(
            pattern_id=pattern_id,
            description=description,
            frequency=frequency,
            impact_score=avg_impact,
            suggested_action=suggested_action,
            examples=examples
        )
    
    def _identify_common_issues(self, feedbacks: List[Dict]) -> List[str]:
        """Identify common issues from feedback"""
        issues = []
        
        # Simple keyword-based analysis (could be enhanced with NLP)
        issue_keywords = {
            "response_quality": ["poor", "bad", "wrong", "irrelevant"],
            "understanding": ["misunderstood", "didn't get", "missed point"],
            "personality": ["robotic", "unnatural", "inconsistent"],
            "knowledge": ["incorrect", "outdated", "missing information"]
        }
        
        feedback_text = " ".join([f.get("text", "") for f in feedbacks]).lower()
        
        for issue_type, keywords in issue_keywords.items():
            if any(keyword in feedback_text for keyword in keywords):
                issues.append(issue_type)
        
        return issues
    
    def _suggest_improvement_action(self, category: str, issues: List[str], impact: float) -> str:
        """Suggest improvement action based on feedback analysis"""
        if impact > 0.8:
            priority = "urgent"
        elif impact > 0.6:
            priority = "high priority"
        else:
            priority = "medium priority"
        
        action_templates = {
            "response_quality": f"Review and improve response generation logic ({priority})",
            "understanding": f"Enhance context understanding and intent recognition ({priority})",
            "personality": f"Refine persona consistency and natural language patterns ({priority})",
            "knowledge": f"Update knowledge base and training data ({priority})"
        }
        
        if issues:
            return action_templates.get(issues[0], f"Address {category} issues ({priority})")
        else:
            return f"Investigate {category} feedback patterns ({priority})"
    
    def _check_improvement_triggers(self):
        """Check if any improvement actions should be triggered"""
        if len(self.performance_history) < 2:
            return
        
        current = self.performance_history[-1]
        previous = self.performance_history[-2]
        
        # Check for performance decline
        for metric_name in self.config["monitoring_metrics"]:
            current_value = current.performance_metrics.get(metric_name, 0.0)
            previous_value = previous.performance_metrics.get(metric_name, 0.0)
            
            if previous_value > 0:  # Avoid division by zero
                decline = (previous_value - current_value) / previous_value
                
                threshold = self.config["improvement_thresholds"]["performance_decline_threshold"]
                if decline > threshold:
                    self._schedule_improvement_action("performance_decline", {
                        "metric": metric_name,
                        "decline": decline,
                        "current_value": current_value,
                        "previous_value": previous_value
                    })
        
        # Check user satisfaction
        if current.user_satisfaction < self.config["improvement_thresholds"]["user_satisfaction_min"]:
            self._schedule_improvement_action("low_satisfaction", {
                "satisfaction_score": current.user_satisfaction,
                "threshold": self.config["improvement_thresholds"]["user_satisfaction_min"]
            })
    
    def _schedule_improvement_action(self, trigger_type: str, context: Dict):
        """Schedule an improvement action"""
        action = {
            "trigger_type": trigger_type,
            "context": context,
            "scheduled_at": datetime.now().isoformat(),
            "status": "pending",
            "priority": self._determine_action_priority(trigger_type, context)
        }
        
        self.scheduled_improvements.append(action)
        logger.info(f"Scheduled improvement action for {trigger_type}")
    
    def _determine_action_priority(self, trigger_type: str, context: Dict) -> str:
        """Determine priority for improvement action"""
        if trigger_type == "performance_decline":
            decline = context.get("decline", 0.0)
            if decline > 0.15:  # 15% decline
                return "urgent"
            elif decline > 0.1:  # 10% decline
                return "high"
            else:
                return "medium"
        elif trigger_type == "low_satisfaction":
            satisfaction = context.get("satisfaction_score", 1.0)
            if satisfaction < 0.6:
                return "urgent"
            elif satisfaction < 0.7:
                return "high"
            else:
                return "medium"
        
        return "medium"
    
    async def execute_improvement_cycle(self) -> Dict:
        """Execute a complete improvement cycle"""
        logger.info("Starting continuous improvement cycle")
        
        cycle_results = {
            "cycle_start": datetime.now().isoformat(),
            "actions_executed": [],
            "patterns_identified": len(self.feedback_patterns),
            "metrics_updated": len(self.improvement_metrics),
            "recommendations": []
        }
        
        # Process scheduled improvements
        for action in self.scheduled_improvements:
            if action["status"] == "pending":
                result = await self._execute_improvement_action(action)
                action["status"] = "completed"
                action["result"] = result
                cycle_results["actions_executed"].append(action)
        
        # Generate recommendations
        recommendations = self._generate_improvement_recommendations()
        cycle_results["recommendations"] = recommendations
        
        # Update cycle results
        cycle_results["cycle_end"] = datetime.now().isoformat()
        
        # Save cycle results
        self._save_improvement_cycle_results(cycle_results)
        
        logger.info(f"Improvement cycle completed: {len(cycle_results['actions_executed'])} actions executed")
        
        return cycle_results
    
    async def _execute_improvement_action(self, action: Dict) -> Dict:
        """Execute a specific improvement action"""
        trigger_type = action["trigger_type"]
        
        if trigger_type == "performance_decline":
            return await self._handle_performance_decline(action["context"])
        elif trigger_type == "low_satisfaction":
            return await self._handle_low_satisfaction(action["context"])
        else:
            return {"status": "no_handler", "message": f"No handler for {trigger_type}"}
    
    async def _handle_performance_decline(self, context: Dict) -> Dict:
        """Handle performance decline"""
        metric = context["metric"]
        decline = context["decline"]
        
        logger.info(f"Handling performance decline in {metric}: {decline:.2%}")
        
        # Simulate improvement actions
        actions_taken = []
        
        if decline > 0.1:  # Significant decline
            actions_taken.append("Scheduled model retraining")
            actions_taken.append("Updated training data filtering")
        else:
            actions_taken.append("Adjusted model parameters")
            actions_taken.append("Enhanced validation rules")
        
        return {
            "status": "handled",
            "metric": metric,
            "decline": decline,
            "actions_taken": actions_taken
        }
    
    async def _handle_low_satisfaction(self, context: Dict) -> Dict:
        """Handle low user satisfaction"""
        satisfaction = context["satisfaction_score"]
        
        logger.info(f"Handling low user satisfaction: {satisfaction:.2f}")
        
        # Simulate satisfaction improvement actions
        actions_taken = [
            "Enhanced persona response generation",
            "Improved objection handling patterns",
            "Updated feedback integration"
        ]
        
        return {
            "status": "handled",
            "satisfaction_score": satisfaction,
            "actions_taken": actions_taken
        }
    
    def _generate_improvement_recommendations(self) -> List[Dict]:
        """Generate improvement recommendations"""
        recommendations = []
        
        # Analyze metrics for recommendations
        for metric_name, metric in self.improvement_metrics.items():
            if metric.trend == 'declining' and metric.priority in ['high', 'urgent']:
                recommendations.append({
                    "type": "metric_improvement",
                    "metric": metric_name,
                    "current_value": metric.current_value,
                    "target_value": metric.target_value,
                    "recommendation": f"Focus on improving {metric_name} - currently declining",
                    "priority": metric.priority
                })
        
        # Analyze feedback patterns for recommendations
        high_impact_patterns = [
            pattern for pattern in self.feedback_patterns.values()
            if pattern.impact_score > 0.7 and pattern.frequency > 5
        ]
        
        for pattern in high_impact_patterns:
            recommendations.append({
                "type": "feedback_pattern",
                "pattern_id": pattern.pattern_id,
                "description": pattern.description,
                "frequency": pattern.frequency,
                "recommendation": pattern.suggested_action,
                "priority": "high" if pattern.impact_score > 0.8 else "medium"
            })
        
        return recommendations
    
    def _save_improvement_cycle_results(self, results: Dict):
        """Save improvement cycle results"""
        results_path = Path("./training/validation/improvement_cycles")
        results_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"improvement_cycle_{timestamp}.json"
        
        with open(results_path / filename, 'w') as f:
            json.dump(results, f, indent=2)
    
    def get_improvement_status(self) -> Dict:
        """Get current improvement status"""
        return {
            "performance_snapshots": len(self.performance_history),
            "improvement_metrics": {
                name: {
                    "current_value": metric.current_value,
                    "target_value": metric.target_value,
                    "trend": metric.trend,
                    "priority": metric.priority
                }
                for name, metric in self.improvement_metrics.items()
            },
            "feedback_patterns": len(self.feedback_patterns),
            "scheduled_improvements": len([a for a in self.scheduled_improvements if a["status"] == "pending"]),
            "last_update": max([metric.last_updated for metric in self.improvement_metrics.values()]) if self.improvement_metrics else None
        }

async def main():
    """Demo continuous improvement system"""
    logger.info("Initializing Continuous Improvement Engine")
    
    engine = ContinuousImprovementEngine()
    
    # Simulate performance data
    mock_performance = {
        "metrics": {
            "conversation_quality": 0.82,
            "objection_handling_effectiveness": 0.79,
            "closing_success_rate": 0.75,
            "user_engagement": 0.88,
            "response_relevance": 0.91
        },
        "user_satisfaction": 0.78,
        "training_data_size": 1250,
        "validation_scores": {
            "accuracy": 0.85,
            "relevance": 0.82
        }
    }
    
    # Record performance
    engine.record_performance_snapshot("v1.2.0", mock_performance)
    
    # Simulate feedback data
    mock_feedback = [
        {"category": "response_quality", "text": "Response was not relevant to my question", "impact_score": 0.8},
        {"category": "response_quality", "text": "Answer didn't address the objection properly", "impact_score": 0.7},
        {"category": "personality", "text": "Felt robotic and unnatural", "impact_score": 0.6}
    ]
    
    # Analyze feedback patterns
    patterns = engine.analyze_feedback_patterns(mock_feedback)
    logger.info(f"Identified {len(patterns)} feedback patterns")
    
    # Execute improvement cycle
    cycle_results = await engine.execute_improvement_cycle()
    logger.info(f"Improvement cycle results: {len(cycle_results['recommendations'])} recommendations")
    
    # Show status
    status = engine.get_improvement_status()
    logger.info(f"Current status: {status['scheduled_improvements']} pending improvements")

if __name__ == "__main__":
    asyncio.run(main())