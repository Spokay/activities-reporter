import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from auth.jwt import _jwks_cache
from main import app


@pytest.fixture
def mock_jwks_http(fake_jwks):
    with patch.object(_jwks_cache, "get", new_callable=AsyncMock) as m:
        m.return_value = fake_jwks
        yield m


# --- /mcp middleware ---

async def test_mcp_no_token_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/mcp")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing Bearer token"


async def test_mcp_invalid_token_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/mcp", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


async def test_mcp_valid_token_passes_middleware(mock_jwks_http, valid_token):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/mcp", headers={"Authorization": f"Bearer {valid_token}"})
    # Middleware passed — MCP handler may return anything but NOT a 401 from our guard
    assert resp.status_code != 401


# --- /api/reports router dependency ---

async def test_reports_no_token_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/reports",
            json={"city": "Paris", "start_date": "2024-01-01", "end_date": "2024-01-31"},
        )
    assert resp.status_code == 401


async def test_reports_valid_token_accepted(mock_jwks_http, valid_token):
    with patch("routes.reports.report_router.generate_report"):  # skip actual agent calls
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/reports",
                json={"city": "Paris", "start_date": "2024-01-01", "end_date": "2024-01-31"},
                headers={"Authorization": f"Bearer {valid_token}"},
            )
    assert resp.status_code in (200, 202)
