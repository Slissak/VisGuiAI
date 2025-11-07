"""Custom exceptions for the Step Guide Management System.

This module defines a hierarchy of custom exceptions with error codes
and detailed information for API error responses.
"""

from typing import Any


class GuideException(Exception):
    """Base exception for guide system.

    All custom exceptions inherit from this base class, which provides
    structured error information including error codes and details.
    """

    def __init__(self, message: str, code: str, details: dict[str, Any] | None = None):
        """Initialize GuideException.

        Args:
            message: Human-readable error message
            code: Machine-readable error code (e.g., "GUIDE_NOT_FOUND")
            details: Optional dictionary with additional error context
        """
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class GuideNotFoundError(GuideException):
    """Raised when a guide cannot be found by its ID."""

    def __init__(self, guide_id: str):
        """Initialize GuideNotFoundError.

        Args:
            guide_id: The ID of the guide that was not found
        """
        super().__init__(
            message=f"Guide {guide_id} not found",
            code="GUIDE_NOT_FOUND",
            details={"guide_id": guide_id},
        )


class SessionNotFoundError(GuideException):
    """Raised when a session cannot be found by its ID."""

    def __init__(self, session_id: str):
        """Initialize SessionNotFoundError.

        Args:
            session_id: The ID of the session that was not found
        """
        super().__init__(
            message=f"Session {session_id} not found",
            code="SESSION_NOT_FOUND",
            details={"session_id": session_id},
        )


class InvalidStepIdentifierError(GuideException):
    """Raised when a step identifier has an invalid format."""

    def __init__(self, identifier: str, reason: str | None = None):
        """Initialize InvalidStepIdentifierError.

        Args:
            identifier: The invalid step identifier
            reason: Optional explanation of why the identifier is invalid
        """
        message = f"Invalid step identifier: {identifier}"
        if reason:
            message += f" - {reason}"

        super().__init__(
            message=message,
            code="INVALID_STEP_IDENTIFIER",
            details={
                "identifier": identifier,
                "reason": reason
                or "Does not match expected format (e.g., '0', '1a', '2b')",
            },
        )


class LLMGenerationError(GuideException):
    """Raised when LLM generation fails."""

    def __init__(self, provider: str, error: str):
        """Initialize LLMGenerationError.

        Args:
            provider: The LLM provider that failed (e.g., "openai", "anthropic")
            error: Description of the error that occurred
        """
        super().__init__(
            message=f"LLM generation failed with {provider}",
            code="LLM_GENERATION_FAILED",
            details={"provider": provider, "error": error},
        )


class AdaptationError(GuideException):
    """Raised when guide adaptation fails."""

    def __init__(self, reason: str, guide_id: str | None = None):
        """Initialize AdaptationError.

        Args:
            reason: Description of why adaptation failed
            guide_id: Optional ID of the guide being adapted
        """
        details = {"reason": reason}
        if guide_id:
            details["guide_id"] = guide_id

        super().__init__(
            message=f"Guide adaptation failed: {reason}",
            code="ADAPTATION_FAILED",
            details=details,
        )


class ValidationError(GuideException):
    """Raised when input validation fails."""

    def __init__(self, field: str, value: Any, reason: str):
        """Initialize ValidationError.

        Args:
            field: The field that failed validation
            value: The invalid value
            reason: Why the validation failed
        """
        super().__init__(
            message=f"Validation failed for field '{field}': {reason}",
            code="VALIDATION_ERROR",
            details={"field": field, "value": str(value), "reason": reason},
        )
