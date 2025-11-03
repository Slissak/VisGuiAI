"""Validation utility functions for the Step Guide Management System.

This module provides validation helpers for common data types and formats
used throughout the application.
"""

import re
from typing import Optional
from uuid import UUID

from ..exceptions import InvalidStepIdentifierError, ValidationError


def validate_step_identifier(identifier: str) -> bool:
    """Validate step identifier format.

    Step identifiers must match the pattern: digit(s) followed by optional lowercase letter.
    Examples of valid identifiers: "0", "1", "1a", "1b", "2", "10", "10a"

    Args:
        identifier: The step identifier to validate

    Returns:
        True if validation passes

    Raises:
        InvalidStepIdentifierError: If the identifier format is invalid
    """
    if not identifier:
        raise InvalidStepIdentifierError(
            identifier="",
            reason="Step identifier cannot be empty"
        )

    if not isinstance(identifier, str):
        raise InvalidStepIdentifierError(
            identifier=str(identifier),
            reason="Step identifier must be a string"
        )

    # Pattern: one or more digits followed by optional single lowercase letter
    pattern = r'^\d+[a-z]?$'

    if not re.match(pattern, identifier):
        raise InvalidStepIdentifierError(
            identifier=identifier,
            reason="Must be digits optionally followed by a lowercase letter (e.g., '0', '1a', '2b')"
        )

    return True


def validate_uuid(value: str, field_name: str = "value") -> bool:
    """Validate UUID format.

    Args:
        value: The string to validate as UUID
        field_name: Name of the field being validated (for error messages)

    Returns:
        True if validation passes

    Raises:
        ValidationError: If the value is not a valid UUID
    """
    if not value:
        raise ValidationError(
            field=field_name,
            value=value,
            reason="UUID cannot be empty"
        )

    if not isinstance(value, str):
        raise ValidationError(
            field=field_name,
            value=value,
            reason="UUID must be a string"
        )

    try:
        UUID(value)
        return True
    except ValueError as e:
        raise ValidationError(
            field=field_name,
            value=value,
            reason=f"Invalid UUID format: {str(e)}"
        )


def validate_non_empty_string(
    value: Optional[str],
    field_name: str,
    min_length: int = 1,
    max_length: Optional[int] = None
) -> bool:
    """Validate that a string is non-empty and within length constraints.

    Args:
        value: The string to validate
        field_name: Name of the field being validated
        min_length: Minimum required length (default: 1)
        max_length: Maximum allowed length (optional)

    Returns:
        True if validation passes

    Raises:
        ValidationError: If the string is invalid
    """
    if value is None:
        raise ValidationError(
            field=field_name,
            value=value,
            reason="Value cannot be None"
        )

    if not isinstance(value, str):
        raise ValidationError(
            field=field_name,
            value=value,
            reason="Value must be a string"
        )

    if len(value) < min_length:
        raise ValidationError(
            field=field_name,
            value=value,
            reason=f"Value must be at least {min_length} character(s) long"
        )

    if max_length is not None and len(value) > max_length:
        raise ValidationError(
            field=field_name,
            value=value,
            reason=f"Value must be no more than {max_length} character(s) long"
        )

    return True


def validate_positive_integer(
    value: int,
    field_name: str,
    min_value: int = 1,
    max_value: Optional[int] = None
) -> bool:
    """Validate that a value is a positive integer within constraints.

    Args:
        value: The integer to validate
        field_name: Name of the field being validated
        min_value: Minimum allowed value (default: 1)
        max_value: Maximum allowed value (optional)

    Returns:
        True if validation passes

    Raises:
        ValidationError: If the integer is invalid
    """
    if not isinstance(value, int):
        raise ValidationError(
            field=field_name,
            value=value,
            reason="Value must be an integer"
        )

    if value < min_value:
        raise ValidationError(
            field=field_name,
            value=value,
            reason=f"Value must be at least {min_value}"
        )

    if max_value is not None and value > max_value:
        raise ValidationError(
            field=field_name,
            value=value,
            reason=f"Value must be no more than {max_value}"
        )

    return True
