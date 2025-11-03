#!/usr/bin/env python3
"""Test script to demonstrate error handling system.

This script tests the custom exceptions and validation helpers
without requiring the full server to be running.
"""

import sys
import os

# Add backend src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.exceptions import (
    GuideException,
    GuideNotFoundError,
    SessionNotFoundError,
    InvalidStepIdentifierError,
    LLMGenerationError,
    AdaptationError,
    ValidationError
)
from src.utils.validation import (
    validate_step_identifier,
    validate_uuid,
    validate_non_empty_string,
    validate_positive_integer
)


def test_exceptions():
    """Test custom exceptions."""
    print("=" * 70)
    print("TESTING CUSTOM EXCEPTIONS")
    print("=" * 70)

    # Test GuideNotFoundError
    print("\n1. Testing GuideNotFoundError:")
    try:
        raise GuideNotFoundError("123e4567-e89b-12d3-a456-426614174000")
    except GuideException as e:
        print(f"   Code: {e.code}")
        print(f"   Message: {e.message}")
        print(f"   Details: {e.details}")

    # Test SessionNotFoundError
    print("\n2. Testing SessionNotFoundError:")
    try:
        raise SessionNotFoundError("789e4567-e89b-12d3-a456-426614174999")
    except GuideException as e:
        print(f"   Code: {e.code}")
        print(f"   Message: {e.message}")
        print(f"   Details: {e.details}")

    # Test InvalidStepIdentifierError
    print("\n3. Testing InvalidStepIdentifierError:")
    try:
        raise InvalidStepIdentifierError("invalid_step", "Must be numeric")
    except GuideException as e:
        print(f"   Code: {e.code}")
        print(f"   Message: {e.message}")
        print(f"   Details: {e.details}")

    # Test LLMGenerationError
    print("\n4. Testing LLMGenerationError:")
    try:
        raise LLMGenerationError("openai", "Rate limit exceeded")
    except GuideException as e:
        print(f"   Code: {e.code}")
        print(f"   Message: {e.message}")
        print(f"   Details: {e.details}")

    # Test AdaptationError
    print("\n5. Testing AdaptationError:")
    try:
        raise AdaptationError("Step structure incompatible", "guide-123")
    except GuideException as e:
        print(f"   Code: {e.code}")
        print(f"   Message: {e.message}")
        print(f"   Details: {e.details}")

    # Test ValidationError
    print("\n6. Testing ValidationError:")
    try:
        raise ValidationError("user_id", "abc", "Must be a valid UUID")
    except GuideException as e:
        print(f"   Code: {e.code}")
        print(f"   Message: {e.message}")
        print(f"   Details: {e.details}")


def test_validators():
    """Test validation helpers."""
    print("\n" + "=" * 70)
    print("TESTING VALIDATION HELPERS")
    print("=" * 70)

    # Test validate_step_identifier - valid cases
    print("\n1. Testing validate_step_identifier() - Valid cases:")
    valid_identifiers = ["0", "1", "2", "10", "1a", "1b", "2a", "10z"]
    for identifier in valid_identifiers:
        try:
            result = validate_step_identifier(identifier)
            print(f"   ✓ '{identifier}' - Valid: {result}")
        except Exception as e:
            print(f"   ✗ '{identifier}' - Error: {e.message}")

    # Test validate_step_identifier - invalid cases
    print("\n2. Testing validate_step_identifier() - Invalid cases:")
    invalid_identifiers = ["", "abc", "1AB", "1-a", "step1", "a1"]
    for identifier in invalid_identifiers:
        try:
            result = validate_step_identifier(identifier)
            print(f"   ✗ '{identifier}' - Should have failed but didn't!")
        except InvalidStepIdentifierError as e:
            print(f"   ✓ '{identifier}' - Correctly rejected")
            print(f"      Error: {e.message}")

    # Test validate_uuid - valid cases
    print("\n3. Testing validate_uuid() - Valid cases:")
    valid_uuids = [
        "123e4567-e89b-12d3-a456-426614174000",
        "550e8400-e29b-41d4-a716-446655440000"
    ]
    for uuid_str in valid_uuids:
        try:
            result = validate_uuid(uuid_str, "test_id")
            print(f"   ✓ '{uuid_str}' - Valid: {result}")
        except Exception as e:
            print(f"   ✗ '{uuid_str}' - Error: {e.message}")

    # Test validate_uuid - invalid cases
    print("\n4. Testing validate_uuid() - Invalid cases:")
    invalid_uuids = ["", "not-a-uuid", "123", "abc-def-ghi"]
    for uuid_str in invalid_uuids:
        try:
            result = validate_uuid(uuid_str, "test_id")
            print(f"   ✗ '{uuid_str}' - Should have failed but didn't!")
        except ValidationError as e:
            print(f"   ✓ '{uuid_str}' - Correctly rejected")
            print(f"      Error: {e.message}")

    # Test validate_non_empty_string
    print("\n5. Testing validate_non_empty_string():")
    try:
        validate_non_empty_string("Hello World", "title")
        print("   ✓ 'Hello World' - Valid")
    except Exception as e:
        print(f"   ✗ Error: {e.message}")

    try:
        validate_non_empty_string("", "title")
        print("   ✗ Empty string should have failed!")
    except ValidationError as e:
        print(f"   ✓ Empty string correctly rejected: {e.message}")

    # Test validate_positive_integer
    print("\n6. Testing validate_positive_integer():")
    try:
        validate_positive_integer(5, "count")
        print("   ✓ 5 - Valid")
    except Exception as e:
        print(f"   ✗ Error: {e.message}")

    try:
        validate_positive_integer(-1, "count")
        print("   ✗ Negative number should have failed!")
    except ValidationError as e:
        print(f"   ✓ Negative number correctly rejected: {e.message}")


def simulate_api_error_response():
    """Simulate what an API error response would look like."""
    from datetime import datetime

    print("\n" + "=" * 70)
    print("SIMULATED API ERROR RESPONSES")
    print("=" * 70)

    # Simulate SessionNotFoundError response
    print("\n1. Session Not Found Error (404-style):")
    try:
        raise SessionNotFoundError("550e8400-e29b-41d4-a716-446655440000")
    except GuideException as e:
        response = {
            "error": e.code,
            "message": e.message,
            "details": e.details,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        import json
        print(json.dumps(response, indent=2))

    # Simulate InvalidStepIdentifierError response
    print("\n2. Invalid Step Identifier Error:")
    try:
        raise InvalidStepIdentifierError("step-abc")
    except GuideException as e:
        response = {
            "error": e.code,
            "message": e.message,
            "details": e.details,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        import json
        print(json.dumps(response, indent=2))

    # Simulate LLMGenerationError response
    print("\n3. LLM Generation Error:")
    try:
        raise LLMGenerationError("openai", "Rate limit exceeded: 429 Too Many Requests")
    except GuideException as e:
        response = {
            "error": e.code,
            "message": e.message,
            "details": e.details,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        import json
        print(json.dumps(response, indent=2))


if __name__ == "__main__":
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "ERROR HANDLING SYSTEM TEST" + " " * 27 + "║")
    print("╚" + "=" * 68 + "╝")

    test_exceptions()
    test_validators()
    simulate_api_error_response()

    print("\n" + "=" * 70)
    print("✓ ALL TESTS COMPLETED SUCCESSFULLY")
    print("=" * 70 + "\n")
