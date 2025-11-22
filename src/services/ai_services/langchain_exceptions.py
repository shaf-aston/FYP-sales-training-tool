"""Custom exceptions for LangChain services."""


class LangChainServiceError(Exception):
    """Base exception for LangChain service errors."""
    pass


class PersonaNotFoundError(LangChainServiceError):
    """Raised when a requested persona is not found."""
    pass


class ModelInitializationError(LangChainServiceError):
    """Raised when model initialization fails."""
    pass


class ConversationError(LangChainServiceError):
    """Raised when conversation processing fails."""
    pass
