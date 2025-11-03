# Test Fixtures Quick Reference

## Quick Fixture Guide

This is a quick reference for commonly used test fixtures. For detailed documentation, see [TEST_SETUP.md](./TEST_SETUP.md).

---

## Database Fixtures

### `test_db` - Database Session
```python
@pytest.mark.asyncio
async def test_example(test_db: AsyncSession):
    from src.models.database import StepGuideModel
    guide = StepGuideModel(...)
    test_db.add(guide)
    await test_db.commit()
```

### `test_db_engine` - Database Engine
```python
@pytest.mark.asyncio
async def test_example(test_db_engine):
    async with test_db_engine.begin() as conn:
        result = await conn.execute("SELECT 1")
```

### `get_test_database` - Database Factory
```python
@pytest.mark.asyncio
async def test_example(get_test_database):
    async for db in get_test_database():
        # Use db session
        pass
```

---

## HTTP Client Fixtures

### `client` - Basic HTTP Client
```python
@pytest.mark.asyncio
async def test_example(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    response = await client.post("/api/v1/endpoint", json={...})
```

### `authenticated_client` - Authenticated Client
```python
@pytest.mark.asyncio
async def test_example(authenticated_client: AsyncClient):
    # Has Authorization header pre-configured
    response = await authenticated_client.get("/api/v1/protected")
```

---

## Mock Fixtures

### `mock_llm_service` - Mock LLM Service
```python
@pytest.mark.asyncio
async def test_example(mock_llm_service):
    # Configure mock response
    mock_llm_service.generate_guide.return_value = (guide_data, "mock", 1.0)

    # Use in test
    with patch('src.services.llm_service.LLMService.generate_guide',
               mock_llm_service.generate_guide):
        # Your test code
        pass
```

### `mock_llm_response` - Static Mock Data
```python
def test_example(mock_llm_response: dict):
    guide = mock_llm_response["guide"]
    assert guide["title"] == "How to Set Up Python Virtual Environment"
```

### `mock_auth_user` - Mock User ID
```python
def test_example(mock_auth_user: str):
    assert mock_auth_user == "test_user_123"
```

### `mock_get_current_user` - Mock Auth Dependency
```python
@pytest.mark.asyncio
async def test_example(mock_get_current_user):
    from src.auth.middleware import get_current_user
    from src.main import app

    app.dependency_overrides[get_current_user] = mock_get_current_user
    # Your test code
    app.dependency_overrides.clear()
```

---

## Sample Data Fixtures

### `sample_guide_id` - Created Guide ID
```python
@pytest.mark.asyncio
async def test_example(client: AsyncClient, sample_guide_id: str):
    response = await client.get(f"/api/v1/guides/{sample_guide_id}")
    assert response.status_code == 200
```

### `sample_session_id` - Created Session ID
```python
@pytest.mark.asyncio
async def test_example(client: AsyncClient, sample_session_id: str):
    response = await client.get(f"/api/v1/sessions/{sample_session_id}")
    assert response.status_code == 200
```

---

## Common Test Patterns

### Pattern 1: API Test with Mocked LLM
```python
@pytest.mark.asyncio
async def test_api_with_mocked_llm(client: AsyncClient):
    mock_data = {"guide": {...}}

    with patch('src.services.llm_service.LLMService.generate_guide') as mock:
        mock.return_value = (mock_data, "mock", 1.0)

        response = await client.post("/api/v1/endpoint", json={...})
        assert response.status_code == 200
```

### Pattern 2: Database Test
```python
@pytest.mark.asyncio
async def test_database_operation(test_db: AsyncSession):
    from src.models.database import StepGuideModel
    from sqlalchemy import select

    # Create
    guide = StepGuideModel(...)
    test_db.add(guide)
    await test_db.commit()

    # Query
    result = await test_db.execute(select(StepGuideModel))
    guides = result.scalars().all()
    assert len(guides) > 0
```

### Pattern 3: Integration Test
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_workflow(client: AsyncClient):
    # Step 1: Create resource
    response = await client.post("/api/v1/guides/generate", json={...})
    guide_id = response.json()["guide_id"]

    # Step 2: Use resource
    response = await client.get(f"/api/v1/guides/{guide_id}")
    assert response.status_code == 200

    # Step 3: Modify resource
    response = await client.put(f"/api/v1/guides/{guide_id}", json={...})
    assert response.status_code == 200
```

### Pattern 4: Authenticated Test
```python
@pytest.mark.asyncio
async def test_protected_endpoint(client: AsyncClient):
    with patch('src.auth.middleware.get_current_user') as mock_auth:
        mock_auth.return_value = "test_user_123"

        response = await client.get("/api/v1/protected")
        assert response.status_code == 200
```

### Pattern 5: Custom Fixture
```python
@pytest.fixture
async def custom_test_data(test_db: AsyncSession):
    """Create custom test data."""
    # Setup code
    data = create_test_data()
    test_db.add(data)
    await test_db.commit()

    yield data

    # Teardown (if needed)
    # Usually not needed as test_db handles rollback

@pytest.mark.asyncio
async def test_with_custom_fixture(custom_test_data):
    assert custom_test_data is not None
```

---

## Test Markers

```python
@pytest.mark.asyncio          # Async test (REQUIRED for async tests)
@pytest.mark.integration      # Integration test
@pytest.mark.unit            # Unit test
@pytest.mark.contract        # API contract test
@pytest.mark.performance     # Performance test
@pytest.mark.e2e            # End-to-end test

# Example:
@pytest.mark.integration
@pytest.mark.asyncio
async def test_example():
    pass
```

---

## Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_filename.py

# Specific test
pytest tests/test_file.py::TestClass::test_method

# By marker
pytest -m integration
pytest -m "integration and not performance"

# Verbose
pytest -v

# With output
pytest -s

# With coverage
pytest --cov=src --cov-report=html
```

---

## Common Issues

### Issue: Import errors
```bash
# Solution: Run from backend directory
cd backend
pytest
```

### Issue: Event loop errors
```python
# Solution: Add @pytest.mark.asyncio
@pytest.mark.asyncio
async def test_async():
    pass
```

### Issue: Database errors
```python
# Solution: Use test_db fixture
@pytest.mark.asyncio
async def test_db_operation(test_db: AsyncSession):
    # Database operations here
```

### Issue: Mock not working
```python
# Solution: Patch where it's used, not where it's defined
# Correct:
with patch('src.api.endpoint.llm_service.generate_guide'):

# Incorrect:
with patch('src.services.llm_service.LLMService.generate_guide'):
```

---

## Fixture Scope

- `session` - Once per test session
- `module` - Once per module
- `class` - Once per test class
- `function` - Once per test function (default, most fixtures)

```python
@pytest.fixture(scope="function")  # New instance per test
async def test_db():
    # Fresh database for each test
    pass
```

---

## Files to Reference

1. **Fixture Definitions**: `/Users/sivanlissak/Documents/VisGuiAI/backend/tests/conftest.py`
2. **Full Documentation**: `/Users/sivanlissak/Documents/VisGuiAI/backend/docs/TEST_SETUP.md`
3. **Example Tests**: `/Users/sivanlissak/Documents/VisGuiAI/backend/tests/test_fixtures_example.py`
4. **Integration Tests**: `/Users/sivanlissak/Documents/VisGuiAI/backend/tests/test_instruction_guides_integration.py`

---

## Quick Tips

1. **Always use `@pytest.mark.asyncio` for async tests**
2. **Database is automatically cleaned between tests** (function scope)
3. **Mock external services** (LLM, Redis, external APIs)
4. **Use fixtures for setup** - avoid repetitive setup code
5. **Test one thing per test** - focused, clear tests
6. **Follow AAA pattern** - Arrange, Act, Assert
7. **Use descriptive test names** - they serve as documentation

---

## Getting Help

- See `TEST_SETUP.md` for detailed documentation
- See `test_fixtures_example.py` for practical examples
- Check `conftest.py` for available fixtures and their implementation
- Run `pytest --fixtures` to see all available fixtures
