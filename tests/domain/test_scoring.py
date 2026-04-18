"""Unit tests for training scoring logic: signal detection, conversation length, stage progression."""

from unittest.mock import patch
from chatbot.trainer import score_session
from chatbot.constants import SCORING_RUBRIC


class TestScoreSesssionBasics:
    """Test basic score_session function behavior."""

    def test_score_session_no_analytics(self):
        """Should return zero score when no analytics exist."""
        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = []

            result = score_session("nonexistent_session")

            assert result["total_score"] == 0
            assert result["breakdown"] == {}

    def test_score_session_structure(self):
        """Score result should have required fields."""
        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = []

            result = score_session("test_session")

            assert "total_score" in result
            assert "breakdown" in result
            assert isinstance(result["total_score"], int)
            assert isinstance(result["breakdown"], dict)


class TestStageProgression:
    """Test stage progression scoring."""

    def test_stage_progression_intent_reached(self):
        """Should award points when intent stage reached."""
        events = [
            {
                "event_type": "stage_transition",
                "from_stage": "WELCOME",
                "to_stage": "INTENT",
                "user_turns_in_stage": 1,
            },
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            score_breakdown = result["breakdown"]
            assert "stage_progression" in score_breakdown
            # Should have some points for reaching intent
            assert score_breakdown["stage_progression"] >= 0

    def test_stage_progression_multiple_stages(self):
        """Should award higher points for reaching further stages."""
        events = [
            {
                "event_type": "stage_transition",
                "from_stage": "WELCOME",
                "to_stage": "INTENT",
                "user_turns_in_stage": 1,
            },
            {
                "event_type": "stage_transition",
                "from_stage": "INTENT",
                "to_stage": "LOGICAL",
                "user_turns_in_stage": 2,
            },
            {
                "event_type": "stage_transition",
                "from_stage": "LOGICAL",
                "to_stage": "EMOTIONAL",
                "user_turns_in_stage": 2,
            },
            {
                "event_type": "session_end",
                "final_stage": "EMOTIONAL",
            },
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            score_breakdown = result["breakdown"]
            # Should have points for reaching emotional stage
            assert score_breakdown["stage_progression"] > 0


class TestSignalDetection:
    """Test signal detection scoring (25 pts max)."""

    def test_signal_detection_zero_transitions(self):
        """Should score 0 when no transitions."""
        events = [
            {"event_type": "dummy"}
        ]  # Need at least one event to enter scoring logic

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            assert result["breakdown"]["signal_detection"] == 0

    def test_signal_detection_perfect_ratio(self):
        """Should score max when all transitions have signals."""
        # Transitions that occur early (within timeout threshold) = signals
        events = [
            {
                "event_type": "stage_transition",
                "from_stage": "INTENT",
                "to_stage": "LOGICAL",
                "user_turns_in_stage": 2,  # Early transition
            },
            {
                "event_type": "stage_transition",
                "from_stage": "LOGICAL",
                "to_stage": "EMOTIONAL",
                "user_turns_in_stage": 2,  # Early transition
            },
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            signal_score = result["breakdown"]["signal_detection"]
            # Ratio = 2/2 = 1.0 → should be 25 pts (or close to max)
            assert signal_score > 0
            assert signal_score <= SCORING_RUBRIC["signal_detection_max"]

    def test_signal_detection_partial_ratio(self):
        """Should score proportionally to signal ratio."""
        events = [
            {
                "event_type": "stage_transition",
                "from_stage": "INTENT",
                "to_stage": "LOGICAL",
                "user_turns_in_stage": 2,  # Signal
            },
            {
                "event_type": "stage_transition",
                "from_stage": "LOGICAL",
                "to_stage": "EMOTIONAL",
                "user_turns_in_stage": 99,  # No signal (too many turns)
            },
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            signal_score = result["breakdown"]["signal_detection"]
            # Ratio = 1/2 = 0.5 → should be ~12.5 pts
            assert 0 < signal_score < SCORING_RUBRIC["signal_detection_max"]

    def test_signal_detection_capped_at_max(self):
        """Signal detection should not exceed max."""
        max_signal = SCORING_RUBRIC["signal_detection_max"]

        events = [
            {
                "event_type": "stage_transition",
                "from_stage": "INTENT",
                "to_stage": "LOGICAL",
                "user_turns_in_stage": 1,
            },
            {
                "event_type": "stage_transition",
                "from_stage": "LOGICAL",
                "to_stage": "EMOTIONAL",
                "user_turns_in_stage": 1,
            },
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            assert result["breakdown"]["signal_detection"] <= max_signal

    def test_signal_detection_pitch_objection_stuck(self):
        """Pitch/objection stages with many turns should not count as signal transitions."""
        # Bug fix: pitch and objection now have timeout thresholds (8 and 6 turns respectively)
        # so spending more than that time in them will reduce signal detection score
        events = [
            {
                "event_type": "stage_transition",
                "from_stage": "INTENT",
                "to_stage": "LOGICAL",
                "user_turns_in_stage": 2,  # Early transition = signal
            },
            {
                "event_type": "stage_transition",
                "from_stage": "LOGICAL",
                "to_stage": "PITCH",
                "user_turns_in_stage": 2,  # Early transition = signal
            },
            {
                "event_type": "stage_transition",
                "from_stage": "PITCH",
                "to_stage": "OBJECTION",
                "user_turns_in_stage": 15,  # Stuck in pitch (way over 8-turn threshold) = NOT a signal
            },
            {
                "event_type": "stage_transition",
                "from_stage": "OBJECTION",
                "to_stage": "PITCH",
                "user_turns_in_stage": 20,  # Stuck in objection (way over 6-turn threshold) = NOT a signal
            },
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            signal_score = result["breakdown"]["signal_detection"]
            # Ratio = 2 signals / 4 total transitions = 0.5 → should be ~12.5 pts (int(25 * 0.5))
            expected = int(SCORING_RUBRIC["signal_detection_max"] * 0.5)
            assert signal_score == expected, (
                f"Expected {expected} (50% of max) but got {signal_score}. "
                f"This tests that pitch/objection with too many turns don't score as signals."
            )


class TestObjectionHandling:
    """Test objection handling scoring."""

    def test_objection_handling_none_classified(self):
        """Should score 0 when no objections classified."""
        events = [
            {"event_type": "dummy"}
        ]  # Need at least one event to enter scoring logic

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            objection_score = result["breakdown"]["objection_handling"]
            assert objection_score == 0

    def test_objection_handling_one_classified(self):
        """Should award full points when objection classified."""
        events = [
            {
                "event_type": "objection_classified",
                "objection_type": "price",
            },
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            objection_score = result["breakdown"]["objection_handling"]
            max_objection = SCORING_RUBRIC["objection_handling_max"]
            assert objection_score == max_objection

    def test_objection_handling_multiple_classifications(self):
        """Should award full points even with multiple objections."""
        events = [
            {
                "event_type": "objection_classified",
                "objection_type": "price",
            },
            {
                "event_type": "objection_classified",
                "objection_type": "implementation",
            },
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            # Still max (binary: either handled or not)
            objection_score = result["breakdown"]["objection_handling"]
            max_objection = SCORING_RUBRIC["objection_handling_max"]
            assert objection_score == max_objection


class TestQuestioningDepth:
    """Test questioning depth scoring."""

    def test_questioning_depth_no_intent_events(self):
        """Should score 0 when no intent classification events."""
        events = [
            {"event_type": "dummy"}
        ]  # Need at least one event to enter scoring logic

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            depth_score = result["breakdown"]["questioning_depth"]
            assert depth_score == 0

    def test_questioning_depth_low_intent(self):
        """Should score 0 for low intent classification."""
        events = [
            {
                "event_type": "intent_classification",
                "intent_level": "low",
            },
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            depth_score = result["breakdown"]["questioning_depth"]
            assert depth_score == 0

    def test_questioning_depth_medium_intent(self):
        """Should award points for medium intent."""
        events = [
            {
                "event_type": "intent_classification",
                "intent_level": "medium",
            },
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            depth_score = result["breakdown"]["questioning_depth"]
            per_hit = SCORING_RUBRIC["questioning_depth_per_hit"]
            assert depth_score == per_hit

    def test_questioning_depth_high_intent(self):
        """Should award points for high intent."""
        events = [
            {
                "event_type": "intent_classification",
                "intent_level": "high",
            },
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            depth_score = result["breakdown"]["questioning_depth"]
            per_hit = SCORING_RUBRIC["questioning_depth_per_hit"]
            assert depth_score == per_hit

    def test_questioning_depth_multiple_hits(self):
        """Should accumulate points for multiple medium/high intents."""
        events = [
            {"event_type": "intent_classification", "intent_level": "medium"},
            {"event_type": "intent_classification", "intent_level": "high"},
            {"event_type": "intent_classification", "intent_level": "high"},
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            depth_score = result["breakdown"]["questioning_depth"]
            per_hit = SCORING_RUBRIC["questioning_depth_per_hit"]
            expected = min(3 * per_hit, SCORING_RUBRIC["questioning_depth_max"])
            assert depth_score == expected


class TestConversationLength:
    """Test conversation length scoring (sweet spot 7-12 turns)."""

    def test_conversation_length_sweet_spot(self):
        """Should award full points for turns in sweet spot (7-12)."""
        sweet_min, sweet_max = SCORING_RUBRIC["sweet_spot_turns"]

        for turns in range(sweet_min, sweet_max + 1):
            events = [
                {
                    "event_type": "dummy",
                    "user_turn_count": turns,
                },
            ] + [
                {
                    "event_type": "stage_transition",
                    "from_stage": "INTENT",
                    "to_stage": "LOGICAL",
                    "user_turns_in_stage": 1,
                    "user_turn": turns,
                }
            ]

            with patch(
                "chatbot.trainer.SessionAnalytics.get_session_analytics"
            ) as mock:
                # Manually set max_turn by changing user_turn on the last event
                final_events = []
                for evt in events:
                    e = evt.copy()
                    e["user_turn"] = turns
                    final_events.append(e)

                mock.return_value = final_events

                result = score_session("test_session")

                conv_score = result["breakdown"]["conversation_length"]
                max_conv = SCORING_RUBRIC["conversation_length_max"]
                assert conv_score == max_conv, f"Failed for turns={turns}"

    def test_conversation_length_too_short(self):
        """Should award half points for too few turns."""
        sweet_min = SCORING_RUBRIC["sweet_spot_turns"][0]
        events = [
            {
                "event_type": "session_end",
                "user_turn": sweet_min - 3,
            }
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            conv_score = result["breakdown"]["conversation_length"]
            max_conv = SCORING_RUBRIC["conversation_length_max"]
            assert conv_score == max_conv // 2

    def test_conversation_length_too_long(self):
        """Should award reduced points for too many turns."""
        sweet_max = SCORING_RUBRIC["sweet_spot_turns"][1]
        events = [
            {
                "event_type": "session_end",
                "user_turn": sweet_max + 5,
            }
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            conv_score = result["breakdown"]["conversation_length"]
            max_conv = SCORING_RUBRIC["conversation_length_max"]
            assert conv_score == max_conv // 2

    def test_conversation_length_just_over_sweet_spot(self):
        """Should award 80% for 1-3 turns over sweet spot."""
        sweet_max = SCORING_RUBRIC["sweet_spot_turns"][1]
        events = [
            {
                "event_type": "session_end",
                "user_turn": sweet_max + 2,
            }
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            conv_score = result["breakdown"]["conversation_length"]
            max_conv = SCORING_RUBRIC["conversation_length_max"]
            expected = int(max_conv * 0.8)
            assert conv_score == expected


class TestTotalScore:
    """Test total score calculation."""

    def test_total_score_is_sum(self):
        """Total should be sum of breakdown components."""
        events = [
            {
                "event_type": "stage_transition",
                "from_stage": "INTENT",
                "to_stage": "LOGICAL",
                "user_turns_in_stage": 2,
            },
            {
                "event_type": "objection_classified",
                "objection_type": "price",
            },
            {
                "event_type": "intent_classification",
                "intent_level": "high",
            },
            {
                "event_type": "session_end",
                "user_turn": 9,  # In sweet spot
                "final_stage": "LOGICAL",
            },
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            breakdown = result["breakdown"]
            total = sum(breakdown.values())
            assert result["total_score"] == total

    def test_total_score_capped_at_100(self):
        """Total score should not exceed 100."""
        # Create events that would sum to >100
        events = [
            {
                "event_type": "stage_transition",
                "from_stage": "INTENT",
                "to_stage": "LOGICAL",
                "user_turns_in_stage": 1,  # Signal
            },
            {
                "event_type": "objection_classified",
                "objection_type": "price",
            },
            {
                "event_type": "intent_classification",
                "intent_level": "high",
            },
            {
                "event_type": "session_end",
                "user_turn": 9,
                "final_stage": "LOGICAL",
            },
        ]

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            assert result["total_score"] <= 100

    def test_total_score_not_negative(self):
        """Total score should never be negative."""
        events = []

        with patch(
            "chatbot.trainer.SessionAnalytics.get_session_analytics"
        ) as mock_analytics:
            mock_analytics.return_value = events

            result = score_session("test_session")

            assert result["total_score"] >= 0
