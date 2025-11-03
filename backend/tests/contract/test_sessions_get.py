"""Contract tests for GET /api/v1/sessions/{session_id} endpoint."""

import pytest
from httpx import AsyncClient


class TestSessionsGetContract:
    """Test GET /api/v1/sessions/{session_id} endpoint contract."""

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_get_session_success_contract(self, client: AsyncClient):
        """Test successful session retrieval returns 200 with detailed schema."""
        # Create session first
        guide_response = await client.post("/api/v1/guides/generate", json={
            "user_query": "How to configure Git",
            "user_id": "test_user_001"
        })
        guide_id = guide_response.json()["guide_id"]

        session_response = await client.post("/api/v1/sessions", json={
            "guide_id": guide_id,
            "user_id": "test_user_001"
        })
        session_id = session_response.json()["session_id"]

        response = await client.get(f"/api/v1/sessions/{session_id}")

        assert response.status_code == 200

        # Validate SessionDetailResponse schema
        data = response.json()
        assert "session" in data
        assert "guide" in data
        assert "current_step" in data
        assert "progress" in data

        # Validate nested objects
        session = data["session"]
        assert "session_id" in session
        assert "status" in session

        guide = data["guide"]
        assert "guide_id" in guide
        assert "steps" in guide

        progress = data["progress"]
        assert "completion_percentage" in progress
        assert "total_steps" in progress

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_get_session_not_found_404(self, client: AsyncClient):
        """Test non-existent session returns 404."""
        response = await client.get("/api/v1/sessions/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data