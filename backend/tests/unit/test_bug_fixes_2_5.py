"""
Unit tests for Task 2.5 Bug Fixes (BUG-004, BUG-005, BUG-006)

Tests the Pydantic validation fixes without requiring a running backend.
"""

import pytest
from pydantic import ValidationError
from pathlib import Path

# Import the request model with the bug fixes
from src.api.instruction_guides import InstructionGuideRequest


class TestBug004EmptyInstructionValidation:
    """Test BUG-004: Empty instruction should be rejected"""

    def test_empty_string_rejected(self):
        """Empty string should raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            InstructionGuideRequest(instruction="")

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("at least 5 characters" in str(err).lower() for err in errors)

    def test_whitespace_only_rejected(self):
        """Whitespace-only string should raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            InstructionGuideRequest(instruction="   ")

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_too_short_rejected(self):
        """String shorter than 5 chars should raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            InstructionGuideRequest(instruction="hi")

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("at least 5 characters" in str(err).lower() for err in errors)

    def test_exactly_5_chars_accepted(self):
        """String with exactly 5 chars should be accepted"""
        request = InstructionGuideRequest(instruction="hello")
        assert request.instruction == "hello"

    def test_valid_instruction_accepted(self):
        """Valid instruction should be accepted"""
        request = InstructionGuideRequest(
            instruction="How to make a cup of tea"
        )
        assert request.instruction == "How to make a cup of tea"
        assert request.difficulty.value == "beginner"  # default


class TestBug005LongInstructionValidation:
    """Test BUG-005: Very long instruction should be rejected"""

    def test_exactly_1000_chars_accepted(self):
        """String with exactly 1000 chars should be accepted"""
        instruction = "a" * 1000
        request = InstructionGuideRequest(instruction=instruction)
        assert len(request.instruction) == 1000

    def test_1001_chars_rejected(self):
        """String with 1001 chars should raise ValidationError"""
        instruction = "a" * 1001
        with pytest.raises(ValidationError) as exc_info:
            InstructionGuideRequest(instruction=instruction)

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("at most 1000 characters" in str(err).lower() for err in errors)

    def test_1500_chars_rejected(self):
        """String with 1500 chars should raise ValidationError (original bug case)"""
        instruction = "a" * 1500
        with pytest.raises(ValidationError) as exc_info:
            InstructionGuideRequest(instruction=instruction)

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("at most 1000 characters" in str(err).lower() for err in errors)

    def test_realistic_long_instruction(self):
        """Test with realistic long instruction text"""
        instruction = (
            "I need to create a comprehensive guide for deploying a microservices "
            "architecture to AWS EKS with the following requirements: " + "x" * 900
        )
        with pytest.raises(ValidationError) as exc_info:
            InstructionGuideRequest(instruction=instruction)

        errors = exc_info.value.errors()
        assert len(errors) > 0


class TestBug006SQLColumnName:
    """Test BUG-006: SQL column name fix (test file verification)"""

    def test_e2e_test_file_uses_correct_column_name(self):
        """Verify the E2E test file uses difficulty_level not difficulty"""
        e2e_test_path = Path(__file__).parent.parent.parent / "test_e2e_guide_generation.py"

        if not e2e_test_path.exists():
            pytest.skip("E2E test file not found")

        content = e2e_test_path.read_text()

        # Check that line 392 contains difficulty_level
        lines = content.split('\n')
        if len(lines) < 392:
            pytest.skip("E2E test file doesn't have 392 lines")

        # Find the SQL query around line 392
        for i in range(385, 400):  # Check lines around 392
            if i < len(lines) and "SELECT guide_id" in lines[i]:
                query_section = '\n'.join(lines[i:i+5])
                assert "difficulty_level" in query_section, \
                    f"SQL query should use 'difficulty_level' not 'difficulty' around line {i+1}"
                assert "difficulty," not in query_section, \
                    f"SQL query should not use 'difficulty,' (with comma) around line {i+1}"
                return

        pytest.skip("Could not find SQL query in expected location")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
