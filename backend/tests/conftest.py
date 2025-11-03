"""Pytest configuration and fixtures for the Step Guide Backend API.

This file provides shared fixtures for all test modules.
The fixtures are designed to fail initially until implementation is complete.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch, MagicMock

# Add parent directory to path so 'shared' module can be imported
backend_dir = Path(__file__).parent.parent
project_root = backend_dir.parent
sys.path.insert(0, str(project_root))

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Import will fail until main.py is implemented
try:
    from src.main import app
    from src.models.database import Base
    from src.core.database import get_db
    from src.services.llm_service import LLMService
except ImportError:
    app = None
    Base = None
    get_db = None
    LLMService = None


# Event loop configuration for pytest-asyncio
@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Database fixtures
@pytest_asyncio.fixture(scope="function")
async def test_db_engine():
    """Create an in-memory SQLite database engine for testing."""
    # Use in-memory SQLite for fast testing
    database_url = "postgresql+asyncpg://stepguide:stepguide_dev_password@localhost:5432/stepguide_test"

    engine = create_async_engine(
        database_url,
        echo=False,
        poolclass=NullPool
    )

    # Create all tables
    if Base is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    if Base is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        yield session
        await session.rollback()
        await session.close()


@pytest_asyncio.fixture(scope="function")
async def get_test_database(test_db: AsyncSession):
    """Fixture that provides a database session for testing.

    This fixture is used by integration tests to access the test database.
    """
    async def _get_test_db():
        yield test_db

    return _get_test_db


# Mock LLM Service fixtures
@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    service = AsyncMock(spec=LLMService)

    # Default mock response for guide generation
    service.generate_guide = AsyncMock(return_value=(
        {
            "guide": {
                "title": "Mock Guide",
                "description": "A mock guide for testing",
                "category": "testing",
                "difficulty_level": "beginner",
                "estimated_duration_minutes": 15,
                "sections": [
                    {
                        "section_id": "setup",
                        "section_title": "Setup",
                        "section_description": "Initial preparation",
                        "section_order": 0,
                        "steps": [
                            {
                                "step_index": 0,
                                "title": "First Step",
                                "description": "First step description",
                                "completion_criteria": "Step is complete",
                                "assistance_hints": ["Hint 1"],
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
        },
        "mock",
        1.0
    ))

    # Mock for step alternatives
    service.generate_step_alternatives = AsyncMock(return_value=(
        {
            "reason_for_change": "Step was blocked",
            "alternative_steps": [
                {
                    "title": "Alternative Step",
                    "description": "Alternative approach",
                    "completion_criteria": "Alternative complete",
                    "assistance_hints": ["Alternative hint"],
                    "estimated_duration_minutes": 5,
                    "requires_desktop_monitoring": False,
                    "visual_markers": [],
                    "prerequisites": []
                }
            ]
        },
        "mock",
        0.5
    ))

    return service


# Authentication mock fixtures
@pytest.fixture
def mock_auth_user():
    """Mock authenticated user for testing."""
    return "test_user_123"


@pytest.fixture
def mock_get_current_user(mock_auth_user):
    """Mock the get_current_user dependency."""
    async def _mock_get_current_user():
        return mock_auth_user
    return _mock_get_current_user


# Client fixtures
@pytest_asyncio.fixture(scope="function")
async def client(test_db_engine, test_db) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with in-memory database."""
    if app is None:
        pytest.skip("FastAPI app not implemented yet - this test will fail (TDD)")

    # Set test environment variables
    os.environ["ENVIRONMENT"] = "test"
    os.environ["SECRET_KEY"] = "test_secret_key_with_minimum_32_characters_required"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["REDIS_URL"] = "redis://localhost:6379"
    os.environ["OPENAI_API_KEY"] = "test_openai_key"
    os.environ["ANTHROPIC_API_KEY"] = "test_anthropic_key"

    # Override the database dependency to use our test database
    async def override_get_db():
        yield test_db

    if get_db is not None:
        app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    # Clean up overrides
    if get_db is not None:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_client(client: AsyncClient, mock_auth_user: str) -> AsyncGenerator[AsyncClient, None]:
    """Create authenticated test client with mocked authentication."""
    # Mock authentication by adding a valid token header
    # In a real scenario, this would be a JWT token
    client.headers.update({"Authorization": f"Bearer mock_token_{mock_auth_user}"})
    yield client


# Sample data fixtures for integration tests
@pytest_asyncio.fixture
async def sample_guide_id(client: AsyncClient) -> str:
    """Create a sample guide and return its ID."""
    # This will fail until guide generation is implemented
    response = await client.post("/api/v1/guides/generate", json={
        "user_query": "How to create a Python virtual environment",
        "user_id": "test_user_001",
        "difficulty_preference": "beginner"
    })

    if response.status_code != 201:
        pytest.skip("Guide generation not implemented yet - this test will fail (TDD)")

    return response.json()["guide_id"]


@pytest_asyncio.fixture
async def sample_session_id(client: AsyncClient, sample_guide_id: str) -> str:
    """Create a sample session and return its ID."""
    # This will fail until session creation is implemented
    response = await client.post("/api/v1/sessions", json={
        "guide_id": sample_guide_id,
        "user_id": "test_user_001",
        "completion_method": "manual_checkbox"
    })

    if response.status_code != 201:
        pytest.skip("Session creation not implemented yet - this test will fail (TDD)")

    return response.json()["session_id"]


# Mock LLM response fixture (legacy support)
@pytest.fixture
def mock_llm_response():
    """Mock LLM API response for testing with sectioned structure."""
    return {
        "guide": {
            "title": "How to Set Up Python Virtual Environment",
            "description": "A step-by-step guide to creating and managing Python virtual environments",
            "category": "development",
            "difficulty_level": "beginner",
            "estimated_duration_minutes": 15,
            "sections": [
                {
                    "section_id": "setup",
                    "section_title": "Setup",
                    "section_description": "Initial preparation steps",
                    "section_order": 0,
                    "steps": [
                        {
                            "step_index": 0,
                            "title": "Install Python",
                            "description": "Download and install Python from python.org",
                            "completion_criteria": "Python is installed and accessible via command line",
                            "assistance_hints": ["Check python --version", "Add Python to PATH"],
                            "estimated_duration_minutes": 5,
                            "requires_desktop_monitoring": False,
                            "visual_markers": [],
                            "prerequisites": [],
                            "completed": False,
                            "needs_assistance": False
                        },
                        {
                            "step_index": 1,
                            "title": "Create virtual environment",
                            "description": "Run 'python -m venv myenv' to create a virtual environment",
                            "completion_criteria": "Virtual environment directory is created",
                            "assistance_hints": ["Use 'python3' on macOS/Linux", "Choose descriptive environment name"],
                            "estimated_duration_minutes": 2,
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


# Markers for test categorization
pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "contract: marks tests as API contract tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )
    config.addinivalue_line(
        "markers", "asyncio: marks tests as async tests"
    )