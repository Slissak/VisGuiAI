# Test Setup and Fixtures Guide

## Overview

This document describes the test infrastructure for the Step Guide Backend API, including available fixtures, database setup, mocking strategies, and best practices for writing tests.

## Table of Contents

1. [Test Infrastructure](#test-infrastructure)
2. [Available Fixtures](#available-fixtures)
3. [Database Testing](#database-testing)
4. [Mocking Strategies](#mocking-strategies)
5. [Writing Tests](#writing-tests)
6. [Running Tests](#running-tests)
7. [Troubleshooting](#troubleshooting)

---

## Test Infrastructure

### Architecture

The test suite uses:
- **pytest**: Test framework
- **pytest-asyncio**: Async test support
- **httpx.AsyncClient**: API testing client
- **SQLAlchemy**: Database ORM with async support
- **unittest.mock**: Mocking framework
- **In-memory SQLite**: Fast, isolated database for tests

### File Structure

```
backend/tests/
├── conftest.py              # Shared fixtures and configuration
├── test_*.py                # Integration tests
├── contract/                # API contract tests
├── integration/             # Integration tests
├── unit/                    # Unit tests
└── performance/             # Performance tests
```

---

## Available Fixtures

### Core Fixtures

#### `event_loop`
- **Scope**: session
- **Purpose**: Provides event loop for async tests
- **Usage**: Automatic - no need to explicitly use

```python
# Used automatically by pytest-asyncio
@pytest.mark.asyncio
async def test_something():
    await some_async_function()
```

#### `test_db_engine`
- **Scope**: function
- **Purpose**: Creates in-memory SQLite database engine
- **Usage**: Used by other database fixtures

```python
@pytest.mark.asyncio
async def test_with_engine(test_db_engine):
    # Engine is already set up with all tables created
    async with test_db_engine.begin() as conn:
        result = await conn.execute("SELECT 1")
```

#### `test_db`
- **Scope**: function
- **Purpose**: Provides database session for tests
- **Usage**: Direct database access in tests

```python
@pytest.mark.asyncio
async def test_database_operations(test_db):
    # Use test_db for database operations
    from src.models.database import StepGuideModel

    guide = StepGuideModel(
        title="Test Guide",
        description="Test description",
        total_steps=2,
        total_sections=1,
        estimated_duration_minutes=10,
        difficulty_level="beginner",
        category="test",
        guide_data={}
    )
    test_db.add(guide)
    await test_db.commit()
    await test_db.refresh(guide)

    assert guide.guide_id is not None
```

#### `get_test_database`
- **Scope**: function
- **Purpose**: Factory fixture that returns database session generator
- **Usage**: When you need a callable that provides database sessions

```python
from tests.conftest import get_test_database

@pytest.mark.asyncio
async def test_with_db_factory(get_test_database):
    async for db in get_test_database():
        # Use db session
        result = await db.execute("SELECT 1")
```

#### `client`
- **Scope**: function
- **Purpose**: HTTP client for API testing with automatic database override
- **Usage**: Main fixture for API integration tests

```python
@pytest.mark.asyncio
async def test_api_endpoint(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    # POST request
    response = await client.post(
        "/api/v1/guides/generate",
        json={"user_query": "test", "user_id": "test_user"}
    )
    assert response.status_code == 201
```

#### `authenticated_client`
- **Scope**: function
- **Purpose**: HTTP client with mock authentication headers
- **Usage**: For testing protected endpoints

```python
@pytest.mark.asyncio
async def test_protected_endpoint(authenticated_client):
    response = await authenticated_client.get("/api/v1/protected")
    assert response.status_code == 200
```

### Mock Fixtures

#### `mock_llm_service`
- **Scope**: function
- **Purpose**: Mock LLM service for testing without API calls
- **Usage**: Patch LLM service in tests

```python
from unittest.mock import patch

@pytest.mark.asyncio
async def test_guide_generation(client, mock_llm_service):
    with patch('src.services.llm_service.llm_service', mock_llm_service):
        response = await client.post(
            "/api/v1/instruction-guides/generate",
            json={"instruction": "test guide", "difficulty": "beginner"}
        )
        assert response.status_code == 200
```

The mock service returns:
```python
{
    "guide": {
        "title": "Mock Guide",
        "description": "A mock guide for testing",
        "category": "testing",
        "difficulty_level": "beginner",
        "estimated_duration_minutes": 15,
        "sections": [...]
    }
}
```

#### `mock_llm_response`
- **Scope**: function
- **Purpose**: Static mock response data for LLM calls
- **Usage**: Use in tests that need structured guide data

```python
def test_process_guide(mock_llm_response):
    guide_data = mock_llm_response["guide"]
    assert guide_data["title"] == "How to Set Up Python Virtual Environment"
    assert len(guide_data["sections"]) > 0
```

#### `mock_auth_user`
- **Scope**: function
- **Purpose**: Returns mock user ID for authentication
- **Usage**: Test user identification

```python
def test_user_context(mock_auth_user):
    assert mock_auth_user == "test_user_123"
```

#### `mock_get_current_user`
- **Scope**: function
- **Purpose**: Mock authentication dependency
- **Usage**: Override get_current_user in endpoints

```python
from src.auth.middleware import get_current_user

@pytest.mark.asyncio
async def test_with_mock_auth(client, mock_get_current_user):
    # Override the dependency
    from src.main import app
    app.dependency_overrides[get_current_user] = mock_get_current_user

    response = await client.get("/api/v1/protected")
    assert response.status_code == 200

    # Clean up
    app.dependency_overrides.clear()
```

### Sample Data Fixtures

#### `sample_guide_id`
- **Scope**: function
- **Purpose**: Creates a test guide and returns its ID
- **Usage**: For tests that need an existing guide

```python
@pytest.mark.asyncio
async def test_with_guide(client, sample_guide_id):
    # sample_guide_id is already created
    response = await client.get(f"/api/v1/guides/{sample_guide_id}")
    assert response.status_code == 200
```

#### `sample_session_id`
- **Scope**: function
- **Purpose**: Creates a test session and returns its ID
- **Usage**: For tests that need an existing session

```python
@pytest.mark.asyncio
async def test_with_session(client, sample_session_id):
    response = await client.get(f"/api/v1/sessions/{sample_session_id}")
    assert response.status_code == 200
```

---

## Database Testing

### In-Memory SQLite

Tests use in-memory SQLite for speed and isolation:

**Advantages:**
- Fast test execution
- No external dependencies
- Clean state for each test
- No test data pollution

**Limitations:**
- SQLite syntax differs slightly from PostgreSQL
- Some PostgreSQL-specific features may not work
- Array types are handled differently

### Database Lifecycle

```python
# Per-function lifecycle (default)
@pytest.mark.asyncio
async def test_example(test_db):
    # 1. Fresh database created
    # 2. All tables created from Base.metadata
    # 3. Your test runs
    # 4. Transaction rolled back
    # 5. Database dropped
```

### Working with Database Models

```python
from src.models.database import StepGuideModel, GuideSessionModel
from uuid import uuid4

@pytest.mark.asyncio
async def test_create_guide(test_db):
    # Create a guide
    guide = StepGuideModel(
        guide_id=uuid4(),
        title="Test Guide",
        description="Test Description",
        total_steps=3,
        total_sections=1,
        estimated_duration_minutes=15,
        difficulty_level="beginner",
        category="testing",
        guide_data={
            "sections": [
                {
                    "section_id": "test",
                    "section_title": "Test Section",
                    "steps": []
                }
            ]
        }
    )

    test_db.add(guide)
    await test_db.commit()
    await test_db.refresh(guide)

    # Query the guide
    from sqlalchemy import select
    result = await test_db.execute(
        select(StepGuideModel).where(StepGuideModel.guide_id == guide.guide_id)
    )
    fetched_guide = result.scalar_one()

    assert fetched_guide.title == "Test Guide"
```

---

## Mocking Strategies

### Mocking External Services

#### LLM Service Mocking

```python
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_with_mocked_llm(client):
    mock_response = {
        "guide": {
            "title": "Custom Mock Guide",
            "description": "Custom description",
            "sections": [...]
        }
    }

    with patch('src.services.llm_service.LLMService.generate_guide') as mock_gen:
        mock_gen.return_value = (mock_response, "mock_provider", 1.5)

        response = await client.post(
            "/api/v1/instruction-guides/generate",
            json={"instruction": "test"}
        )

        assert response.status_code == 200
        mock_gen.assert_called_once()
```

#### Authentication Mocking

```python
from unittest.mock import patch

@pytest.mark.asyncio
async def test_authenticated_endpoint(client):
    with patch('src.auth.middleware.get_current_user') as mock_auth:
        mock_auth.return_value = "test_user_123"

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/protected-endpoint")
            assert response.status_code == 200
```

### Mocking Redis

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_redis_mock():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True

    with patch('src.core.redis.get_redis_client', return_value=mock_redis):
        # Your test code using redis
        pass
```

---

## Writing Tests

### Test Structure

```python
import pytest
from httpx import AsyncClient

class TestFeatureName:
    """Test suite for specific feature."""

    @pytest.mark.asyncio
    async def test_specific_behavior(self, client: AsyncClient):
        """Test a specific behavior."""
        # Arrange: Set up test data
        test_data = {"key": "value"}

        # Act: Perform the action
        response = await client.post("/api/endpoint", json=test_data)

        # Assert: Verify the results
        assert response.status_code == 200
        data = response.json()
        assert "expected_key" in data
```

### Best Practices

1. **Use descriptive test names**
   ```python
   async def test_guide_generation_returns_sectioned_structure(self, client):
       """Test that guide generation returns guides with sections."""
   ```

2. **Follow AAA pattern** (Arrange, Act, Assert)
   ```python
   async def test_example(self, client):
       # Arrange
       test_input = {"query": "test"}

       # Act
       response = await client.post("/endpoint", json=test_input)

       # Assert
       assert response.status_code == 200
   ```

3. **Test one thing per test**
   ```python
   # Good - tests one specific behavior
   async def test_returns_404_when_guide_not_found(self, client):
       response = await client.get("/api/v1/guides/nonexistent-id")
       assert response.status_code == 404

   # Bad - tests multiple behaviors
   async def test_guide_endpoints(self, client):
       # Creates guide, lists guides, updates guide, deletes guide...
   ```

4. **Use fixtures for setup**
   ```python
   @pytest.fixture
   async def created_guide(self, client):
       """Create a guide for testing."""
       response = await client.post("/api/v1/guides/generate", json={...})
       return response.json()["guide_id"]

   async def test_guide_retrieval(self, client, created_guide):
       response = await client.get(f"/api/v1/guides/{created_guide}")
       assert response.status_code == 200
   ```

5. **Mock external dependencies**
   ```python
   from unittest.mock import patch

   async def test_with_mocked_service(self, client):
       with patch('src.services.external_service.call') as mock_call:
           mock_call.return_value = {"result": "mocked"}
           response = await client.post("/endpoint")
           assert response.status_code == 200
   ```

### Integration Test Example

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_guide_workflow(self, client):
    """Test complete workflow from guide generation to completion."""
    # Step 1: Generate guide
    gen_response = await client.post(
        "/api/v1/instruction-guides/generate",
        json={
            "instruction": "set up development environment",
            "difficulty": "beginner"
        }
    )
    assert gen_response.status_code == 200
    session_id = gen_response.json()["session_id"]

    # Step 2: Get current step
    step_response = await client.get(
        f"/api/v1/instruction-guides/{session_id}/current-step"
    )
    assert step_response.status_code == 200
    assert step_response.json()["current_step"]["step_index"] == 0

    # Step 3: Complete step
    complete_response = await client.post(
        f"/api/v1/instruction-guides/{session_id}/complete-step",
        json={"completion_notes": "Step completed"}
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["current_step"]["step_index"] == 1
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_instruction_guides_integration.py

# Run specific test
pytest tests/test_instruction_guides_integration.py::TestInstructionGuidesIntegration::test_generate_instruction_guide_workflow

# Run tests by marker
pytest -m integration
pytest -m "not performance"

# Run with verbose output
pytest -v

# Run with output (don't capture stdout)
pytest -s

# Run with coverage
pytest --cov=src --cov-report=html
```

### Test Markers

Available markers:
- `@pytest.mark.asyncio` - Async test
- `@pytest.mark.integration` - Integration test
- `@pytest.mark.unit` - Unit test
- `@pytest.mark.contract` - API contract test
- `@pytest.mark.performance` - Performance test
- `@pytest.mark.e2e` - End-to-end test

Example:
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_scenario(self, client):
    """Integration test example."""
    pass
```

### Environment Variables

Tests automatically set:
```bash
ENVIRONMENT=test
SECRET_KEY=test_secret_key_with_minimum_32_characters_required
DATABASE_URL=sqlite+aiosqlite:///:memory:
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=test_openai_key
ANTHROPIC_API_KEY=test_anthropic_key
```

---

## Troubleshooting

### Common Issues

#### 1. "ImportError: No module named 'src'"

**Solution**: Ensure you're running tests from the backend directory:
```bash
cd backend
pytest
```

#### 2. "Database URL must be a PostgreSQL connection string"

**Solution**: Tests override DATABASE_URL. If you see this, check conftest.py:
```python
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
```

#### 3. "RuntimeError: Event loop is closed"

**Solution**: Use `@pytest.mark.asyncio` decorator:
```python
@pytest.mark.asyncio
async def test_async_function():
    await some_async_call()
```

#### 4. "Table already exists"

**Solution**: This shouldn't happen with function-scoped fixtures. Check:
- Fixture scope is "function" not "session"
- Tables are dropped after each test
- Using `test_db` fixture properly

#### 5. Mock not working

**Solution**: Ensure you're patching the right location:
```python
# Patch where it's used, not where it's defined
# Wrong:
with patch('src.services.llm_service.LLMService.generate_guide'):

# Right (if imported in endpoint):
with patch('src.api.instruction_guides.llm_service.generate_guide'):
```

### Debug Tips

1. **Print database state**
   ```python
   async def test_debug(test_db):
       from sqlalchemy import select
       from src.models.database import StepGuideModel

       result = await test_db.execute(select(StepGuideModel))
       guides = result.scalars().all()
       print(f"Found {len(guides)} guides")
   ```

2. **Inspect response data**
   ```python
   async def test_debug(client):
       response = await client.post("/endpoint", json={...})
       print(f"Status: {response.status_code}")
       print(f"Body: {response.json()}")
   ```

3. **Check fixtures**
   ```python
   async def test_debug(test_db, client, mock_llm_service):
       print(f"DB: {test_db}")
       print(f"Client: {client}")
       print(f"Mock: {mock_llm_service}")
   ```

---

## Example Test Patterns

### Pattern 1: API Contract Test

```python
@pytest.mark.contract
@pytest.mark.asyncio
async def test_guide_generation_contract(self, client):
    """Verify API contract for guide generation."""
    response = await client.post(
        "/api/v1/instruction-guides/generate",
        json={
            "instruction": "test",
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

    # Verify types
    from uuid import UUID
    assert isinstance(UUID(data["session_id"]), UUID)
    assert isinstance(data["guide_title"], str)
```

### Pattern 2: Error Handling Test

```python
@pytest.mark.asyncio
async def test_handles_missing_guide(self, client):
    """Test 404 response for non-existent guide."""
    response = await client.get("/api/v1/guides/nonexistent-id")

    assert response.status_code == 404
    error = response.json()
    assert "error" in error
    assert "not found" in error["error"].lower()
```

### Pattern 3: Integration Test with Mocks

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_guide_workflow_with_mocks(self, client):
    """Test complete workflow with mocked LLM."""
    mock_guide = {...}  # Mock guide data

    with patch('src.services.llm_service.LLMService.generate_guide') as mock:
        mock.return_value = (mock_guide, "mock", 1.0)

        # Generate guide
        response = await client.post(
            "/api/v1/instruction-guides/generate",
            json={"instruction": "test"}
        )
        assert response.status_code == 200

        session_id = response.json()["session_id"]

        # Complete step
        response = await client.post(
            f"/api/v1/instruction-guides/{session_id}/complete-step",
            json={"completion_notes": "Done"}
        )
        assert response.status_code == 200
```

---

## Summary

This test infrastructure provides:
- Fast, isolated tests using in-memory SQLite
- Comprehensive fixtures for database, HTTP client, and mocks
- Easy mocking of external services (LLM, Redis, Auth)
- Clear patterns for writing maintainable tests
- Support for integration, unit, and contract tests

For questions or issues, refer to:
- `/Users/sivanlissak/Documents/VisGuiAI/backend/tests/conftest.py` - Fixture definitions
- `/Users/sivanlissak/Documents/VisGuiAI/backend/tests/test_instruction_guides_integration.py` - Example tests
- This document for usage patterns and troubleshooting
