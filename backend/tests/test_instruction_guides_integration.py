"""Integration tests for instruction guides functionality."""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from uuid import uuid4
from unittest.mock import patch, AsyncMock
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.services.llm_service import LLMService
from src.core.database import get_db


class TestInstructionGuidesIntegration:
    """Integration tests for instruction-based guide generation and progression."""

    @pytest.fixture
    def test_user_id(self):
        """Fixture providing a test user ID."""
        return "test_user_123"

    @pytest.fixture
    def mock_llm_response(self):
        """Fixture providing a mock LLM response with sectioned structure."""
        return {
            "guide": {
                "title": "How to set up a development environment",
                "description": "A comprehensive guide for setting up a development environment",
                "category": "development",
                "difficulty_level": "beginner",
                "estimated_duration_minutes": 45,
                "sections": [
                    {
                        "section_id": "setup",
                        "section_title": "Setup",
                        "section_description": "Initial preparation steps",
                        "section_order": 0,
                        "steps": [
                            {
                                "step_index": 0,
                                "title": "Install Node.js",
                                "description": "Download and install Node.js from the official website",
                                "completion_criteria": "Node.js version 18+ is installed and accessible via command line",
                                "assistance_hints": ["Use the official Node.js website", "Verify installation with 'node --version'"],
                                "estimated_duration_minutes": 10,
                                "requires_desktop_monitoring": False,
                                "visual_markers": [],
                                "prerequisites": [],
                                "completed": False,
                                "needs_assistance": False
                            },
                            {
                                "step_index": 1,
                                "title": "Install Code Editor",
                                "description": "Install VS Code or your preferred code editor",
                                "completion_criteria": "Code editor is installed and can open files",
                                "assistance_hints": ["VS Code is recommended for beginners", "Configure basic extensions"],
                                "estimated_duration_minutes": 15,
                                "requires_desktop_monitoring": True,
                                "visual_markers": ["download_button", "install_wizard"],
                                "prerequisites": [],
                                "completed": False,
                                "needs_assistance": False
                            }
                        ]
                    },
                    {
                        "section_id": "configuration",
                        "section_title": "Configuration",
                        "section_description": "Settings and adjustments",
                        "section_order": 1,
                        "steps": [
                            {
                                "step_index": 2,
                                "title": "Configure Git",
                                "description": "Set up Git with your name and email",
                                "completion_criteria": "Git is configured with user name and email",
                                "assistance_hints": ["Use git config --global commands", "Check configuration with git config --list"],
                                "estimated_duration_minutes": 5,
                                "requires_desktop_monitoring": False,
                                "visual_markers": [],
                                "prerequisites": ["Complete Node.js installation"],
                                "completed": False,
                                "needs_assistance": False
                            }
                        ]
                    }
                ]
            }
        }

    @pytest.mark.asyncio
    async def test_generate_instruction_guide_workflow(
        self,
        test_user_id: str,
        mock_llm_response: dict,
        test_db
    ):
        """Test the complete instruction guide generation workflow."""

        # Mock the LLM service to return our test data
        with patch('src.services.llm_service.LLMService.generate_guide') as mock_llm:
            mock_llm.return_value = (mock_llm_response, "mock_provider", 1.5)

            # Override authentication dependency
            from src.auth.middleware import get_current_user
            async def mock_get_current_user():
                return test_user_id

            # Override database dependency to use test database
            async def get_test_db():
                yield test_db

            app.dependency_overrides[get_current_user] = mock_get_current_user
            app.dependency_overrides[get_db] = get_test_db

            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    # Test guide generation
                    response = await client.post(
                        "/api/v1/instruction-guides/generate",
                        json={
                            "instruction": "set up a development environment",
                            "difficulty": "beginner",
                            "format_preference": "detailed"
                        }
                    )

                    assert response.status_code == 200
                    data = response.json()

                    # Verify response structure
                    assert "session_id" in data
                    assert "guide_id" in data
                    assert "guide_title" in data
                    assert "first_step" in data

                    session_id = data["session_id"]

                    # Verify first step contains only current step info
                    first_step = data["first_step"]
                    assert first_step["status"] == "active"
                    assert "current_step" in first_step
                    assert first_step["current_step"]["step_index"] == 0
                    assert "Install Node.js" in first_step["current_step"]["title"]

                    # Test getting current step
                    response = await client.get(f"/api/v1/instruction-guides/{session_id}/current-step")
                    assert response.status_code == 200

                    current_step_data = response.json()
                    assert current_step_data["current_step"]["step_index"] == 0
                    assert current_step_data["progress"]["completed_steps"] == 0
                    assert current_step_data["progress"]["total_steps"] == 3
            finally:
                # Clean up dependency override
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_step_completion_progression(
        self,
        test_user_id: str,
        mock_llm_response: dict,
        test_db: AsyncSession
    ):
        """Test step completion and progression through multiple steps."""

        with patch('src.services.llm_service.LLMService.generate_guide') as mock_llm:
            mock_llm.return_value = (mock_llm_response, "mock_provider", 1.5)

            from src.auth.middleware import get_current_user
            async def mock_get_current_user():
                return test_user_id

            async def get_test_db():
                yield test_db

            app.dependency_overrides[get_current_user] = mock_get_current_user
            app.dependency_overrides[get_db] = get_test_db

            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    # Generate guide and get session
                    response = await client.post(
                        "/api/v1/instruction-guides/generate",
                        json={
                            "instruction": "set up a development environment",
                            "difficulty": "beginner"
                        }
                    )

                    assert response.status_code == 200
                    session_id = response.json()["session_id"]

                    # Complete first step
                    response = await client.post(
                        f"/api/v1/instruction-guides/{session_id}/complete-step",
                        json={
                            "completion_notes": "Successfully installed Node.js version 18.17.0",
                            "time_taken_minutes": 8
                        }
                    )

                    assert response.status_code == 200
                    next_step_data = response.json()

                    # Verify progression to second step
                    assert next_step_data["current_step"]["step_index"] == 1
                    assert "Install Code Editor" in next_step_data["current_step"]["title"]
                    assert next_step_data["progress"]["completed_steps"] == 1

                    # Complete second step
                    response = await client.post(
                        f"/api/v1/instruction-guides/{session_id}/complete-step",
                        json={
                            "completion_notes": "Installed VS Code with extensions",
                            "time_taken_minutes": 12
                        }
                    )

                    assert response.status_code == 200
                    next_step_data = response.json()

                    # Verify progression to third step (different section)
                    assert next_step_data["current_step"]["step_index"] == 2
                    assert "Configure Git" in next_step_data["current_step"]["title"]
                    assert next_step_data["progress"]["completed_steps"] == 2
                    assert next_step_data["current_section"]["section_title"] == "Configuration"
            finally:
                app.dependency_overrides.clear()
    @pytest.mark.asyncio
    async def test_step_navigation_back_and_forth(
        self,
        test_user_id: str,
        mock_llm_response: dict,
        test_db: AsyncSession
    ):
        """Test going back to previous steps and forward again."""

        with patch('src.services.llm_service.LLMService.generate_guide') as mock_llm:
            mock_llm.return_value = (mock_llm_response, "mock_provider", 1.5)

            from src.auth.middleware import get_current_user
            async def mock_get_current_user():
                return test_user_id

            async def get_test_db():
                yield test_db

            app.dependency_overrides[get_current_user] = mock_get_current_user
            app.dependency_overrides[get_db] = get_test_db

            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    # Generate guide and get session
                    response = await client.post(
                        "/api/v1/instruction-guides/generate",
                        json={"instruction": "set up a development environment"}
                    )

                    assert response.status_code == 200
                    session_id = response.json()["session_id"]

                    # Complete first step to move to second
                    await client.post(
                        f"/api/v1/instruction-guides/{session_id}/complete-step",
                        json={"completion_notes": "First step completed"}
                    )

                    # Verify we're on step 1 (second step)
                    response = await client.get(f"/api/v1/instruction-guides/{session_id}/current-step")
                    assert response.json()["current_step"]["step_index"] == 1

                    # Go back to previous step
                    response = await client.post(f"/api/v1/instruction-guides/{session_id}/previous-step")
                    assert response.status_code == 200

                    previous_step_data = response.json()
                    assert previous_step_data["current_step"]["step_index"] == 0
                    assert previous_step_data["navigation"]["can_go_back"] == False
            finally:
                app.dependency_overrides.clear()
    @pytest.mark.asyncio
    async def test_section_overview_access(
        self,
        test_user_id: str,
        mock_llm_response: dict,
        test_db: AsyncSession
    ):
        """Test accessing section overview without revealing full step details."""

        with patch('src.services.llm_service.LLMService.generate_guide') as mock_llm:
            mock_llm.return_value = (mock_llm_response, "mock_provider", 1.5)

            from src.auth.middleware import get_current_user
            async def mock_get_current_user():
                return test_user_id

            async def get_test_db():
                yield test_db

            app.dependency_overrides[get_current_user] = mock_get_current_user
            app.dependency_overrides[get_db] = get_test_db

            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    # Generate guide and get session
                    response = await client.post(
                        "/api/v1/instruction-guides/generate",
                        json={"instruction": "set up a development environment"}
                    )

                    assert response.status_code == 200
                    session_id = response.json()["session_id"]

                    # Get overview of setup section
                    response = await client.get(
                        f"/api/v1/instruction-guides/{session_id}/sections/setup/overview"
                    )

                    assert response.status_code == 200
                    overview_data = response.json()

                    # Verify overview contains titles but not full descriptions
                    assert overview_data["section_title"] == "Setup"
                    assert overview_data["section_id"] == "setup"
                    assert len(overview_data["step_overview"]) == 2

                    # Verify step overview has titles but not full descriptions
                    step_overview = overview_data["step_overview"]
                    assert step_overview[0]["title"] == "Install Node.js"
                    assert step_overview[0]["current"] == True  # First step is current
                    assert step_overview[1]["locked"] == True   # Second step is locked

                    # Verify no full descriptions are exposed
                    assert "description" not in step_overview[0]
            finally:
                app.dependency_overrides.clear()
    @pytest.mark.asyncio
    async def test_progress_tracking(
        self,
        test_user_id: str,
        mock_llm_response: dict,
        test_db: AsyncSession
    ):
        """Test progress tracking across sections and steps."""

        with patch('src.services.llm_service.LLMService.generate_guide') as mock_llm:
            mock_llm.return_value = (mock_llm_response, "mock_provider", 1.5)

            from src.auth.middleware import get_current_user
            async def mock_get_current_user():
                return test_user_id

            async def get_test_db():
                yield test_db

            app.dependency_overrides[get_current_user] = mock_get_current_user
            app.dependency_overrides[get_db] = get_test_db

            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    # Generate guide and get session
                    response = await client.post(
                        "/api/v1/instruction-guides/generate",
                        json={"instruction": "set up a development environment"}
                    )

                    assert response.status_code == 200
                    session_id = response.json()["session_id"]

                    # Check initial progress
                    response = await client.get(f"/api/v1/instruction-guides/{session_id}/progress")
                    assert response.status_code == 200

                    progress_data = response.json()
                    assert progress_data["progress"]["completed_steps"] == 0
                    assert progress_data["progress"]["total_steps"] == 3
                    assert progress_data["progress"]["completion_percentage"] == 0.0
                    assert progress_data["current_section"]["title"] == "Setup"

                    # Complete first step and check progress
                    await client.post(
                        f"/api/v1/instruction-guides/{session_id}/complete-step",
                        json={"completion_notes": "First step done"}
                    )

                    response = await client.get(f"/api/v1/instruction-guides/{session_id}/progress")
                    progress_data = response.json()

                    assert progress_data["progress"]["completed_steps"] == 1
                    assert progress_data["progress"]["completion_percentage"] == 33.3
                    assert progress_data["status"] == "active"
            finally:
                app.dependency_overrides.clear()
    @pytest.mark.asyncio
    async def test_help_request_functionality(
        self,
        test_user_id: str,
        mock_llm_response: dict,
        test_db: AsyncSession
    ):
        """Test requesting help for current step."""

        with patch('src.services.llm_service.LLMService.generate_guide') as mock_llm:
            mock_llm.return_value = (mock_llm_response, "mock_provider", 1.5)

            from src.auth.middleware import get_current_user
            async def mock_get_current_user():
                return test_user_id

            async def get_test_db():
                yield test_db

            app.dependency_overrides[get_current_user] = mock_get_current_user
            app.dependency_overrides[get_db] = get_test_db

            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    # Generate guide and get session
                    response = await client.post(
                        "/api/v1/instruction-guides/generate",
                        json={"instruction": "set up a development environment"}
                    )

                    assert response.status_code == 200
                    session_id = response.json()["session_id"]

                    # Request help for current step
                    response = await client.post(
                        f"/api/v1/instruction-guides/{session_id}/request-help",
                        json={
                            "issue": "I can't find the download link for Node.js",
                            "attempted_solutions": ["Searched on Google", "Checked official website"]
                        }
                    )

                    assert response.status_code == 200
                    help_data = response.json()

                    assert help_data["help_provided"] == True
                    assert "additional_hints" in help_data
                    assert len(help_data["additional_hints"]) > 0
                    assert "current_step" in help_data
            finally:
                app.dependency_overrides.clear()
    @pytest.mark.asyncio
    async def test_session_access_control(
        self,
        test_user_id: str,
        mock_llm_response: dict,
        test_db: AsyncSession
    ):
        """Test that users can only access their own sessions."""

        with patch('src.services.llm_service.LLMService.generate_guide') as mock_llm:
            mock_llm.return_value = (mock_llm_response, "mock_provider", 1.5)

            from src.auth.middleware import get_current_user
            async def mock_get_current_user():
                return test_user_id

            async def get_test_db():
                yield test_db

            app.dependency_overrides[get_current_user] = mock_get_current_user
            app.dependency_overrides[get_db] = get_test_db

            try:
                # Create session with first user
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post(
                        "/api/v1/instruction-guides/generate",
                        json={"instruction": "set up a development environment"}
                    )

                    assert response.status_code == 200
                    session_id = response.json()["session_id"]

                # Try to access session with different user
                async def mock_get_different_user():
                    return "different_user_456"
                app.dependency_overrides[get_current_user] = mock_get_different_user

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.get(f"/api/v1/instruction-guides/{session_id}/current-step")

                    # Should get 403 Forbidden
                    assert response.status_code == 403
                    assert "Access denied" in response.json()["detail"]
            finally:
                app.dependency_overrides.clear()
    @pytest.mark.asyncio
    async def test_complete_guide_workflow(
        self,
        test_user_id: str,
        mock_llm_response: dict,
        test_db: AsyncSession
    ):
        """Test completing an entire guide from start to finish."""

        with patch('src.services.llm_service.LLMService.generate_guide') as mock_llm:
            mock_llm.return_value = (mock_llm_response, "mock_provider", 1.5)

            from src.auth.middleware import get_current_user
            async def mock_get_current_user():
                return test_user_id

            async def get_test_db():
                yield test_db

            app.dependency_overrides[get_current_user] = mock_get_current_user
            app.dependency_overrides[get_db] = get_test_db

            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    # Generate guide
                    response = await client.post(
                        "/api/v1/instruction-guides/generate",
                        json={"instruction": "set up a development environment"}
                    )

                    assert response.status_code == 200
                    session_id = response.json()["session_id"]

                    # Complete all 3 steps
                    for step_num in range(3):
                        response = await client.post(
                            f"/api/v1/instruction-guides/{session_id}/complete-step",
                            json={"completion_notes": f"Completed step {step_num + 1}"}
                        )

                        assert response.status_code == 200

                        if step_num < 2:  # Not the last step
                            assert response.json()["status"] == "active"
                        else:  # Last step completed
                            assert response.json()["status"] == "completed"
                            assert "Guide completed successfully" in response.json()["message"]
            finally:
                app.dependency_overrides.clear()
