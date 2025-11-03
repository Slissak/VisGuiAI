"""Integration test for complete guide generation and execution flow.

This test MUST FAIL initially (TDD requirement).
It validates the end-to-end user journey from guide request to completion.
"""

import pytest
from httpx import AsyncClient


class TestCompleteFlow:
    """Test complete user journey integration."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_guide_flow_integration(self, client: AsyncClient):
        """Test complete flow: generate guide → create session → complete steps → finish."""
        # Step 1: Generate a guide
        guide_request = {
            "user_query": "How to create a Python virtual environment",
            "user_id": "integration_test_user",
            "difficulty_preference": "beginner"
        }

        guide_response = await client.post("/api/v1/guides/generate", json=guide_request)
        assert guide_response.status_code == 201, "Guide generation should succeed"

        guide_data = guide_response.json()
        guide_id = guide_data["guide_id"]
        guide = guide_data["guide"]

        # Validate guide has multiple steps
        assert len(guide["steps"]) >= 2, "Guide should have multiple steps"

        # Step 2: Create a session
        session_request = {
            "guide_id": guide_id,
            "user_id": "integration_test_user",
            "completion_method": "manual_checkbox"
        }

        session_response = await client.post("/api/v1/sessions", json=session_request)
        assert session_response.status_code == 201, "Session creation should succeed"

        session_data = session_response.json()
        session_id = session_data["session_id"]

        # Step 3: Get current step (should be step 0)
        current_step_response = await client.get(f"/api/v1/sessions/{session_id}/current-step")
        assert current_step_response.status_code == 200, "Should get current step"

        current_step_data = current_step_response.json()
        assert current_step_data["step"]["step_index"] == 0, "Should start at step 0"
        assert current_step_data["is_current"] is True, "Should be marked as current"

        # Step 4: Check initial progress
        progress_response = await client.get(f"/api/v1/sessions/{session_id}/progress")
        assert progress_response.status_code == 200, "Should get progress"

        progress_data = progress_response.json()
        assert progress_data["completion_percentage"] == 0.0, "Should start at 0% complete"
        assert progress_data["completed_steps"] == 0, "Should have 0 completed steps"
        assert progress_data["current_step_index"] == 0, "Should be on step 0"

        # Step 5: Complete first step
        complete_request = {
            "completion_method": "manual_checkbox",
            "user_feedback": "Successfully completed first step"
        }

        complete_response = await client.post(
            f"/api/v1/sessions/{session_id}/steps/0/complete",
            json=complete_request
        )
        assert complete_response.status_code == 200, "Step completion should succeed"

        complete_data = complete_response.json()
        assert complete_data["completed"] is True, "Step should be marked completed"
        assert complete_data["next_step_index"] == 1, "Should advance to step 1"

        # Step 6: Verify progress updated
        progress_response = await client.get(f"/api/v1/sessions/{session_id}/progress")
        progress_data = progress_response.json()

        expected_percentage = (1 / len(guide["steps"])) * 100
        assert progress_data["completion_percentage"] == expected_percentage, "Progress should update"
        assert progress_data["completed_steps"] == 1, "Should have 1 completed step"
        assert progress_data["current_step_index"] == 1, "Should be on step 1"

        # Step 7: Complete remaining steps
        for step_index in range(1, len(guide["steps"])):
            complete_response = await client.post(
                f"/api/v1/sessions/{session_id}/steps/{step_index}/complete",
                json={"completion_method": "manual_checkbox"}
            )
            assert complete_response.status_code == 200, f"Step {step_index} completion should succeed"

        # Step 8: Verify session completion
        final_progress_response = await client.get(f"/api/v1/sessions/{session_id}/progress")
        final_progress_data = final_progress_response.json()

        assert final_progress_data["completion_percentage"] == 100.0, "Should be 100% complete"
        assert final_progress_data["completed_steps"] == len(guide["steps"]), "All steps should be completed"

        # Step 9: Verify session status
        session_detail_response = await client.get(f"/api/v1/sessions/{session_id}")
        session_detail_data = session_detail_response.json()

        assert session_detail_data["session"]["status"] == "completed", "Session should be completed"
        assert session_detail_data["session"]["completed_at"] is not None, "Should have completion timestamp"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_session_pause_resume_integration(self, client: AsyncClient):
        """Test session pause and resume functionality."""
        # Create guide and session
        guide_response = await client.post("/api/v1/guides/generate", json={
            "user_query": "How to configure Git",
            "user_id": "pause_test_user"
        })
        guide_id = guide_response.json()["guide_id"]

        session_response = await client.post("/api/v1/sessions", json={
            "guide_id": guide_id,
            "user_id": "pause_test_user"
        })
        session_id = session_response.json()["session_id"]

        # Complete first step
        await client.post(
            f"/api/v1/sessions/{session_id}/steps/0/complete",
            json={"completion_method": "manual_checkbox"}
        )

        # Pause session
        pause_response = await client.put(f"/api/v1/sessions/{session_id}", json={
            "status": "paused",
            "user_feedback": "Taking a break"
        })
        assert pause_response.status_code == 200, "Should be able to pause session"
        assert pause_response.json()["status"] == "paused", "Status should be paused"

        # Resume session
        resume_response = await client.put(f"/api/v1/sessions/{session_id}", json={
            "status": "active"
        })
        assert resume_response.status_code == 200, "Should be able to resume session"
        assert resume_response.json()["status"] == "active", "Status should be active"

        # Verify progress preserved
        progress_response = await client.get(f"/api/v1/sessions/{session_id}/progress")
        progress_data = progress_response.json()
        assert progress_data["completed_steps"] == 1, "Progress should be preserved"