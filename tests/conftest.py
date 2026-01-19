"""
Pytest configuration and shared fixtures for KALAP V2 tests.
Provides reusable test data and setup utilities.
"""

import pytest
import sys
import os

# Add parent directory to path for kalap_v2 imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kalap_v2.fuzzy_matcher import FuzzyMatcher
from kalap_v2.context_tracker import ContextTracker
from kalap_v2.answer_validator import AnswerValidator
from kalap_v2.question_router import QuestionRouter
from kalap_v2.phase_manager import PhaseManager
from kalap_v2.response_generator import ResponseGenerator


@pytest.fixture
def fuzzy_matcher():
    """Fixture for FuzzyMatcher instance with default config."""
    return FuzzyMatcher(mode="simple")


@pytest.fixture
def context_tracker():
    """Fixture for ContextTracker instance."""
    return ContextTracker()


@pytest.fixture
def answer_validator():
    """Fixture for AnswerValidator instance."""
    return AnswerValidator(mode="simple")


@pytest.fixture
def phase_manager():
    """Fixture for PhaseManager instance."""
    return PhaseManager()


@pytest.fixture
def question_router(phase_manager, context_tracker, answer_validator):
    """Fixture for QuestionRouter instance with dependencies."""
    return QuestionRouter(phase_manager, context_tracker, answer_validator)


@pytest.fixture
def response_generator():
    """Fixture for ResponseGenerator instance."""
    return ResponseGenerator(mode="simple")


@pytest.fixture
def sample_session_id():
    """Fixture for test session ID."""
    return "test-session-123"


@pytest.fixture
def sample_user_inputs():
    """Fixture for common user input test cases."""
    return {
        "short": "Yes",
        "medium": "I want to increase my sales by 20%",
        "detailed": "I've been struggling with closing deals for the past 6 months. My current strategy involves cold calling but I'm only converting 2% of leads. I need a better approach.",
        "emotional": "I'm really frustrated with my current results and worried about missing my quota.",
        "with_typos": "I ned hlp with my salez proces",
        "budget_related": "What's the budget for this solution?"
    }


@pytest.fixture
def sample_intents():
    """Fixture for intent matching test cases."""
    return {
        "budget_inquiry": ["budget", "cost", "price", "investment"],
        "timeline_inquiry": ["when", "timeline", "deadline", "how long"],
        "pain_point": ["problem", "issue", "challenge", "struggle"]
    }
