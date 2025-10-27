"""
Integration Tests for Storage Services

Tests the Session Log Store and Quality Metrics Store integration
with the existing chatbot system components.
"""

import sys
import os
import unittest
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import json

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.session_service import (
    SessionLogStore, TrainingSession, ConversationTurn, SessionDatabase
)
from services.quality_metrics_service import (
    QualityMetricsStore, QualityMetric, ImprovementRecommendation, 
    SkillAssessment, QualityMetricsDatabase
)
# Mock services for testing without complex dependencies
class MockFeedbackService:
    """Mock feedback service for testing purposes"""
    def __init__(self):
        pass

class MockChatService:
    """Mock chat service for testing purposes"""
    def __init__(self):
        pass

class TestSessionLogStore(unittest.TestCase):
    """Test SessionLogStore functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.session_store = SessionLogStore(db_path=os.path.join(self.temp_dir, "test_sessions.db"))
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)
    
    def test_session_lifecycle(self):
        """Test complete session lifecycle"""
        # Start session
        session_id = self.session_store.start_session(
            user_id="test_user_001",
            persona_id="mary",
            session_type="sales_training",
            session_goals=["improve_objection_handling", "practice_closing"],
            metadata={"test": True}
        )
        
        self.assertIsNotNone(session_id)
        self.assertTrue(len(session_id) > 0)
        
        # Log conversation turns
        turn1_success = self.session_store.log_conversation_turn(
            session_id=session_id,
            user_message="Hello, I'm interested in your product",
            bot_response="Great! I'm Mary from TechSolutions. What brings you here today?",
            persona_used="mary",
            response_time=0.8,
            context_tokens=150,
            feedback_scores={"clarity": 85.0, "rapport_building": 78.0},
            user_emotions=["curious", "engaged"],
            bot_confidence=0.92
        )
        
        self.assertTrue(turn1_success)
        
        turn2_success = self.session_store.log_conversation_turn(
            session_id=session_id,
            user_message="I'm not sure if this is the right fit for us",
            bot_response="I understand your concern. Can you tell me more about what you're looking for?",
            persona_used="mary",
            response_time=1.2,
            context_tokens=180,
            feedback_scores={"clarity": 88.0, "objection_handling": 82.0},
            user_emotions=["uncertain", "cautious"],
            bot_confidence=0.87
        )
        
        self.assertTrue(turn2_success)
        
        # End session
        end_success = self.session_store.end_session(
            session_id=session_id,
            performance_metrics={
                "average_response_time": 1.0,
                "total_turns": 2,
                "engagement_level": "high"
            },
            final_scores={
                "clarity": 86.5,
                "objection_handling": 82.0,
                "rapport_building": 78.0
            },
            session_notes="Good practice session with focus on objection handling"
        )
        
        self.assertTrue(end_success)
        
        # Retrieve session details
        session_details = self.session_store.get_session_details(session_id)
        self.assertIsNotNone(session_details)
        self.assertEqual(session_details['session']['user_id'], "test_user_001")
        self.assertEqual(len(session_details['conversation']), 2)
        self.assertEqual(session_details['summary']['total_turns'], 2)
        self.assertEqual(session_details['summary']['status'], 'completed')
    
    def test_user_history_retrieval(self):
        """Test retrieving user session history"""
        user_id = "history_test_user"
        
        # Create multiple sessions
        session_ids = []
        for i in range(3):
            session_id = self.session_store.start_session(
                user_id=user_id,
                persona_id="jake",
                session_type=f"training_type_{i}",
                session_goals=[f"goal_{i}"]
            )
            session_ids.append(session_id)
            
            # Add a conversation turn to each session
            self.session_store.log_conversation_turn(
                session_id=session_id,
                user_message=f"Test message {i}",
                bot_response=f"Test response {i}",
                persona_used="jake",
                response_time=0.5,
                context_tokens=100
            )
            
            # End session
            self.session_store.end_session(session_id)
        
        # Get user history
        history = self.session_store.get_user_history(
            user_id=user_id,
            include_conversations=True
        )
        
        self.assertEqual(len(history), 3)
        
        # Check that conversations are included
        for session_data in history:
            self.assertIn('conversation', session_data)
            self.assertEqual(len(session_data['conversation']), 1)
    
    def test_session_analytics(self):
        """Test session analytics generation"""
        user_id = "analytics_test_user"
        
        # Create test sessions with metrics
        for i in range(5):
            session_id = self.session_store.start_session(
                user_id=user_id,
                persona_id="sarah",
                session_type="sales_training"
            )
            
            # Add multiple turns per session
            for j in range(3):
                self.session_store.log_conversation_turn(
                    session_id=session_id,
                    user_message=f"Message {i}-{j}",
                    bot_response=f"Response {i}-{j}",
                    persona_used="sarah",
                    response_time=0.7 + (j * 0.1),
                    context_tokens=120 + (j * 10),
                    feedback_scores={"clarity": 80 + i, "empathy": 75 + j}
                )
            
            self.session_store.end_session(session_id)
        
        # Get analytics
        analytics = self.session_store.get_session_analytics(user_id=user_id)
        
        self.assertIsNotNone(analytics)
        self.assertEqual(analytics['total_sessions'], 5)
        self.assertEqual(analytics['completed_sessions'], 5)
        self.assertEqual(analytics['total_turns'], 15)
        self.assertGreater(analytics['avg_response_time'], 0)
        self.assertGreater(analytics['avg_context_tokens'], 0)

class TestQualityMetricsStore(unittest.TestCase):
    """Test QualityMetricsStore functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.metrics_store = QualityMetricsStore(db_path=os.path.join(self.temp_dir, "test_metrics.db"))
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)
    
    def test_session_metrics_recording(self):
        """Test recording session metrics"""
        user_id = "metrics_test_user"
        session_id = "test_session_001"
        
        feedback_scores = {
            "clarity": 85.0,
            "objection_handling": 78.0,
            "rapport_building": 82.0,
            "empathy": 88.0,
            "closing_techniques": 75.0
        }
        
        conversation_analysis = {
            "total_turns": 8,
            "avg_response_time": 1.2,
            "engagement_indicators": ["questions_asked", "active_listening"]
        }
        
        # Record metrics
        success = self.metrics_store.record_session_metrics(
            session_id=session_id,
            user_id=user_id,
            feedback_scores=feedback_scores,
            conversation_analysis=conversation_analysis
        )
        
        self.assertTrue(success)
        
        # Retrieve metrics
        metrics = self.metrics_store.db.get_user_metrics(user_id)
        self.assertEqual(len(metrics), len(feedback_scores))
        
        # Check individual metrics
        metric_types = {m.metric_type for m in metrics}
        self.assertEqual(metric_types, set(feedback_scores.keys()))
    
    def test_skill_assessment_generation(self):
        """Test skill assessment generation"""
        user_id = "assessment_test_user"
        
        # Record metrics over time
        base_date = datetime.now() - timedelta(days=20)
        session_count = 10
        
        for i in range(session_count):
            session_id = f"session_{i:03d}"
            
            # Simulate improving performance over time
            improvement_factor = i * 0.02  # 2% improvement per session
            
            feedback_scores = {
                "clarity": 70 + (improvement_factor * 20),
                "objection_handling": 65 + (improvement_factor * 25),
                "rapport_building": 75 + (improvement_factor * 15),
                "empathy": 80 + (improvement_factor * 10)
            }
            
            # Set timestamp for this session
            session_date = base_date + timedelta(days=i * 2)
            
            # Create and store individual metrics with backdated timestamps
            for skill, score in feedback_scores.items():
                metric = QualityMetric(
                    metric_id=f"metric_{i}_{skill}",
                    session_id=session_id,
                    user_id=user_id,
                    metric_type=skill,
                    metric_category='skill',
                    score=score,
                    score_scale='percentage',
                    measurement_context='session_level',
                    timestamp=session_date,
                    confidence=0.85,
                    source='automated'
                )
                
                self.metrics_store.db.store_metric(metric)
        
        # Generate skill assessment
        assessment = self.metrics_store.generate_skill_assessment(
            user_id=user_id,
            days_back=25
        )
        
        self.assertIsNotNone(assessment)
        self.assertEqual(assessment.user_id, user_id)
        self.assertGreater(assessment.overall_score, 0)
        self.assertTrue(len(assessment.skill_scores) > 0)
        self.assertIsNotNone(assessment.assessment_summary)
        
        # Check that assessment includes expected skills
        expected_skills = {"clarity", "objection_handling", "rapport_building", "empathy"}
        self.assertEqual(set(assessment.skill_scores.keys()), expected_skills)
    
    def test_improvement_recommendations(self):
        """Test improvement recommendation generation"""
        user_id = "recommendation_test_user"
        
        # Record metrics with some low-performing skills
        low_performing_scores = {
            "clarity": 55.0,          # Below threshold
            "objection_handling": 48.0, # Below threshold
            "rapport_building": 85.0,   # Above threshold
            "empathy": 78.0            # Above threshold
        }
        
        # Record multiple sessions with these scores
        for i in range(8):
            session_id = f"rec_session_{i:03d}"
            
            self.metrics_store.record_session_metrics(
                session_id=session_id,
                user_id=user_id,
                feedback_scores=low_performing_scores,
                conversation_analysis={"session_number": i}
            )
        
        # Generate recommendations
        recommendations = self.metrics_store.generate_improvement_recommendations(user_id)
        
        self.assertGreater(len(recommendations), 0)
        
        # Check that recommendations target low-performing skills
        recommended_skills = {rec.skill_area for rec in recommendations}
        expected_low_skills = {"clarity", "objection_handling"}
        
        # Should have recommendations for low-performing skills
        self.assertTrue(recommended_skills.intersection(expected_low_skills))
        
        # Check recommendation properties
        for rec in recommendations:
            self.assertEqual(rec.user_id, user_id)
            self.assertIn(rec.priority, ['high', 'medium', 'low'])
            self.assertTrue(len(rec.action_items) > 0)
            self.assertGreater(rec.target_improvement, 0)
    
    def test_performance_analytics(self):
        """Test performance analytics generation"""
        user_id = "analytics_test_user"
        
        # Create diverse performance data
        skills = ["clarity", "objection_handling", "rapport_building", "empathy"]
        sessions = 15
        
        for i in range(sessions):
            session_id = f"analytics_session_{i:03d}"
            
            feedback_scores = {}
            for skill in skills:
                # Create varied performance with some skills improving, others stable
                if skill == "clarity":
                    score = 60 + (i * 1.5)  # Improving
                elif skill == "objection_handling":
                    score = 70 + (i * 0.5)  # Slowly improving
                elif skill == "rapport_building":
                    score = 80 + ((i % 3) - 1) * 2  # Stable with variation
                else:  # empathy
                    score = 85 - (i * 0.3)  # Slightly declining
                
                feedback_scores[skill] = min(95, max(30, score))  # Clamp to reasonable range
            
            self.metrics_store.record_session_metrics(
                session_id=session_id,
                user_id=user_id,
                feedback_scores=feedback_scores
            )
        
        # Get performance analytics
        analytics = self.metrics_store.get_performance_analytics(
            user_id=user_id,
            days_back=30
        )
        
        self.assertIsNotNone(analytics)
        self.assertIn('skill_analytics', analytics)
        self.assertIn('overall_analytics', analytics)
        
        # Check skill analytics
        skill_analytics = analytics['skill_analytics']
        self.assertEqual(set(skill_analytics.keys()), set(skills))
        
        for skill, data in skill_analytics.items():
            self.assertIn('current_average', data)
            self.assertIn('improvement_trend', data)
            self.assertIn('total_sessions', data)
            self.assertGreater(data['current_average'], 0)
        
        # Check overall analytics
        overall = analytics['overall_analytics']
        self.assertIn('overall_average', overall)
        self.assertIn('total_metrics', overall)
        self.assertIn('improvement_rate', overall)
        self.assertEqual(overall['total_sessions'], sessions)
        self.assertEqual(overall['total_metrics'], sessions * len(skills))
    
    def test_progress_tracking(self):
        """Test detailed progress tracking for specific skills"""
        user_id = "progress_test_user"
        skill = "objection_handling"
        
        # Create progress data over time
        sessions = 12
        base_score = 60
        
        for i in range(sessions):
            session_id = f"progress_session_{i:03d}"
            
            # Simulate gradual improvement with some variation
            progress = i * 2.5  # 2.5 points improvement per session
            variation = (i % 3 - 1) * 1.5  # Some random variation
            score = base_score + progress + variation
            
            # Create metric with backdated timestamp
            session_date = datetime.now() - timedelta(days=(sessions - i) * 2)
            
            metric = QualityMetric(
                metric_id=f"progress_metric_{i}",
                session_id=session_id,
                user_id=user_id,
                metric_type=skill,
                metric_category='skill',
                score=score,
                score_scale='percentage',
                measurement_context='session_level',
                timestamp=session_date,
                confidence=0.85,
                source='automated'
            )
            
            self.metrics_store.db.store_metric(metric)
        
        # Get progress tracking
        progress = self.metrics_store.get_progress_tracking(user_id, skill)
        
        self.assertIsNotNone(progress)
        self.assertEqual(progress['skill'], skill)
        self.assertEqual(progress['total_measurements'], sessions)
        self.assertGreater(progress['improvement'], 0)  # Should show improvement
        self.assertEqual(progress['trend'], 'improving')
        self.assertEqual(len(progress['time_series']), sessions)

class TestStorageIntegration(unittest.TestCase):
    """Test integration between storage services and existing components"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize services with test databases
        self.session_store = SessionLogStore(db_path=os.path.join(self.temp_dir, "test_sessions.db"))
        self.metrics_store = QualityMetricsStore(db_path=os.path.join(self.temp_dir, "test_metrics.db"))
        
        # Mock services for integration testing
        self.chat_service = MockChatService()
        self.feedback_service = MockFeedbackService()
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)
    
    def test_integrated_training_session(self):
        """Test complete integrated training session workflow"""
        user_id = "integration_test_user"
        persona_id = "mary"
        
        # 1. Start training session
        session_id = self.session_store.start_session(
            user_id=user_id,
            persona_id=persona_id,
            session_type="sales_training",
            session_goals=["improve_closing", "handle_objections"]
        )
        
        # 2. Simulate conversation turns with feedback and metrics
        conversation_data = [
            {
                "user_message": "Hi, I'm looking for a CRM solution",
                "bot_response": "Perfect timing! I'm Mary from TechSolutions. What specific challenges are you facing with customer management?",
                "expected_scores": {"clarity": 88, "rapport_building": 85, "questioning": 82}
            },
            {
                "user_message": "It's too expensive for our small business",
                "bot_response": "I understand budget is important. Can you share what you're currently spending on customer management tools?",
                "expected_scores": {"objection_handling": 85, "empathy": 88, "value_exploration": 80}
            },
            {
                "user_message": "We're not ready to make a decision yet",
                "bot_response": "No pressure at all. What would help you feel more confident about moving forward?",
                "expected_scores": {"objection_handling": 90, "empathy": 92, "patience": 88}
            }
        ]
        
        all_scores = {}
        
        for i, turn_data in enumerate(conversation_data):
            # Log conversation turn
            turn_success = self.session_store.log_conversation_turn(
                session_id=session_id,
                user_message=turn_data["user_message"],
                bot_response=turn_data["bot_response"],
                persona_used=persona_id,
                response_time=0.8 + (i * 0.1),
                context_tokens=150 + (i * 20),
                feedback_scores=turn_data["expected_scores"],
                user_emotions=["engaged", "curious"] if i < 2 else ["hesitant", "thoughtful"],
                bot_confidence=0.9 - (i * 0.02)
            )
            
            self.assertTrue(turn_success)
            
            # Aggregate scores for session-level metrics
            for skill, score in turn_data["expected_scores"].items():
                if skill not in all_scores:
                    all_scores[skill] = []
                all_scores[skill].append(score)
        
        # 3. Calculate final session scores
        final_scores = {skill: sum(scores) / len(scores) for skill, scores in all_scores.items()}
        
        # 4. End session with performance metrics
        performance_metrics = {
            "total_turns": len(conversation_data),
            "avg_response_time": 0.9,
            "engagement_level": "high",
            "conversation_flow": "natural"
        }
        
        end_success = self.session_store.end_session(
            session_id=session_id,
            performance_metrics=performance_metrics,
            final_scores=final_scores,
            session_notes="Excellent objection handling practice session"
        )
        
        self.assertTrue(end_success)
        
        # 5. Record quality metrics
        metrics_success = self.metrics_store.record_session_metrics(
            session_id=session_id,
            user_id=user_id,
            feedback_scores=final_scores,
            conversation_analysis=performance_metrics
        )
        
        self.assertTrue(metrics_success)
        
        # 6. Verify data consistency across services
        
        # Check session details
        session_details = self.session_store.get_session_details(session_id)
        self.assertIsNotNone(session_details)
        self.assertEqual(session_details['summary']['total_turns'], len(conversation_data))
        
        # Check metrics storage
        user_metrics = self.metrics_store.db.get_user_metrics(user_id)
        stored_metric_types = {m.metric_type for m in user_metrics}
        expected_metric_types = set(final_scores.keys())
        self.assertEqual(stored_metric_types, expected_metric_types)
        
        # 7. Generate comprehensive analytics
        session_analytics = self.session_store.get_session_analytics(user_id)
        performance_analytics = self.metrics_store.get_performance_analytics(user_id)
        
        self.assertIsNotNone(session_analytics)
        self.assertIsNotNone(performance_analytics)
        
        # Verify analytics consistency
        self.assertEqual(session_analytics['total_sessions'], 1)
        self.assertEqual(session_analytics['completed_sessions'], 1)
        
    def test_multi_session_learning_progression(self):
        """Test tracking learning progression across multiple sessions"""
        user_id = "progression_test_user"
        
        # Simulate 5 training sessions with improving performance
        session_skills = {
            "clarity": 60,
            "objection_handling": 55,
            "empathy": 70,
            "closing_techniques": 50
        }
        
        session_ids = []
        
        for session_num in range(5):
            # Start session
            session_id = self.session_store.start_session(
                user_id=user_id,
                persona_id="jake",
                session_type="advanced_sales_training",
                session_goals=["skill_improvement"]
            )
            session_ids.append(session_id)
            
            # Simulate improvement over sessions
            improved_scores = {}
            for skill, base_score in session_skills.items():
                # Each session improves by 3-5 points
                improvement = session_num * 4
                improved_scores[skill] = min(95, base_score + improvement)
            
            # Log conversation turns
            for turn in range(4):  # 4 turns per session
                self.session_store.log_conversation_turn(
                    session_id=session_id,
                    user_message=f"Session {session_num}, Turn {turn}: User input",
                    bot_response=f"Session {session_num}, Turn {turn}: Bot response",
                    persona_used="jake",
                    response_time=1.0,
                    context_tokens=140,
                    feedback_scores={
                        list(improved_scores.keys())[turn % len(improved_scores)]: 
                        list(improved_scores.values())[turn % len(improved_scores)]
                    }
                )
            
            # End session
            self.session_store.end_session(
                session_id=session_id,
                final_scores=improved_scores
            )
            
            # Record metrics
            self.metrics_store.record_session_metrics(
                session_id=session_id,
                user_id=user_id,
                feedback_scores=improved_scores
            )
        
        # Generate skill assessment after all sessions
        assessment = self.metrics_store.generate_skill_assessment(user_id)
        self.assertIsNotNone(assessment)
        
        # Verify improvement is reflected in assessment
        for skill in session_skills.keys():
            if skill in assessment.skill_scores:
                final_score = assessment.skill_scores[skill]
                initial_score = session_skills[skill]
                self.assertGreater(final_score, initial_score, 
                                 f"Skill {skill} should have improved from {initial_score} to {final_score}")
        
        # Check progress tracking shows improvement
        for skill in session_skills.keys():
            progress = self.metrics_store.get_progress_tracking(user_id, skill)
            if progress:  # Only check if we have progress data
                self.assertGreater(progress.get('improvement', 0), 0,
                                 f"Skill {skill} should show positive improvement trend")
        
        # Verify session analytics show progression
        analytics = self.session_store.get_session_analytics(user_id)
        self.assertEqual(analytics['total_sessions'], 5)
        self.assertEqual(analytics['completed_sessions'], 5)

def run_storage_tests():
    """Run all storage service tests"""
    print("Running Storage Services Integration Tests...")
    print("=" * 50)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_suite.addTest(unittest.makeSuite(TestSessionLogStore))
    test_suite.addTest(unittest.makeSuite(TestQualityMetricsStore))
    test_suite.addTest(unittest.makeSuite(TestStorageIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print("✅ ALL STORAGE TESTS PASSED!")
        print(f"Ran {result.testsRun} tests successfully")
    else:
        print("❌ SOME TESTS FAILED!")
        print(f"Ran {result.testsRun} tests")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"- {test}: {traceback}")
        
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"- {test}: {traceback}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_storage_tests()
    sys.exit(0 if success else 1)