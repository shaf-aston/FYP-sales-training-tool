"""
Context Window Manager
Manages conversation context within token limits for optimal LLM performance.
Selects most relevant context and handles token counting.
"""
import tiktoken
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC

logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    """Individual context item with metadata"""
    content: str
    timestamp: datetime
    role: str
    importance: float = 1.0
    tokens: int = 0
    session_id: str = ""
    message_type: str = "message" 


class ContextWindowManager:
    """Manages conversation context within token limits"""
    
    def __init__(self, max_tokens: int = 4000, model_name: str = "gpt-3.5-turbo"):
        """
        Initialize context manager
        
        Args:
            max_tokens: Maximum tokens for context window
            model_name: Model name for token counting
        """
        self.max_tokens = max_tokens
        self.model_name = model_name
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        
        self.context_items: List[ContextItem] = []
        self.reserved_tokens = 500
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.warning(f"Error counting tokens: {e}")
            return len(text) // 4
    
    def add_context(self, content: str, role: str = "user", 
                   importance: float = 1.0, message_type: str = "message",
                   session_id: str = "") -> None:
        """Add new context item"""
        token_count = self.count_tokens(content)
        
        context_item = ContextItem(
            content=content,
            timestamp=datetime.now(UTC),
            role=role,
            importance=importance,
            tokens=token_count,
            session_id=session_id,
            message_type=message_type
        )
        
        self.context_items.append(context_item)
        logger.debug(f"Added context: {token_count} tokens, role: {role}, type: {message_type}")
    
    def add_conversation_turn(self, user_message: str, assistant_response: str,
                            session_id: str = "") -> None:
        """Add a complete conversation turn"""
        self.add_context(user_message, role="user", importance=0.8, 
                        message_type="message", session_id=session_id)
        self.add_context(assistant_response, role="assistant", importance=0.7,
                        message_type="message", session_id=session_id)
    
    def add_system_instruction(self, instruction: str, importance: float = 1.0) -> None:
        """Add system instruction with high importance"""
        self.add_context(instruction, role="system", importance=importance,
                        message_type="instruction")
    
    def add_persona_context(self, persona_description: str, session_id: str = "") -> None:
        """Add persona context"""
        self.add_context(persona_description, role="system", importance=0.9,
                        message_type="persona", session_id=session_id)
    
    def get_total_tokens(self) -> int:
        """Get total token count of all context items"""
        return sum(item.tokens for item in self.context_items)
    
    def _calculate_relevance_score(self, item: ContextItem, current_time: datetime) -> float:
        """Calculate relevance score for context item"""
        score = item.importance
        
        time_diff = current_time - item.timestamp
        if time_diff < timedelta(hours=1):
            recency_bonus = 1.0 - (time_diff.total_seconds() / 3600) * 0.3
            score *= recency_bonus
        else:
            hours_old = time_diff.total_seconds() / 3600
            age_penalty = max(0.5, 1.0 - (hours_old - 1) * 0.1)
            score *= age_penalty
        
        type_bonuses = {
            "instruction": 1.0,
            "persona": 0.9,
            "feedback": 0.8,
            "message": 1.0
        }
        score *= type_bonuses.get(item.message_type, 1.0)
        
        role_bonuses = {
            "system": 1.0,
            "user": 0.9,
            "assistant": 0.8
        }
        score *= role_bonuses.get(item.role, 0.8)
        
        return score
    
    def _select_context_items(self, available_tokens: int) -> List[ContextItem]:
        """Select context items that fit within token limit"""
        current_time = datetime.now()
        
        scored_items = []
        for item in self.context_items:
            relevance = self._calculate_relevance_score(item, current_time)
            scored_items.append((item, relevance))
        
        scored_items.sort(key=lambda x: x[1], reverse=True)
        
        selected_items = []
        used_tokens = 0
        
        for item, score in scored_items:
            if item.message_type in ["instruction", "persona"]:
                if used_tokens + item.tokens <= available_tokens:
                    selected_items.append(item)
                    used_tokens += item.tokens
        
        for item, score in scored_items:
            if item.message_type not in ["instruction", "persona"]:
                if used_tokens + item.tokens <= available_tokens:
                    selected_items.append(item)
                    used_tokens += item.tokens
                else:
                    break
        
        logger.debug(f"Selected {len(selected_items)} items using {used_tokens} tokens")
        return selected_items
    
    def build_context_window(self, include_recent_messages: int = 5) -> str:
        """Build context window within token limits"""
        available_tokens = self.max_tokens - self.reserved_tokens
        
        if not self.context_items:
            return ""
        
        recent_messages = []
        message_items = [item for item in self.context_items if item.message_type == "message"]
        if message_items and include_recent_messages > 0:
            recent_messages = message_items[-include_recent_messages * 2:]
        
        selected_items = self._select_context_items(available_tokens)
        
        for msg in recent_messages:
            if msg not in selected_items:
                selected_items.append(msg)
        
        seen_items = set()
        unique_items = []
        for item in selected_items:
            item_id = f"{item.content[:50]}_{item.timestamp}"
            if item_id not in seen_items:
                seen_items.add(item_id)
                unique_items.append(item)
        
        unique_items.sort(key=lambda x: x.timestamp)
        
        context_parts = []
        
        system_items = [item for item in unique_items if item.role == "system"]
        conversation_items = [item for item in unique_items if item.role in ["user", "assistant"]]
        
        for item in system_items:
            if item.message_type == "instruction":
                context_parts.append(f"SYSTEM: {item.content}")
            elif item.message_type == "persona":
                context_parts.append(f"PERSONA: {item.content}")
            else:
                context_parts.append(f"SYSTEM: {item.content}")
        
        if conversation_items:
            context_parts.append("\nCONVERSATION HISTORY:")
            for item in conversation_items:
                role_label = item.role.upper()
                context_parts.append(f"{role_label}: {item.content}")
        
        final_context = "\n".join(context_parts)
        
        final_tokens = self.count_tokens(final_context)
        if final_tokens > available_tokens:
            logger.warning(f"Context exceeds limit: {final_tokens} > {available_tokens}")
            final_context = self._truncate_context(final_context, available_tokens)
        
        logger.info(f"Built context window: {self.count_tokens(final_context)} tokens")
        return final_context
    
    def _truncate_context(self, context: str, max_tokens: int) -> str:
        """Truncate context to fit within token limit"""
        tokens = self.encoding.encode(context)
        
        if len(tokens) <= max_tokens:
            return context
        
        truncated_tokens = tokens[:max_tokens]
        truncated_context = self.encoding.decode(truncated_tokens)
        
        logger.warning(f"Truncated context from {len(tokens)} to {len(truncated_tokens)} tokens")
        return truncated_context
    
    def clear_old_context(self, hours: int = 24) -> int:
        """Clear context older than specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        old_count = len(self.context_items)
        self.context_items = [
            item for item in self.context_items
            if (item.timestamp > cutoff_time or 
                item.message_type in ["instruction", "persona"] or
                item.importance > 0.9)
        ]
        
        removed_count = old_count - len(self.context_items)
        if removed_count > 0:
            logger.info(f"Cleared {removed_count} old context items")
        
        return removed_count
    
    def clear_session_context(self, session_id: str) -> int:
        """Clear context for specific session"""
        old_count = len(self.context_items)
        self.context_items = [
            item for item in self.context_items
            if item.session_id != session_id
        ]
        
        removed_count = old_count - len(self.context_items)
        if removed_count > 0:
            logger.info(f"Cleared {removed_count} context items for session {session_id}")
        
        return removed_count
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get summary of current context"""
        total_tokens = self.get_total_tokens()
        
        by_type = {}
        by_role = {}
        
        for item in self.context_items:
            by_type[item.message_type] = by_type.get(item.message_type, 0) + 1
            by_role[item.role] = by_role.get(item.role, 0) + 1
        
        return {
            "total_items": len(self.context_items),
            "total_tokens": total_tokens,
            "available_tokens": self.max_tokens - self.reserved_tokens - total_tokens,
            "items_by_type": by_type,
            "items_by_role": by_role,
            "oldest_item": min(self.context_items, key=lambda x: x.timestamp).timestamp if self.context_items else None,
            "newest_item": max(self.context_items, key=lambda x: x.timestamp).timestamp if self.context_items else None
        }
    
    def optimize_context(self) -> Dict[str, Any]:
        """Optimize context by removing low-relevance items"""
        if self.get_total_tokens() <= self.max_tokens - self.reserved_tokens:
            return {"optimized": False, "reason": "within_limits"}
        
        current_time = datetime.now()
        
        scored_items = []
        for item in self.context_items:
            relevance = self._calculate_relevance_score(item, current_time)
            scored_items.append((item, relevance))
        
        scored_items.sort(key=lambda x: x[1], reverse=True)
        
        target_tokens = self.max_tokens - self.reserved_tokens
        optimized_items = []
        used_tokens = 0
        
        for item, score in scored_items:
            if used_tokens + item.tokens <= target_tokens:
                optimized_items.append(item)
                used_tokens += item.tokens
        
        removed_count = len(self.context_items) - len(optimized_items)
        self.context_items = optimized_items
        
        logger.info(f"Optimized context: removed {removed_count} items, {used_tokens} tokens remaining")
        
        return {
            "optimized": True,
            "removed_items": removed_count,
            "final_tokens": used_tokens,
            "final_items": len(optimized_items)
        }


_context_manager = None

def get_context_manager() -> ContextWindowManager:
    """Get singleton ContextWindowManager instance"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextWindowManager()
    return _context_manager