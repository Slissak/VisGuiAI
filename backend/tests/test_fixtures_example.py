"""Example tests demonstrating how to use the test fixtures.

This file provides practical examples of using the fixtures defined in conftest.py.
It serves as both documentation and validation that fixtures work correctly.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, AsyncMock
from uuid import uuid4


class TestFixtureExamples:
    """Examples of using test fixtures."""

    @pytest.mark.asyncio
    async def test_using_client_fixture(self, client: AsyncClient):
        """Example: Using the client fixture for API testing."""
        # The client fixture provides an HTTP client connected to the app
        response = await client.get("/api/v1/health")

        # Should get a successful response
        assert response.status_code in [200, 503]  # 503 if services not initialized

    @pytest.mark.asyncio
    async def test_using_test_db_fixture(self, test_db: AsyncSession):
        """Example: Using test_db fixture for direct database access."""
        from src.models.database import StepGuideModel

        # Create a test guide
        guide = StepGuideModel(
            guide_id=uuid4(),
            title="Example Guide",
            description="This is an example guide for testing",
            total_steps=2,
            total_sections=1,
            estimated_duration_minutes=10,
            difficulty_level="beginner",
            category="example",
            guide_data={
                "sections": [
                    {
                        "section_id": "example_section",
                        "section_title": "Example Section",
                        "section_description": "An example section",
                        "section_order": 0,
                        "steps": []
                    }
                ]
            }
        )

        test_db.add(guide)
        await test_db.commit()
        await test_db.refresh(guide)

        # Verify the guide was created
        assert guide.guide_id is not None
        assert guide.title == "Example Guide"

    @pytest.mark.asyncio
    async def test_using_mock_llm_service(self, client: AsyncClient, mock_llm_service):
        """Example: Using mock_llm_service fixture to mock LLM calls."""
        # Mock the LLM service with custom response
        custom_response = {
            "guide": {
                "title": "Custom Test Guide",
                "description": "A custom test guide",
                "category": "testing",
                "difficulty_level": "beginner",
                "estimated_duration_minutes": 5,
                "sections": [
                    {
                        "section_id": "test_section",
                        "section_title": "Test Section",
                        "section_description": "Test section description",
                        "section_order": 0,
                        "steps": [
                            {
                                "step_index": 0,
                                "title": "Test Step",
                                "description": "Test step description",
                                "completion_criteria": "Step complete",
                                "assistance_hints": ["Hint"],
                                "estimated_duration_minutes": 5,
                                "requires_desktop_monitoring": False,
                                "visual_markers": [],
                                "prerequisites": [],
                                "completed": False,
                                "needs_assistance": False
                            }
                        ]
                    }
                ]
            }
        }

        mock_llm_service.generate_guide.return_value = (custom_response, "mock", 1.0)

        # Use the mock in a test with patching
        with patch('src.services.llm_service.LLMService.generate_guide', mock_llm_service.generate_guide):
            # This would call the API endpoint that uses LLM service
            # The mock will be used instead of real LLM calls
            pass

    @pytest.mark.asyncio
    async def test_using_mock_auth(self, client: AsyncClient, mock_auth_user: str):
        """Example: Using mock authentication fixtures."""
        # mock_auth_user provides a test user ID
        assert mock_auth_user == "test_user_123"

        # To test authenticated endpoints, mock the get_current_user dependency
        with patch('src.auth.middleware.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_auth_user

            # Now API calls will be authenticated as the mock user
            # Example: response = await client.get("/api/v1/protected-endpoint")
            pass

    @pytest.mark.asyncio
    async def test_using_authenticated_client(self, authenticated_client: AsyncClient):
        """Example: Using authenticated_client fixture."""
        # authenticated_client has mock auth headers already set
        # This is useful for testing protected endpoints

        # The client has Authorization header set
        assert "Authorization" in authenticated_client.headers
        assert authenticated_client.headers["Authorization"].startswith("Bearer mock_token_")

    @pytest.mark.asyncio
    async def test_using_mock_llm_response(self, mock_llm_response: dict):
        """Example: Using mock_llm_response fixture for static test data."""
        # mock_llm_response provides structured guide data
        guide_data = mock_llm_response["guide"]

        assert guide_data["title"] == "How to Set Up Python Virtual Environment"
        assert guide_data["difficulty_level"] == "beginner"
        assert "sections" in guide_data
        assert len(guide_data["sections"]) > 0

        # Verify section structure
        first_section = guide_data["sections"][0]
        assert first_section["section_id"] == "setup"
        assert "steps" in first_section
        assert len(first_section["steps"]) > 0

    @pytest.mark.asyncio
    async def test_complete_workflow_example(self, client: AsyncClient):
        """Example: Complete integration test workflow with mocking."""
        # This example shows how to test a complete workflow

        # Step 1: Mock LLM service
        mock_guide_data = {
            "guide": {
                "title": "Workflow Test Guide",
                "description": "Testing complete workflow",
                "category": "testing",
                "difficulty_level": "beginner",
                "estimated_duration_minutes": 10,
                "sections": [
                    {
                        "section_id": "workflow_section",
                        "section_title": "Workflow Section",
                        "section_description": "Testing workflow",
                        "section_order": 0,
                        "steps": [
                            {
                                "step_index": 0,
                                "title": "First Step",
                                "description": "Complete the first step",
                                "completion_criteria": "Step is done",
                                "assistance_hints": ["Do this"],
                                "estimated_duration_minutes": 5,
                                "requires_desktop_monitoring": False,
                                "visual_markers": [],
                                "prerequisites": [],
                                "completed": False,
                                "needs_assistance": False
                            },
                            {
                                "step_index": 1,
                                "title": "Second Step",
                                "description": "Complete the second step",
                                "completion_criteria": "Step is done",
                                "assistance_hints": ["Do that"],
                                "estimated_duration_minutes": 5,
                                "requires_desktop_monitoring": False,
                                "visual_markers": [],
                                "prerequisites": [],
                                "completed": False,
                                "needs_assistance": False
                            }
                        ]
                    }
                ]
            }
        }

        # Step 2: Mock authentication
        with patch('src.services.llm_service.LLMService.generate_guide') as mock_llm:
            mock_llm.return_value = (mock_guide_data, "mock", 1.5)

            with patch('src.auth.middleware.get_current_user') as mock_auth:
                mock_auth.return_value = "workflow_test_user"

                # Step 3: Test the workflow
                # This would test: generate guide -> get current step -> complete step
                # For now, we just verify mocks are set up correctly
                assert mock_llm.return_value[0] == mock_guide_data
                assert mock_auth.return_value == "workflow_test_user"

    @pytest.mark.asyncio
    async def test_database_isolation(self, test_db: AsyncSession):
        """Example: Demonstrating database isolation between tests."""
        from src.models.database import StepGuideModel
        from sqlalchemy import select

        # This test demonstrates that each test gets a fresh database

        # Check that database is empty at start
        result = await test_db.execute(select(StepGuideModel))
        guides = result.scalars().all()
        assert len(guides) == 0, "Database should be empty at test start"

        # Create a guide
        guide = StepGuideModel(
            guide_id=uuid4(),
            title="Isolation Test Guide",
            description="Testing isolation",
            total_steps=1,
            total_sections=1,
            estimated_duration_minutes=5,
            difficulty_level="beginner",
            category="test",
            guide_data={"sections": []}
        )

        test_db.add(guide)
        await test_db.commit()

        # Verify guide exists
        result = await test_db.execute(select(StepGuideModel))
        guides = result.scalars().all()
        assert len(guides) == 1, "Should have one guide after creation"

        # After this test completes, the database is rolled back
        # The next test will start with a clean database


class TestAdvancedPatterns:
    """Advanced testing patterns using fixtures."""

    @pytest.fixture
    async def created_guide(self, test_db: AsyncSession):
        """Custom fixture that creates a guide for testing."""
        from src.models.database import StepGuideModel

        guide = StepGuideModel(
            guide_id=uuid4(),
            title="Fixture Created Guide",
            description="Guide created by fixture",
            total_steps=2,
            total_sections=1,
            estimated_duration_minutes=10,
            difficulty_level="intermediate",
            category="fixture",
            guide_data={
                "sections": [
                    {
                        "section_id": "fixture_section",
                        "section_title": "Fixture Section",
                        "section_description": "Created by fixture",
                        "section_order": 0,
                        "steps": []
                    }
                ]
            }
        )

        test_db.add(guide)
        await test_db.commit()
        await test_db.refresh(guide)

        return guide

    @pytest.mark.asyncio
    async def test_with_custom_fixture(self, test_db: AsyncSession, created_guide):
        """Example: Using a custom fixture defined in the test class."""
        # The created_guide fixture automatically creates a guide
        assert created_guide.guide_id is not None
        assert created_guide.title == "Fixture Created Guide"

        # We can use the guide in our test
        from sqlalchemy import select
        from src.models.database import StepGuideModel

        result = await test_db.execute(
            select(StepGuideModel).where(StepGuideModel.guide_id == created_guide.guide_id)
        )
        fetched_guide = result.scalar_one()

        assert fetched_guide.title == created_guide.title

    @pytest.mark.asyncio
    async def test_parametrized_with_fixtures(
        self,
        test_db: AsyncSession,
        difficulty_level: str
    ):
        """Example: Parametrized test with fixtures."""
        # Note: This requires @pytest.mark.parametrize decorator
        from src.models.database import StepGuideModel

        guide = StepGuideModel(
            guide_id=uuid4(),
            title=f"Guide - {difficulty_level}",
            description="Parametrized test guide",
            total_steps=1,
            total_sections=1,
            estimated_duration_minutes=5,
            difficulty_level=difficulty_level,
            category="parametrized",
            guide_data={"sections": []}
        )

        test_db.add(guide)
        await test_db.commit()

        assert guide.difficulty_level == difficulty_level


# Parametrize the test
TestAdvancedPatterns.test_parametrized_with_fixtures = pytest.mark.parametrize(
    "difficulty_level",
    ["beginner", "intermediate", "advanced"]
)(TestAdvancedPatterns.test_parametrized_with_fixtures)


@pytest.mark.asyncio
async def test_fixture_combination(
    client: AsyncClient,
    test_db: AsyncSession,
    mock_auth_user: str
):
    """Example: Combining multiple fixtures in a single test."""
    # This test demonstrates using multiple fixtures together

    # Access database directly
    from src.models.database import StepGuideModel
    from sqlalchemy import select

    result = await test_db.execute(select(StepGuideModel))
    guides = result.scalars().all()
    initial_count = len(guides)

    # Use authenticated user context
    assert mock_auth_user == "test_user_123"

    # Use HTTP client (which is also connected to test_db)
    response = await client.get("/api/v1/health")
    # Response might be 200 or 503 depending on if services are initialized
    assert response.status_code in [200, 503]

    # Verify database state hasn't changed from just health check
    result = await test_db.execute(select(StepGuideModel))
    guides = result.scalars().all()
    assert len(guides) == initial_count


if __name__ == "__main__":
    # This file can be run directly for quick testing
    pytest.main([__file__, "-v", "-s"])
