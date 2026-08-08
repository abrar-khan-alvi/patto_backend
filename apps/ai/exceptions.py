class AIServiceError(Exception):
    """Base exception for AI service-layer failures."""


class AIConfigurationError(AIServiceError):
    """Raised when required provider configuration is missing."""


class AIProviderError(AIServiceError):
    """Raised when the provider call fails before returning usable output."""


class AIRefusalError(AIServiceError):
    """Raised when the provider refuses to produce the requested analysis."""
