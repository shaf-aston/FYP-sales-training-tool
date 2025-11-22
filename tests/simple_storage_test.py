"""
Simple Storage Services Test

Basic functionality test for Session Log Store and Quality Metrics Store
to verify core operations work correctly.
"""

import sys
import os
import tempfile
import shutil
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.services.data_services.session_service import SessionLogStore, TrainingSession, ConversationTurn
from src.services.analysis_services.quality_metrics_service import QualityMetricsStore, QualityMetric

def test_storage_services():
    """Test core storage service functionality"""
    
    print("Testing Storage Services...")
    print("=" * 40)
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        print("1. Testing Session Log Store...")
        
        session_store = SessionLogStore(db_path=os.path.join(temp_dir, "sessions.db"))
        
        session_id = session_store.start_session(
            user_id="test_user",
            persona_id="mary",
            session_type="sales_training",
            session_goals=["improve_objection_handling"]
        )
        
        print(f"   ✓ Started session: {session_id}")
        
        turn_success = session_store.log_conversation_turn(
            session_id=session_id,
            user_message="Hello, I'm interested in your product",
            bot_response="Great! I'm Mary. How can I help you today?",
            persona_used="mary",
            response_time=0.8,
            context_tokens=150,
            feedback_scores={"clarity": 85.0, "rapport_building": 78.0}
        )
        
        print(f"   ✓ Logged conversation turn: {turn_success}")
        
        end_success = session_store.end_session(
            session_id=session_id,
            final_scores={"clarity": 85.0, "rapport_building": 78.0}
        )
        
        print(f"   ✓ Ended session: {end_success}")
        
        details = session_store.get_session_details(session_id)
        session_found = details is not None
        conversation_logged = len(details.get('conversation', [])) > 0 if details else False
        
        print(f"   ✓ Retrieved session details: {session_found}")
        print(f"   ✓ Conversation logged: {conversation_logged}")
        
        print("\n2. Testing Quality Metrics Store...")
        
        metrics_store = QualityMetricsStore(db_path=os.path.join(temp_dir, "metrics.db"))
        
        metrics_success = metrics_store.record_session_metrics(
            session_id=session_id,
            user_id="test_user",
            feedback_scores={
                "clarity": 85.0,
                "objection_handling": 78.0,
                "rapport_building": 82.0
            }
        )
        
        print(f"   ✓ Recorded session metrics: {metrics_success}")
        
        user_metrics = metrics_store.db.get_user_metrics("test_user")
        metrics_found = len(user_metrics) > 0
        
        print(f"   ✓ Retrieved user metrics: {metrics_found} ({len(user_metrics)} metrics)")
        
        print("\n3. Testing Integration...")
        
        session_id_2 = session_store.start_session(
            user_id="test_user",
            persona_id="jake",
            session_type="objection_training"
        )
        
        for i in range(3):
            session_store.log_conversation_turn(
                session_id=session_id_2,
                user_message=f"Turn {i+1} message",
                bot_response=f"Turn {i+1} response",
                persona_used="jake",
                response_time=1.0 + i * 0.1,
                context_tokens=140 + i * 10,
                feedback_scores={"empathy": 80 + i, "clarity": 75 + i}
            )
        
        session_store.end_session(
            session_id=session_id_2,
            final_scores={"empathy": 82.0, "clarity": 77.0}
        )
        
        metrics_store.record_session_metrics(
            session_id=session_id_2,
            user_id="test_user",
            feedback_scores={"empathy": 82.0, "clarity": 77.0}
        )
        
        history = session_store.get_user_history("test_user")
        history_found = len(history) >= 2
        
        print(f"   ✓ User has session history: {history_found} ({len(history)} sessions)")
        
        try:
            analytics = metrics_store.get_performance_analytics("test_user")
            analytics_generated = len(analytics) > 0
        except Exception as e:
            print(f"   ⚠ Analytics generation had issues: {e}")
            analytics_generated = False
        
        print(f"   ✓ Performance analytics generated: {analytics_generated}")
        
        print("\n4. Testing Data Consistency...")
        
        all_metrics = metrics_store.db.get_user_metrics("test_user")
        unique_sessions_in_metrics = len(set(m.session_id for m in all_metrics))
        
        user_sessions = session_store.get_user_history("test_user")
        session_count = len(user_sessions)
        
        consistency_check = unique_sessions_in_metrics == session_count
        
        print(f"   ✓ Data consistency: {consistency_check}")
        print(f"     Sessions in log store: {session_count}")
        print(f"     Unique sessions in metrics: {unique_sessions_in_metrics}")
        
        print("\n" + "=" * 40)
        
        all_tests = [
            session_id is not None,
            turn_success,
            end_success,
            session_found,
            conversation_logged,
            metrics_success,
            metrics_found,
            history_found,
            analytics_generated,
            consistency_check
        ]
        
        passed_tests = sum(all_tests)
        total_tests = len(all_tests)
        
        if passed_tests == total_tests:
            print("🎉 ALL STORAGE TESTS PASSED!")
            print(f"Successfully completed {passed_tests}/{total_tests} tests")
            return True
        else:
            print("⚠️  SOME TESTS HAD ISSUES")
            print(f"Completed {passed_tests}/{total_tests} tests successfully")
            return False
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False
        
    finally:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

if __name__ == "__main__":
    success = test_storage_services()
    print("\n" + "=" * 40)
    if success:
        print("✅ Storage services are functional!")
    else:
        print("⚠️  Storage services need attention")
    
    sys.exit(0 if success else 1)