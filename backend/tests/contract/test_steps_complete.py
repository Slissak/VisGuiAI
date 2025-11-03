"""Contract tests for POST /api/v1/sessions/{session_id}/steps/{step_index}/complete endpoint."""

import pytest
from httpx import AsyncClient


class TestStepsCompleteContract:
    """Test step completion endpoint contract."""

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_complete_step_manual_success_contract(self, client: AsyncClient):
        """Test manual step completion returns 200 with correct schema."""
        # Setup: create guide and session
        guide_response = await client.post("/api/v1/guides/generate", json={
            "user_query": "How to create a file",
            "user_id": "test_user_001"
        })
        guide_id = guide_response.json()["guide_id"]

        session_response = await client.post("/api/v1/sessions", json={
            "guide_id": guide_id,
            "user_id": "test_user_001",
            "completion_method": "manual_checkbox"
        })
        session_id = session_response.json()["session_id"]

        # Complete first step
        request_data = {
            "completion_method": "manual_checkbox",
            "user_feedback": "Completed successfully"
        }

        response = await client.post(
            f"/api/v1/sessions/{session_id}/steps/0/complete",
            json=request_data
        )

        assert response.status_code == 200

        # Validate StepCompletionResponse schema
        data = response.json()
        assert "completed" in data
        assert "next_step_index" in data
        assert "progress" in data
        assert "completion_event" in data

        assert data["completed"] is True
        assert isinstance(data["next_step_index"], (int, type(None)))

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_complete_step_desktop_monitoring_contract(self, client: AsyncClient):
        """Test desktop monitoring completion with validation score."""
        # Setup session
        guide_response = await client.post("/api/v1/guides/generate", json={
            "user_query": "How to open a terminal",
            "user_id": "test_user_001"
        })
        guide_id = guide_response.json()["guide_id"]

        session_response = await client.post("/api/v1/sessions", json={
            "guide_id": guide_id,
            "user_id": "test_user_001",
            "completion_method": "desktop_monitoring"
        })
        session_id = session_response.json()["session_id"]

        request_data = {
            "completion_method": "desktop_monitoring",
            "validation_score": 0.95,
            "validation_data": {
                "screenshot_url": "test_screenshot.png",
                "detected_elements": ["terminal_window_opened"]
            }
        }

        response = await client.post(
            f"/api/v1/sessions/{session_id}/steps/0/complete",
            json=request_data
        )

        assert response.status_code == 200

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_complete_step_out_of_sequence_409(self, client: AsyncClient):
        """Test completing step out of sequence returns 409."""
        # Setup session
        guide_response = await client.post("/api/v1/guides/generate", json={
            "user_query": "Multi-step process",
            "user_id": "test_user_001"
        })
        guide_id = guide_response.json()["guide_id"]

        session_response = await client.post("/api/v1/sessions", json={
            "guide_id": guide_id,
            "user_id": "test_user_001"
        })
        session_id = session_response.json()["session_id"]

        # Try to complete step 2 before step 0
        request_data = {"completion_method": "manual_checkbox"}
        response = await client.post(
            f"/api/v1/sessions/{session_id}/steps/2/complete",
            json=request_data
        )

        assert response.status_code == 409