from typing import Optional
from fastapi_mcp.types import AuthConfig


def build_auth_config(
    issuer: str,
    client_id: str,
    client_secret: Optional[str] = None,
    audience: Optional[str] = None,
) -> AuthConfig:
    return AuthConfig(
        issuer=issuer,
        client_id=client_id,
        client_secret=client_secret,
        audience=audience,
        authorize_url=f"{issuer}/protocol/openid-connect/auth",
        oauth_metadata_url=f"{issuer}/.well-known/openid-configuration",
        setup_proxies=True,
        setup_fake_dynamic_registration=True,
    )
