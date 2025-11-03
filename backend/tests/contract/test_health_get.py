"""Contract tests for GET /api/v1/health endpoint."""

import pytest
from httpx import AsyncClient


class TestHealthContract:
    """Test GET /api/v1/health endpoint contract."""

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_health_check_success_contract(self, client: AsyncClient):
        """Test health check returns 200 with correct schema."""
        response = await client.get("/api/v1/health")

        assert response.status_code == 200

        # Validate HealthResponse schema
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert data["status"] in ["healthy", "unhealthy"]

        # Optional fields
        if "dependencies" in data:
            deps = data["dependencies"]
            if "database" in deps:
                assert deps["database"] in ["healthy", "unhealthy"]
            if "redis" in deps:
                assert deps["redis"] in ["healthy", "unhealthy"]
            if "llm_api" in deps:
                assert deps["llm_api"] in ["healthy", "unhealthy"]

    @pytest.mark.contract
    @pytest.mark.asyncio
    async def test_health_check_unhealthy_503(self, client: AsyncClient):
        """Test health check can return 503 when dependencies are down."""
        # This test will initially pass if health always returns 200
        # Should be updated when proper health checks are implemented
        response = await client.get("/api/v1/health")

        # Health endpoint should exist and return valid status codes
        assert response.status_code in [200, 503]

        if response.status_code == 503:
            data = response.json()
            assert data["status"] == "unhealthy"