import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from auth.jwt import verify_token, require_auth, _jwks_cache
from tests.conftest import ISSUER, AUDIENCE


@pytest.fixture
def mock_jwks(fake_jwks):
    with patch.object(_jwks_cache, "get", new_callable=AsyncMock) as m:
        m.return_value = fake_jwks
        yield m


# --- verify_token ---

async def test_verify_token_valid(mock_jwks, valid_token):
    claims = await verify_token(valid_token)
    assert claims["sub"] == "test-user"
    assert claims["iss"] == ISSUER


async def test_verify_token_expired(mock_jwks, make_token):
    token = make_token(exp_offset=-10)
    with pytest.raises(HTTPException) as exc:
        await verify_token(token)
    assert exc.value.status_code == 401


async def test_verify_token_wrong_issuer(mock_jwks, make_token):
    token = make_token(issuer="https://evil.example.com/realm")
    with pytest.raises(HTTPException) as exc:
        await verify_token(token)
    assert exc.value.status_code == 401


async def test_verify_token_wrong_audience(mock_jwks, make_token):
    token = make_token(audience="wrong-client")
    with pytest.raises(HTTPException) as exc:
        await verify_token(token)
    assert exc.value.status_code == 401


async def test_verify_token_retries_on_stale_jwks(fake_jwks, make_token):
    """Stale JWKS on first call → retry with force=True returns fresh JWKS → decode succeeds."""
    call_count = 0

    async def flaky_get(force: bool = False):
        nonlocal call_count
        call_count += 1
        return {"keys": []} if not force else fake_jwks  # empty keys → JWTError on first try

    with patch.object(_jwks_cache, "get", side_effect=flaky_get):
        claims = await verify_token(make_token())

    assert claims["sub"] == "test-user"
    assert call_count == 2


# --- require_auth ---

async def test_require_auth_bypassed_when_no_oauth(monkeypatch):
    mock_settings = MagicMock()
    mock_settings.oauth_issuer = None
    monkeypatch.setattr("auth.jwt.get_settings", lambda: mock_settings)
    result = await require_auth(credentials=None)
    assert result is None


async def test_require_auth_no_credentials_raises_401(monkeypatch):
    mock_settings = MagicMock()
    mock_settings.oauth_issuer = ISSUER
    monkeypatch.setattr("auth.jwt.get_settings", lambda: mock_settings)
    with pytest.raises(HTTPException) as exc:
        await require_auth(credentials=None)
    assert exc.value.status_code == 401


async def test_require_auth_valid_credentials(mock_jwks, valid_token):
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_token)
    claims = await require_auth(credentials=creds)
    assert claims["sub"] == "test-user"
