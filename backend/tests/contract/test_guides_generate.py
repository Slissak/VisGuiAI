"""Contract tests for POST /api/v1/guides/generate endpoint.

These tests MUST FAIL initially (TDD requirement).
They validate the API contract matches the OpenAPI specification.
"""

import pytest
from httpx import AsyncClient


class TestGuidesGenerateContract:
    """Test POST /api/v1/guides/generate endpoint contract."""

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_generate_guide_success_contract(self, client: AsyncClient):
        """Test successful guide generation returns 201 with correct schema."""
        request_data = {
            "user_query": "How to set up a Python virtual environment",
            "user_id": "test_user_001",
            "difficulty_preference": "beginner",
            "format_preference": "detailed"
        }

        response = await client.post("/api/v1/guides/generate", json=request_data)

        # Must return 201 Created
        assert response.status_code == 201

        # Validate response schema matches OpenAPI spec
        data = response.json()
        assert "guide_id" in data
        assert "guide" in data
        assert "generation_time_seconds" in data
        assert "llm_provider" in data

        # Validate guide structure
        guide = data["guide"]
        assert "guide_id" in guide
        assert "title" in guide
        assert "description" in guide
        assert "total_steps" in guide
        assert "steps" in guide
        assert "estimated_duration_minutes" in guide
        assert "difficulty_level" in guide
        assert "category" in guide

        # Validate steps array
        assert isinstance(guide["steps"], list)
        assert len(guide["steps"]) > 0

        # Validate first step structure
        step = guide["steps"][0]
        assert "step_id" in step
        assert "step_index" in step
        assert "title" in step
        assert "description" in step
        assert "completion_criteria" in step
        assert "assistance_hints" in step
        assert "estimated_duration_minutes" in step
        assert "requires_desktop_monitoring" in step
        assert "visual_markers" in step
        assert "completed" in step
        assert "needs_assistance" in step

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_generate_guide_invalid_request_400(self, client: AsyncClient):
        """Test invalid request returns 400 with error schema."""
        request_data = {
            "user_query": "",  # Invalid: empty query
            "user_id": "test_user_001"
        }

        response = await client.post("/api/v1/guides/generate", json=request_data)

        # Must return 400 Bad Request
        assert response.status_code == 400

        # Validate error response schema
        data = response.json()
        assert "error" in data
        assert "message" in data
        assert "timestamp" in data

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_generate_guide_missing_fields_400(self, client: AsyncClient):
        """Test missing required fields returns 400."""
        request_data = {
            "user_query": "How to install Python"
            # Missing required user_id
        }

        response = await client.post("/api/v1/guides/generate", json=request_data)

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "user_id" in data["message"].lower()

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_generate_guide_invalid_difficulty_400(self, client: AsyncClient):
        """Test invalid difficulty preference returns 400."""
        request_data = {
            "user_query": "How to set up Docker",
            "user_id": "test_user_001",
            "difficulty_preference": "invalid_level"  # Not in enum
        }

        response = await client.post("/api/v1/guides/generate", json=request_data)

        assert response.status_code == 400

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_generate_guide_rate_limit_429(self, client: AsyncClient):
        """Test rate limiting returns 429."""
        request_data = {
            "user_query": "How to set up a database",
            "user_id": "test_user_001"
        }

        # Make multiple requests rapidly to trigger rate limiting
        # This will fail initially until rate limiting is implemented
        responses = []
        for _ in range(10):
            response = await client.post("/api/v1/guides/generate", json=request_data)
            responses.append(response)

        # At least one should be rate limited
        rate_limited = any(r.status_code == 429 for r in responses)
        assert rate_limited, "Rate limiting should trigger for rapid requests"

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_generate_guide_response_time(self, client: AsyncClient):
        """Test guide generation completes within 5 seconds."""
        import time

        request_data = {
            "user_query": "How to create a REST API",
            "user_id": "test_user_001"
        }

        start_time = time.time()
        response = await client.post("/api/v1/guides/generate", json=request_data)
        end_time = time.time()

        # Should complete within 5 seconds (per requirements)
        generation_time = end_time - start_time
        assert generation_time < 5.0, f"Generation took {generation_time}s, should be <5s"

        if response.status_code == 201:
            # Verify generation_time_seconds field is accurate
            data = response.json()
            reported_time = data["generation_time_seconds"]
            assert abs(reported_time - generation_time) < 1.0