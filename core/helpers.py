"""History traversal helpers. Centralised patterns for cleaner code."""

from typing import Optional
from .constants_enums import MessageRole


class HistoryHelper:
    """Utility methods for safely traversing conversation history."""

    @staticmethod
    def get_recent_user_messages(
        history: Optional[list[dict]],
        count: int = 2
    ) -> list[str]:
        """Extract N most recent user message texts (lowercased).

        Args:
            history: Conversation history
            count: Number of recent messages to return

        Returns:
            List of user message texts, lowercased, most recent last
        """
        if not history:
            return []

        user_msgs = [
            m["content"].lower()
            for m in history
            if m.get("role") == MessageRole.USER
        ]
        return user_msgs[-count:] if count > 0 else []

    @staticmethod
    def get_last_bot_message(history: Optional[list[dict]]) -> str:
        """Get most recent bot response text.

        Args:
            history: Conversation history

        Returns:
            Most recent bot message, or empty string if none found
        """
        if not history:
            return ""

        for msg in reversed(history):
            if msg.get("role") == MessageRole.ASSISTANT:
                return msg.get("content", "")

        return ""

    @staticmethod
    def count_recent_questions(
        history: Optional[list[dict]],
        window: int = 4
    ) -> int:
        """Count question marks in recent bot messages.

        Args:
            history: Conversation history
            window: Number of recent messages to scan

        Returns:
            Number of messages containing '?' in the window
        """
        if not history:
            return 0

        recent_bot = [
            m["content"]
            for m in history[-window:]
            if m.get("role") == MessageRole.ASSISTANT
        ]
        return sum(1 for msg in recent_bot if "?" in msg)

    @staticmethod
    def get_conversation_window(
        history: Optional[list[dict]],
        max_turns: int = 10
    ) -> list[dict]:
        """Get last N turns from history.

        Args:
            history: Conversation history
            max_turns: Maximum number of recent turns to return

        Returns:
            Recent conversation turns, or empty list if history is None
        """
        if not history:
            return []
        return history[-max_turns:] if max_turns > 0 else []

    @staticmethod
    def get_recent_bot_messages(
        history: Optional[list[dict]],
        count: int = 4
    ) -> list[str]:
        """Extract N most recent bot message texts.

        Args:
            history: Conversation history
            count: Number of recent messages to return

        Returns:
            List of bot message texts, most recent last
        """
        if not history:
            return []

        bot_msgs = [
            m["content"]
            for m in history
            if m.get("role") == MessageRole.ASSISTANT
        ]
        return bot_msgs[-count:] if count > 0 else []

    @staticmethod
    def combine_messages(
        user_messages: list[str],
        separator: str = " "
    ) -> str:
        """Combine a list of messages into a single searchable string.

        Args:
            user_messages: List of message texts
            separator: String to join messages with

        Returns:
            Combined message text
        """
        return separator.join(user_messages).strip()
