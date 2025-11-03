"""Contract tests for POST /api/v1/sessions endpoint.

These tests MUST FAIL initially (TDD requirement).
They validate the API contract matches the OpenAPI specification.
"""

import pytest
from httpx import AsyncClient


class TestSessionsCreateContract:
    """Test POST /api/v1/sessions endpoint contract."""

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_create_session_success_contract(self, client: AsyncClient):
        """Test successful session creation returns 201 with correct schema."""
        # First need a guide_id - this will fail until guide generation works
        guide_response = await client.post("/api/v1/guides/generate", json={
            "user_query": "How to set up Python virtual environment",
            "user_id": "test_user_001"
        })
        assert guide_response.status_code == 201
        guide_id = guide_response.json()["guide_id"]

        request_data = {
            "guide_id": guide_id,
            "user_id": "test_user_001",
            "completion_method": "manual_checkbox"
        }

        response = await client.post("/api/v1/sessions", json=request_data)

        # Must return 201 Created
        assert response.status_code == 201

        # Validate response schema matches OpenAPI spec
        data = response.json()
        assert "session_id" in data
        assert "guide_id" in data
        assert "user_id" in data
        assert "status" in data
        assert "current_step_index" in data
        assert "completion_method" in data
        assert "created_at" in data
        assert "updated_at" in data

        # Validate field values
        assert data["guide_id"] == guide_id
        assert data["user_id"] == "test_user_001"
        assert data["status"] == "active"
        assert data["current_step_index"] == 0
        assert data["completion_method"] == "manual_checkbox"

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_create_session_missing_guide_id_400(self, client: AsyncClient):
        """Test missing guide_id returns 400."""
        request_data = {
            "user_id": "test_user_001",
            "completion_method": "manual_checkbox"
        }

        response = await client.post("/api/v1/sessions", json=request_data)

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "guide_id" in data["message"].lower()

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_create_session_invalid_guide_id_404(self, client: AsyncClient):
        """Test invalid guide_id returns 404."""
        request_data = {
            "guide_id": "00000000-0000-0000-0000-000000000000",
            "user_id": "test_user_001",
            "completion_method": "manual_checkbox"
        }

        response = await client.post("/api/v1/sessions", json=request_data)

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "guide" in data["message"].lower()

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_create_session_invalid_completion_method_400(self, client: AsyncClient):
        """Test invalid completion_method returns 400."""
        request_data = {
            "guide_id": "123e4567-e89b-12d3-a456-426614174000",
            "user_id": "test_user_001",
            "completion_method": "invalid_method"
        }

        response = await client.post("/api/v1/sessions", json=request_data)

        assert response.status_code == 400

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_create_session_default_completion_method(self, client: AsyncClient):
        """Test default completion_method is hybrid."""
        # Create a guide first
        guide_response = await client.post("/api/v1/guides/generate", json={
            "user_query": "How to install Docker",
            "user_id": "test_user_001"
        })
        guide_id = guide_response.json()["guide_id"]

        request_data = {
            "guide_id": guide_id,
            "user_id": "test_user_001"
            # completion_method omitted - should default to hybrid
        }

        response = await client.post("/api/v1/sessions", json=request_data)

        assert response.status_code == 201
        data = response.json()
        assert data["completion_method"] == "hybrid"